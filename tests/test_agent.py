"""Testes unitarios do agente: roteamento, ferramentas e resiliencia (sem rede)."""

import json

import pytest

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


def _resp_sql(sql: str) -> str:
    return json.dumps({"sql": sql})


def test_sql_autocorrige_coluna_inexistente():
    """1a geracao referencia coluna errada; o agente devolve o erro ao LLM e regenera."""
    llm = FakeLLM(
        complete_responses=[
            rota_consultar([{"tipo": "sql", "pergunta": "tempo medio de resolucao"}]),
            _resp_sql(
                "SELECT ROUND(AVG(hours_to_resolve),1) AS media FROM incidentes "
                "WHERE status='Resolvido'"
            ),
            _resp_sql(
                "SELECT ROUND(AVG(horas_para_resolver),1) AS media FROM incidentes "
                "WHERE status='Resolvido'"
            ),
        ],
        stream_chunks=["Media calculada."],
    )
    agente = AgenteSOC(llm=llm)
    saida = "".join(agente.answer("qual o tempo medio de resolucao dos incidentes?"))
    assert "Media calculada" in saida
    sql_ok = [t for t in agente.last_trace if t["tipo"] == "sql"]
    assert len(sql_ok) == 1 and sql_ok[0]["linhas"] == 1
    autocorr = [
        t for t in agente.last_trace if t["tipo"] == "direto" and "autocorrigido" in t["decisao"]
    ]
    assert autocorr, "deveria registrar a autocorrecao no trace"
    retries = [t for t in agente.last_trace if t["tipo"] == "retry"]
    assert retries, "a tentativa falha deveria ficar no rastro como retry"
    erros_finais = [t for t in agente.last_trace if t["tipo"] == "erro"]
    assert not erros_finais  # nenhum erro terminal: a autocorrecao resolveu


def test_seguimento_e_reformulado_em_sql():
    """Follow-up 'e so os do Financeiro?' e reformulado antes de gerar SQL."""
    llm = FakeLLM(
        complete_responses=[
            json.dumps(
                {
                    "pergunta_independente": (
                        "Quantos incidentes criticos abertos no departamento Financeiro?"
                    )
                },
                ensure_ascii=False,
            ),
            rota_consultar([{"tipo": "sql", "pergunta": "incidentes criticos do Financeiro"}]),
            _resp_sql(
                "SELECT COUNT(*) AS total FROM incidentes i JOIN ativos a USING (ativo_id) "
                "WHERE i.severidade = 'Critica' AND i.status = 'Aberto' "
                "AND a.departamento = 'Financeiro'"
            ),
        ],
        stream_chunks=["Existem 3 no Financeiro."],
    )
    agente = AgenteSOC(llm=llm)
    history = [
        {"role": "user", "content": "quantos incidentes criticos estao abertos?"},
        {"role": "assistant", "content": "sao 14 no total"},
    ]
    saida = "".join(agente.answer("e so os do Financeiro?", history))
    assert "3 no Financeiro" in saida
    ctx = [t for t in agente.last_trace if t["tipo"] == "contexto"]
    assert ctx and "Financeiro" in ctx[0]["reescrita"]
    # o SQL final filtra pelo departamento reformulado
    sql_trace = next(t for t in agente.last_trace if t["tipo"] == "sql")
    assert "Financeiro" in sql_trace["sql"]


def test_perfil_do_analista_injetado_na_resposta():
    llm = FakeLLM(
        complete_responses=[rota_consultar([{"tipo": "rag", "consulta": "politica de senhas"}])],
        stream_chunks=["Resposta com perfil."],
    )
    agente = AgenteSOC(llm=llm)
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(
            "sentinelasoc.agent.rag.retrieve",
            lambda q, k=None: [],
        )
        saida = "".join(
            agente.answer("regras de senha?", perfil=["Analista prefere respostas curtas"])
        )
    assert saida == "Resposta com perfil."
    system_msg = llm.stream_calls[0][0]["content"]
    assert "Analista prefere respostas curtas" in system_msg


def test_extrair_fatos_parseia_e_falha_graciosamente():
    llm = FakeLLM(
        complete_responses=[json.dumps({"fatos": ["Atua na triagem N1", ""]}, ensure_ascii=False)]
    )
    agente = AgenteSOC(llm=llm)
    assert agente.extrair_fatos("pergunta", "resposta") == ["Atua na triagem N1"]

    llm_ruim = FakeLLM(complete_responses=["sem json"])
    agente_ruim = AgenteSOC(llm=llm_ruim)
    assert agente_ruim.extrair_fatos("p", "r") == []


def test_rota_invalida_degrada_com_erro_rastreavel():
    llm = FakeLLM(
        complete_responses=["resposta completamente fora de formato"],
        stream_chunks=["Fallback."],
    )
    agente = AgenteSOC(llm=llm)
    saida = "".join(agente.answer("pergunta qualquer"))
    assert saida  # nao explode; a UI trata o erro
