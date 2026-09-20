"""Testes unitarios do agente: roteamento, ferramentas e resiliencia (sem rede)."""

import json

from conftest import FakeLLM, rota_consultar
from sentinelasoc.agent import AgenteSOC, extrair_json


def test_extrair_json_com_texto_ao_redor():
    texto = 'Claro! Aqui vai: {"acao": "direto", "resposta": "oi"}\nQualquer coisa.'
    assert extrair_json(texto)["acao"] == "direto"


def test_extrair_json_invalido_levanta_erro():
    import pytest

    with pytest.raises(ValueError):
        extrair_json("sem json aqui")


def test_rota_direto_nao_usa_ferramentas():
    llm = FakeLLM(complete_responses=[json.dumps({"acao": "direto", "resposta": "Ola, analista!"})])
    agente = AgenteSOC(llm=llm)
    saida = list(agente.answer("oi"))
    assert saida == ["Ola, analista!"]
    decisoes = [t for t in agente.last_trace if t["tipo"] == "direto"]
    assert decisoes and "sem ferramentas" in decisoes[0]["decisao"]
    # apenas 1 chamada de LLM (roteamento); nenhuma de ferramenta/resposta
    assert len(llm.complete_calls) == 1
    assert len(llm.stream_calls) == 0


def test_rota_sql_executa_consulta():
    llm = FakeLLM(
        complete_responses=[
            rota_consultar([{"tipo": "sql", "pergunta": "total de incidentes"}]),
            json.dumps({"sql": "SELECT COUNT(*) AS total FROM incidentes"}),
        ],
        stream_chunks=["Existem ", "356 incidentes."],
    )
    agente = AgenteSOC(llm=llm)
    saida = "".join(agente.answer("quantos incidentes existem?"))
    assert "356" in saida
    tipos = [t["tipo"] for t in agente.last_trace]
    assert "sql" in tipos
    sql_trace = next(t for t in agente.last_trace if t["tipo"] == "sql")
    assert sql_trace["linhas"] == 1


def test_rota_sql_malicioso_e_bloqueado_mas_responde():
    """SQL de escrita gerado pelo LLM e bloqueado; a resposta ainda e produzida."""
    llm = FakeLLM(
        complete_responses=[
            rota_consultar([{"tipo": "sql", "pergunta": "apagar tudo"}]),
            json.dumps({"sql": "DELETE FROM incidentes"}),
        ],
        stream_chunks=["Nao posso executar isso."],
    )
    agente = AgenteSOC(llm=llm)
    saida = "".join(agente.answer("apague os incidentes"))
    assert "Nao posso" in saida
    erros = [t for t in agente.last_trace if t["tipo"] == "erro"]
    assert erros and erros[0]["detalhe"].startswith("sql:")


def test_rota_rag_usa_recuperacao(monkeypatch):
    from sentinelasoc import agent as mod_agent

    def retrieve_fake(query, k=None):
        return [
            {
                "chunk_id": "politica::001",
                "texto": "Senhas devem ter 12 caracteres.",
                "fonte": "politica_de_seguranca.md",
                "secao": "3. Politica de Senhas",
                "distancia": 0.12,
            }
        ]

    monkeypatch.setattr(mod_agent.rag, "retrieve", retrieve_fake)
    llm = FakeLLM(
        complete_responses=[rota_consultar([{"tipo": "rag", "consulta": "politica de senhas"}])],
        stream_chunks=["Segundo a politica: 12 caracteres."],
    )
    agente = AgenteSOC(llm=llm)
    saida = "".join(agente.answer("quantos caracteres deve ter uma senha?"))
    assert "12 caracteres" in saida
    rag_trace = next(t for t in agente.last_trace if t["tipo"] == "rag")
    assert "politica_de_seguranca.md" in rag_trace["fontes"][0]


def test_rota_invalida_degrada_com_erro_rastreavel():
    llm = FakeLLM(
        complete_responses=["resposta completamente fora de formato"],
        stream_chunks=["Fallback."],
    )
    agente = AgenteSOC(llm=llm)
    saida = "".join(agente.answer("pergunta qualquer"))
    assert saida  # nao explode; a UI trata o erro
