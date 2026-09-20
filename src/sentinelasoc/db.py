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


def _enumerar_valores(con: duckdb.DuckDBPyConnection) -> dict[str, list[str]]:
    """Valores distintos (cardinalidade <= 10) por coluna TEXT — enums do esquema."""
    enums: dict[str, list[str]] = {}
    colunas = con.execute(
        "SELECT table_name, column_name FROM information_schema.columns "
        "WHERE table_schema = 'main' AND data_type = 'VARCHAR'"
    ).fetchall()
    for tabela, coluna in colunas:
        distintos = con.execute(
            f'SELECT DISTINCT "{coluna}" FROM "{tabela}" WHERE "{coluna}" IS NOT NULL LIMIT 11'
        ).fetchall()
        if 0 < len(distintos) <= 10:  # 11+ distintos = nao e enum
            enums[coluna] = [str(v[0]) for v in distintos]
    return enums


_ENUM_CACHE: tuple[float, dict[str, list[str]]] | None = None


def _enums() -> dict[str, list[str]]:
    """Enums do esquema com cache por mtime do banco (invalida ao reconstruir)."""
    global _ENUM_CACHE
    s = get_settings()
    try:
        mtime = s.db_path.stat().st_mtime
    except OSError:
        mtime = 0.0
    if _ENUM_CACHE and _ENUM_CACHE[0] == mtime:
        return _ENUM_CACHE[1]
    con = conectar()
    try:
        enums = _enumerar_valores(con)
    finally:
        con.close()
    _ENUM_CACHE = (mtime, enums)
    return enums


def schema_descritivo() -> str:
    """Esquema introspectado ao vivo do DuckDB (tabelas, tipos, enums, contagens).

    Nada hardcoded: trocar os CSVs por outros dados torna o sistema utilizavel
    sem alteracao de codigo — o prompt de SQL se monta sozinho.
    """
    con = conectar()
    try:
        tabelas = [
            r[0]
            for r in con.execute(
                "SELECT table_name FROM information_schema.tables "
                "WHERE table_schema = 'main' ORDER BY table_name"
            ).fetchall()
        ]
        enums = _enumerar_valores(con)
        blocos: list[str] = []
        for tabela in tabelas:
            linha_total = con.execute(f'SELECT COUNT(*) FROM "{tabela}"').fetchone()
            total = int(linha_total[0]) if linha_total else 0
            colunas = con.execute(
                "SELECT column_name, data_type FROM information_schema.columns "
                "WHERE table_schema = 'main' AND table_name = ? ORDER BY ordinal_position",
                [tabela],
            ).fetchall()
            partes = []
            for nome, tipo in colunas:
                partes.append(f"{nome} {tipo.upper()}")
                if nome in enums:
                    partes.append(f"('{enums[nome][0]}')")
            blocos.append(f"TABELA {tabela} ({total} linhas): " + " | ".join(partes))

        # relacionamentos por convencao <nome>_id repetido entre tabelas
        todas: dict[str, set[str]] = {}
        for tabela in tabelas:
            for (nome,) in con.execute(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_schema = 'main' AND table_name = ?",
                [tabela],
            ).fetchall():
                if nome.endswith("_id"):
                    todas.setdefault(nome, set()).add(tabela)
        rels = [
            f"{coluna} presente em {', '.join(sorted(ts))} (chave de relacionamento)"
            for coluna, ts in sorted(todas.items())
            if len(ts) > 1
        ]
    finally:
        con.close()

    rel_linha = ("\n" + "\n".join(rels)) if rels else ""
    return (
        "Tabelas disponiveis no DuckDB (esquema introspectado automaticamente):\n\n"
        + "\n\n".join(blocos)
        + rel_linha
        + "\n\nValores possiveis das colunas enumeraveis: "
        + "; ".join(f"{c}: {', '.join(vs)}" for c, vs in sorted(enums.items()))
        + "\n\nDICAS IMPORTANTES:\n"
        "- Comparacoes de texto sao CASE-SENSITIVE: copie a capitalizacao EXATA dos valores acima.\n"
        "- Taxas/percentuais de um subgrupo: o DENOMINADOR deve ter o MESMO filtro do grupo\n"
        "  perguntado (100.0 * SUM(CASE WHEN <grupo> AND <cond> THEN 1 ELSE 0 END)\n"
        "  / SUM(CASE WHEN <grupo> THEN 1 ELSE 0 END)).\n"
        "- Perguntas com 'quantos' pedem COUNT do predicado exato; 'taxa' pede razao com divisao.\n"
        "- Datas como DATE 'YYYY-MM-DD'."
    )


class SQLBloqueadoError(ValueError):
    """Levantada quando a consulta viola a politica somente-leitura."""


def normalizar_literais(sql: str) -> str:
    """Corrige literais de texto com capitalizacao errada (ex.: 'aberta' -> 'Aberta').

    O LLM frequentemente gera minusculas; DuckDB e case-sensitive. Comparamos contra
    os valores enumeraveis do proprio esquema (introspectados em _enums) e substituimos
    apenas casamentos exatos (ignorando caixa). Literais desconhecidos sao preservados.
    """
    mapa: dict[tuple[str, str], str] = {}
    for coluna, valores in _enums().items():
        for valor in valores:
            mapa[(coluna.lower(), valor.lower())] = valor

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
