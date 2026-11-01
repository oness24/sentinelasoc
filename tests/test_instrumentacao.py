"""Testes da instrumentacao: diario de chamadas LLM em SQLite (Langfuse-equivalente)."""

from types import SimpleNamespace

import pytest

from sentinelasoc import instrumentacao


@pytest.fixture
def banco(tmp_path, monkeypatch):
    """Redireciona o diario para um arquivo temporario."""
    alvo = SimpleNamespace(memory_path=tmp_path / "instrumentacao_teste.db")
    monkeypatch.setattr(instrumentacao, "get_settings", lambda: alvo)
    return alvo.memory_path


def test_registra_e_resume(banco):
    instrumentacao.registrar_chamada(
        modelo="qwen2.5:7b",
        duracao_ms=812.4,
        sucesso=True,
        agente="triador",
        etapa="roteamento",
        request_id="ab12",
        prompt_tokens=120,
        completion_tokens=45,
    )
    instrumentacao.registrar_chamada(
        modelo="qwen2.5:7b", duracao_ms=2400.0, sucesso=False, erro="OpenAIError: boom"
    )

    resumo = instrumentacao.resumo()
    assert resumo["chamadas"] == 2
    assert resumo["requests"] == 2
    assert resumo["ok"] == 1
    assert resumo["falhas"] == 1
    assert resumo["latencia_max"] >= resumo["latencia_media"] > 0
    assert resumo["prompt_tokens"] == 120


def test_por_etapa_agrupa_agente_e_etapa(banco):
    for _ in range(2):
        instrumentacao.registrar_chamada(
            modelo="m", duracao_ms=100.0, sucesso=True, agente="triador", etapa="sql"
        )
    instrumentacao.registrar_chamada(
        modelo="m", duracao_ms=500.0, sucesso=True, agente="redator", etapa="redacao"
    )
    etapas = {(e["agente"], e["etapa"]): e for e in instrumentacao.por_etapa()}
    assert etapas[("triador", "sql")]["chamadas"] == 2
    assert etapas[("redator", "redacao")]["chamadas"] == 1


def test_ultimas_e_por_request(banco):
    instrumentacao.registrar_chamada(
        modelo="m",
        duracao_ms=10.0,
        sucesso=True,
        agente="triador",
        etapa="roteamento",
        request_id="r1",
    )
    instrumentacao.registrar_chamada(
        modelo="m",
        duracao_ms=10.0,
        sucesso=True,
        agente="redator",
        etapa="redacao",
        request_id="r1",
    )
    instrumentacao.registrar_chamada(
        modelo="m",
        duracao_ms=10.0,
        sucesso=True,
        agente="sistema",
        etapa="memoria_facts",
        request_id="r2",
    )
    do_r1 = instrumentacao.por_request("r1")
    assert [c["etapa"] for c in do_r1] == ["roteamento", "redacao"]
    ultimas = instrumentacao.ultimas(2)
    assert len(ultimas) == 2
    assert ultimas[0]["request_id"] == "r2"  # mais recente primeiro


def test_contexto_llm_rotula_agente_e_etapa(banco):
    with instrumentacao.contexto_llm(agente="triador", etapa="roteamento"):
        assert instrumentacao.contexto_corrente() == ("triador", "roteamento")
        instrumentacao.registrar_chamada(modelo="m", duracao_ms=5.0, sucesso=True)
        with instrumentacao.contexto_llm(agente="redator", etapa="redacao"):
            assert instrumentacao.contexto_corrente() == ("redator", "redacao")
        assert instrumentacao.contexto_corrente() == ("triador", "roteamento")
    assert instrumentacao.contexto_corrente() == ("sistema", "llm")
    ultima = instrumentacao.ultimas(1)[0]
    assert (ultima["agente"], ultima["etapa"]) == ("triador", "roteamento")


def test_falha_de_gravacao_nao_propaga(tmp_path, monkeypatch):
    """Diario e observabilidade: erro de gravacao nunca derruba a resposta."""
    alvo = SimpleNamespace(memory_path=tmp_path / "dir" / "nao" / "existe.db")
    monkeypatch.setattr(instrumentacao, "get_settings", lambda: alvo)
    # nao explode; apenas registra warning no log
    instrumentacao.registrar_chamada(modelo="m", duracao_ms=1.0, sucesso=True)
    assert instrumentacao.resumo()["chamadas"] == 0


def test_diario_isolado_da_memoria(banco):
    """O diario vive no mesmo arquivo SQLite da memoria, em tabela propria."""
    import sqlite3

    instrumentacao.registrar_chamada(
        modelo="m", duracao_ms=1.0, sucesso=True, agente="triador", etapa="sql"
    )
    con = sqlite3.connect(str(banco))
    try:
        tabelas = {r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        assert "llm_chamadas" in tabelas
        assert "conversas" not in tabelas  # criada apenas por memory.py
    finally:
        con.close()
