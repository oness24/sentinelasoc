"""Camada de dados estruturados: carga dos CSVs no DuckDB e consulta segura.

Seguranca: `run_select` aceita exclusivamente consultas SELECT de leitura --
qualquer comando de escrita, multiplos statements ou chamadas de funcao
perigosas sao rejeitados antes de tocarem o banco.
"""

import re
import threading
from pathlib import Path

import duckdb

from sentinelasoc.settings import get_settings
from sentinelasoc.telemetry import get_logger

log = get_logger(__name__)
_lock = threading.Lock()

# Palavras reservadas que caracterizam escrita/modificacao ou acesso a recursos.
_FORBIDDEN = re.compile(
    r"\b(insert|update|delete|drop|alter|create|replace|copy|export|import|attach|detach|"
    r"pragma|call|set|prepare|execute|read_csv|read_parquet|glob)\b",
    re.IGNORECASE,
)


def _tabelas() -> dict[str, Path]:
    s = get_settings()
    return {
        "ativos": s.data_dir / "ativos.csv",
        "incidentes": s.data_dir / "incidentes.csv",
        "vulnerabilidades": s.data_dir / "vulnerabilidades.csv",
    }


def conectar(refresh: bool = False) -> duckdb.DuckDBPyConnection:
    """Conecta ao banco DuckDB, criando-o a partir dos CSVs na primeira execucao."""
    with _lock:
        s = get_settings()
        precisa_criar = refresh or not s.db_path.exists()  # testar ANTES do connect
        con = duckdb.connect(str(s.db_path))
        if precisa_criar:
            for tabela, caminho in _tabelas().items():
                con.execute(
                    f"CREATE OR REPLACE TABLE {tabela} AS SELECT * FROM read_csv_auto('{caminho}')"
                )
        return con


def schema_descritivo() -> str:
    """Esquema das tabelas (em texto) injetado no prompt de geracao de SQL."""
    return """Tabelas disponiveis no DuckDB (dados sinteticos da Aurora Tecnologia, periodo 2025-09 a 2026-09-20):

TABELA ativos (catalogo de ativos de TI):
  ativo_id TEXT (PK, ex ATV-001) | hostname TEXT | ip TEXT | sistema_operacional TEXT
  ambiente TEXT ('Producao','Homologacao','DMZ') | criticidade TEXT ('Alta','Media','Baixa')
  departamento TEXT | responsavel TEXT | exposto_internet TEXT ('Sim','Nao')

TABELA incidentes (incidentes de seguranca registrados pelo SOC):
  incidente_id TEXT (PK, ex INC-2026-0001) | ativo_id TEXT (FK -> ativos)
  data_abertura DATE | tipo TEXT ('Phishing','Forca Bruta','Malware','DDoS','Exfiltracao de Dados','Acesso Anomalo','Vulnerabilidade Explorada','Engenharia Social')
  severidade TEXT ('Critica','Alta','Media','Baixa') | tatica_mitre TEXT (ex 'T1566 - Initial Access')
  status TEXT ('Aberto','Em atendimento','Resolvido') | analista_responsavel TEXT
  horas_para_resolver DOUBLE (vazio quando nao resolvido) | falso_positivo TEXT ('Sim','Nao')

TABELA vulnerabilidades (falhas detectadas nos ativos):
  vulnerabilidade_id TEXT (PK, ex VULN-001) | ativo_id TEXT (FK -> ativos)
  cve TEXT | descricao TEXT | cvss DOUBLE (0 a 10)
  data_deteccao DATE | status TEXT ('Aberta','Em correcao','Corrigida') | prazo_sla_dias INTEGER

Relacionamentos: incidentes.ativo_id -> ativos.ativo_id; vulnerabilidades.ativo_id -> ativos.ativo_id.
Datas no formato DATE 'YYYY-MM-DD'. Hoje e 2026-09-20.

DICAS IMPORTANTES:
- A coluna severidade existe SOMENTE em incidentes. A criticidade de uma vulnerabilidade
  e expressa pelo cvss (critica = cvss >= 9.0; alta = cvss >= 7.0).
- Comparacoes de texto sao CASE-SENSITIVE: copie a capitalizacao EXATA dos valores listados
  acima (ex.: status = 'Aberta', NUNCA 'aberta'; severidade = 'Critica').
- Taxas/percentuais de um subgrupo: o DENOMINADOR deve ter o MESMO filtro do grupo
  perguntado. Forma segura: 100.0 * SUM(CASE WHEN <grupo> AND <condicao> THEN 1 ELSE 0 END)
  / SUM(CASE WHEN <grupo> THEN 1 ELSE 0 END) — nunca divida por COUNT(*) sem o filtro do grupo.
- Taxa POR tipo/grupo (GROUP BY): calcule a razao dentro de cada grupo, ex.:
  SELECT tipo, ROUND(100.0 * SUM(CASE WHEN falso_positivo = 'Sim' THEN 1 ELSE 0 END) / COUNT(*), 1)
  AS taxa FROM incidentes GROUP BY tipo ORDER BY taxa DESC.
- 'Agora'/'abertos agora' = status IN ('Aberto','Em atendimento')."""


