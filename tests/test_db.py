"""Testes da camada DuckDB: integridade dos dados e guarda somente-leitura."""

import pytest

from sentinelasoc.db import SQLBloqueadoError, conectar, run_select, validar_sql


@pytest.fixture(scope="module", autouse=True)
def _banco_pronto():
    conectar(refresh=True)  # recria a partir dos CSVs para o estado ser conhecido
    yield


def test_tabelas_populadas():
    con = conectar()
    try:
        assert con.execute("SELECT COUNT(*) FROM ativos").fetchone()[0] == 40
        assert con.execute("SELECT COUNT(*) FROM incidentes").fetchone()[0] == 356
        assert con.execute("SELECT COUNT(*) FROM vulnerabilidades").fetchone()[0] == 118
    finally:
        con.close()


def test_integridade_referencial():
    """Nenhum incidente/vulnerabilidade aponta para ativo inexistente."""
    con = conectar()
    try:
        orfas_incidentes = con.execute(
            "SELECT COUNT(*) FROM incidentes i LEFT JOIN ativos a USING (ativo_id) "
            "WHERE a.ativo_id IS NULL"
        ).fetchone()[0]
        orfas_vulns = con.execute(
            "SELECT COUNT(*) FROM vulnerabilidades v LEFT JOIN ativos a USING (ativo_id) "
            "WHERE a.ativo_id IS NULL"
        ).fetchone()[0]
        assert orfas_incidentes == 0
        assert orfas_vulns == 0
    finally:
        con.close()


def test_join_funciona():
    colunas, linhas = run_select(
        "SELECT a.hostname, COUNT(*) AS total FROM incidentes i "
        "JOIN ativos a ON a.ativo_id = i.ativo_id GROUP BY a.hostname ORDER BY total DESC"
    )
    assert linhas and "hostname" in colunas


@pytest.mark.parametrize(
    "sql",
    [
        "DELETE FROM incidentes",
        "DROP TABLE ativos",
        "UPDATE ativos SET criticidade = 'Baixa'",
        "INSERT INTO ativos VALUES ('x')",
        "SELECT 1; DROP TABLE ativos",
        "CREATE TABLE t AS SELECT 1",
        "COPY incidentes TO '/tmp/x.csv'",
        "ATTACH 'outro.db' AS o",
        "VAMOS SELECIONAR TUDO",  # nao comeca com SELECT
    ],
)
def test_guarda_bloqueia_escritas(sql):
    with pytest.raises(SQLBloqueadoError):
        validar_sql(sql)


def test_guarda_aceita_leituras():
    assert validar_sql("SELECT COUNT(*) FROM incidentes;").startswith("SELECT")
    assert validar_sql("  with x as (select 1) select * from x  ").startswith("with")
