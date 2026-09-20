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


def _enumerar_valores(con: duckdb.DuckDBPyConnection) -> dict[tuple[str, str], list[str]]:
    """Valores distintos (cardinalidade <= 10) por (tabela, coluna) — enums do esquema.

    Escopo por tabela e essencial: `status` vale 'Aberto' em incidentes e 'Aberta'
    em vulnerabilidades; fundir os dois induz o LLM ao erro.
    """
    enums: dict[tuple[str, str], list[str]] = {}
    colunas = con.execute(
        "SELECT table_name, column_name FROM information_schema.columns "
        "WHERE table_schema = 'main' AND data_type = 'VARCHAR'"
    ).fetchall()
    for tabela, coluna in colunas:
        distintos = con.execute(
            f'SELECT DISTINCT "{coluna}" FROM "{tabela}" WHERE "{coluna}" IS NOT NULL LIMIT 11'
        ).fetchall()
        if 0 < len(distintos) <= 10:  # 11+ distintos = nao e enum
            enums[(tabela, coluna)] = [str(v[0]) for v in distintos]
    return enums


_ENUM_CACHE: tuple[float, dict[tuple[str, str], list[str]]] | None = None


def _enums() -> dict[tuple[str, str], list[str]]:
    """Enums (tabela, coluna) com cache por mtime do banco."""
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
                parte = f"{nome} {tipo.upper()}"
                if (tabela, nome) in enums:
                    parte += " (" + ", ".join(enums[(tabela, nome)]) + ")"
                partes.append(parte)
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
        "Tabelas disponiveis no DuckDB (esquema introspectado automaticamente;\n"
        "os valores entre parenteses sao os UNICOS aceitos por cada coluna — respeite\n"
        "a tabela de origem, ex.: status de incidentes e 'Aberto', de vulnerabilidades 'Aberta'):\n\n"
        + "\n\n".join(blocos)
        + rel_linha
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


def _alias_para_tabela(sql: str) -> dict[str, str]:
    """Mapeia alias -> tabela a partir de FROM/JOIN (ex.: 'i' -> 'incidentes')."""
    mapa: dict[str, str] = {}
    for m in re.finditer(
        r"\b(?:FROM|JOIN)\s+([a-zA-Z_]\w*)(?:\s+(?:AS\s+)?([a-zA-Z_]\w*))?", sql, re.IGNORECASE
    ):
        tabela, alias = m.group(1), m.group(2)
        if alias and alias.upper() not in {
            "ON",
            "USING",
            "WHERE",
            "GROUP",
            "ORDER",
            "LIMIT",
            "INNER",
            "LEFT",
            "RIGHT",
            "FULL",
            "CROSS",
            "NATURAL",
            "SET",
            "VALUES",
        }:
            mapa[alias] = tabela
        mapa[tabela] = tabela
    return mapa


def _valores_validos(sql: str, qualificador: str, coluna: str) -> list[str] | None:
    """Valores validos para a coluna no escopo da consulta (por tabela quando possivel)."""
    enums = _enums()
    tabelas_com_coluna = [t for (t, c) in enums if c == coluna]
    if not tabelas_com_coluna:
        return None
    tabela = _alias_para_tabela(sql).get(qualificador or coluna)
    if tabela and (tabela, coluna) in enums:
        return enums[(tabela, coluna)]
    if len(tabelas_com_coluna) == 1:
        return enums[(tabelas_com_coluna[0], coluna)]
    validos: list[str] = []
    for t in tabelas_com_coluna:
        validos.extend(v for v in enums[(t, coluna)] if v not in validos)
    return validos


def normalizar_literais(sql: str) -> str:
    """Corrige literais de texto com capitalizacao errada (ex.: 'aberta' -> 'Aberta').

    O LLM frequentemente gera minusculas; DuckDB e case-sensitive. Comparamos contra
    os valores enumeraveis do esquema, com escopo por tabela quando o SQL permite
    (alias ou coluna exclusiva), e substituimos apenas casamentos exatos ignorando
    caixa. Literais desconhecidos sao preservados.
    """

    def _troca(m: re.Match) -> str:
        prefixo, coluna, literal = m.group(1), m.group(2), m.group(3)
        qualificador = (prefixo or "").removesuffix(".")
        validos = _valores_validos(sql, qualificador, coluna)
        if validos:
            alvo = next((v for v in validos if v.lower() == literal.lower()), None)
            if alvo and alvo != literal:
                log.info("db.literal.normalizado coluna=%s %r -> %r", coluna, literal, alvo)
                return f"{prefixo}{coluna} = '{alvo}'"
        return m.group(0)

    return re.sub(r"((?:\w+\.)?)(\w+)\s*=\s*'([^']*)'", _troca, sql, flags=re.IGNORECASE)


def _distancia1(a: str, b: str) -> bool:
    """Distancia de edicao <= 1 (troca/insercao/remocao de um caractere)."""
    if a == b:
        return True
    if abs(len(a) - len(b)) > 1:
        return False
    if len(a) == len(b):
        return sum(x != y for x, y in zip(a, b, strict=True)) <= 1
    menor, maior = (a, b) if len(a) < len(b) else (b, a)
    i = j = divergencias = 0
    while i < len(menor) and j < len(maior):
        if menor[i] == maior[j]:
            i += 1
            j += 1
        else:
            divergencias += 1
            j += 1
            if divergencias > 1:
                return False
    return True


def literal_proximo(sql: str) -> list[tuple[str, str]]:
    """Literais enum invalidos perto de um valor valido (distancia <= 1).

    Ex.: em consulta sobre `incidentes`, status = 'Aberta' (valor de vulnerabilidades)
    esta a um caractere de 'Aberto'. Serve para feedback de autocorrecao quando a
    consulta retorna zero linhas.
    """
    achados: list[tuple[str, str]] = []
    for m in re.finditer(r"((?:\w+\.)?)(\w+)\s*=\s*'([^']*)'", sql, re.IGNORECASE):
        prefixo, coluna, literal = m.group(1), m.group(2), m.group(3)
        qualificador = prefixo.removesuffix(".")
        tabela = _alias_para_tabela(sql).get(qualificador or coluna)
        if not tabela:
            continue
        enums = _enums()
        validos = enums.get((tabela, coluna))
        if not validos or any(v.lower() == literal.lower() for v in validos):
            continue
        for v in validos:
            if _distancia1(literal.lower(), v.lower()):
                achados.append((literal, v))
                break
    return achados


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