class SQLBloqueadoError(ValueError):
    """Levantada quando a consulta viola a politica somente-leitura."""


# Valores enumeraveis por coluna (para normalizacao de literais gerados por LLM)
_VALORES_COLUNA: dict[str, list[str]] = {
    "status": ["Aberto", "Em atendimento", "Resolvido", "Aberta", "Em correcao", "Corrigida"],
    "severidade": ["Critica", "Alta", "Media", "Baixa"],
    "criticidade": ["Alta", "Media", "Baixa"],
    "ambiente": ["Producao", "Homologacao", "DMZ"],
    "exposto_internet": ["Sim", "Nao"],
    "falso_positivo": ["Sim", "Nao"],
    "tipo": [
        "Phishing",
        "Forca Bruta",
        "Malware",
        "DDoS",
        "Exfiltracao de Dados",
        "Acesso Anomalo",
        "Vulnerabilidade Explorada",
        "Engenharia Social",
    ],
}


def normalizar_literais(sql: str) -> str:
    """Corrige literais de texto com capitalizacao errada (ex.: 'aberta' -> 'Aberta').

    O LLM frequentemente gera minusculas; DuckDB e case-sensitive. Comparamos contra
    os valores enumeraveis conhecidos do esquema e substituimos apenas casamentos exatos
    (ignorando caixa). Literais desconhecidos sao preservados.
    """
    mapa = {
        (coluna, valor.lower()): valor
        for coluna, valores in _VALORES_COLUNA.items()
        for valor in valores
    }

    def _troca(m: re.Match) -> str:
        coluna, literal = m.group(1), m.group(2)
        canonico = mapa.get((coluna.lower(), literal.lower()))
        if canonico and canonico != literal:
            log.info("db.literal.normalizado coluna=%s %r -> %r", coluna, literal, canonico)
            return f"{coluna} = '{canonico}'"
        return m.group(0)

    return re.sub(r"(\w+)\s*=\s*'([^']*)'", _troca, sql, flags=re.IGNORECASE)


def validar_sql(sql: str) -> str:
    """Valida a consulta contra a politica somente-leitura e a retorna normalizada."""
    s = sql.strip().rstrip(";").strip()
    if not re.match(r"^(select|with)\b", s, re.IGNORECASE):
        log.warning("db.guard.blocked motivo=nao_select sql=%r", s[:80])
        raise SQLBloqueadoError("Apenas consultas SELECT sao permitidas.")
    if ";" in s:
        log.warning("db.guard.blocked motivo=multiplos_statements sql=%r", s[:80])
        raise SQLBloqueadoError("Somente uma declaracao por consulta.")
    if _FORBIDDEN.search(s):
        log.warning("db.guard.blocked motivo=comando_bloqueado sql=%r", s[:80])
        raise SQLBloqueadoError(
            "Comando de escrita/modificacao/acesso bloqueado pelo guarda de SQL."
        )
    return s


def run_select(sql: str) -> tuple[list[str], list[tuple]]:
    """Executa uma consulta validada e devolve (colunas, linhas), com limite de linhas."""
    s = get_settings()
    consulta = validar_sql(sql)
    consulta = normalizar_literais(consulta)
    con = conectar()
    try:
        cur = con.execute(f"SELECT * FROM ({consulta}) _consulta LIMIT {s.sql_max_rows}")
        colunas = [d[0] for d in cur.description]
        linhas = cur.fetchall()
        log.info("db.query ok=true linhas=%d", len(linhas))
        return colunas, linhas
    finally:
        con.close()
