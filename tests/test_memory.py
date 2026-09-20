"""Testes da memoria persistente (SQLite): conversas, mensagens e perfil."""

from types import SimpleNamespace

import pytest

from sentinelasoc import memory


@pytest.fixture
def banco(tmp_path, monkeypatch):
    """Redireciona o banco de memoria para um arquivo temporario."""
    alvo = SimpleNamespace(memory_path=tmp_path / "memoria_teste.db")
    monkeypatch.setattr(memory, "get_settings", lambda: alvo)
    return alvo.memory_path


def test_ciclo_de_vida_de_conversa(banco):
    cid = memory.nova_conversa("Incidentes críticos na DMZ")
    conversas = memory.listar_conversas()
    assert len(conversas) == 1
    assert conversas[0]["titulo"] == "Incidentes críticos na DMZ"

    memory.salvar_mensagem(cid, "user", "quantos incidentes criticos?")
    memory.salvar_mensagem(cid, "assistant", "sao 12", trace=[{"tipo": "sql"}])

    msgs = memory.carregar_mensagens(cid)
    assert len(msgs) == 2
    assert msgs[0]["role"] == "user"
    assert msgs[1]["trace"] == [{"tipo": "sql"}]
    assert memory.contar_trocas(cid) == 1

    memory.apagar_conversa(cid)
    assert memory.listar_conversas() == []
    assert memory.carregar_mensagens(cid) == []


def test_titulo_truncado(banco):
    memory.nova_conversa("x" * 200)
    assert len(memory.listar_conversas()[0]["titulo"]) == memory.TITULO_MAX


def test_perfil_deduplica_e_filtra(banco):
    adicionados = memory.atualizar_fatos(
        ["Analista atua na triagem N1", "analista atua na triagem n1.", "ab", ""]
    )
    assert adicionados == 1  # dedup case-insensitive + curtos/vazios descartados
    assert memory.fatos_perfil() == ["Analista atua na triagem N1"]

    assert memory.atualizar_fatos(["Analista atua na triagem N1"]) == 0


def test_perfil_limpar(banco):
    memory.atualizar_fatos(["foco em phishing"])
    memory.limpar_perfil()
    assert memory.fatos_perfil() == []
