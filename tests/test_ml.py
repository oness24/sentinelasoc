"""Testes da camada de ML: treinamento deterministico, previsao e ferramenta do agente."""

import json

from conftest import FakeLLM, rota_consultar
from sentinelasoc import ml
from sentinelasoc.agent import _RE_PREVISAO_FP, AgenteSOC, _executar_ml

_LINHAS = [
    {
        "incidente_id": "T-1",
        "tipo": "Engenharia Social",
        "severidade": "Baixa",
        "tatica_mitre": "T1598 - Phishing for Information",
        "ambiente": "DMZ",
        "criticidade": "Media",
        "sistema_operacional": "Windows Server 2022",
        "exposto_internet": "Sim",
    },
    {
        "incidente_id": "T-2",
        "tipo": "Malware",
        "severidade": "Critica",
        "tatica_mitre": "T1203 - Exploit Public-Facing Application",
        "ambiente": "Producao",
        "criticidade": "Alta",
        "sistema_operacional": "Ubuntu 22.04",
        "exposto_internet": "Nao",
    },
]


def test_treinar_fp_e_deterministico():
    """Mesma seed, mesmos numeros — treino reproducivel em duas execucoes."""
    m1 = ml.treinar_fp(persistir=False)
    m2 = ml.treinar_fp(persistir=False)
    assert m1 == m2
    assert m1["n_total"] == 356
    # metricas coerentes com o problema ruidoso: abaixo do teto de Bayes
    assert float(m1["acuracia"]) <= float(m1["teto_bayes_acuracia"])
    assert 50.0 < float(m1["auc"]) <= float(m1["teto_bayes_auc"])


def test_prever_fp_ordenado_e_em_intervalo_valido():
    previsoes = ml.prever_falso_positivo(_LINHAS)
    assert [p["incidente_id"] for p in previsoes] == ["T-1", "T-2"]  # Baixa antes de Critica
    for p in previsoes:
        assert 0.0 <= p["probabilidade_fp"] <= 1.0
        assert 0.5 <= p["confianca"] <= 1.0
        assert p["classe_prevista"] in ("falso positivo", "incidente real")
    # severidade Baixa deve ter probabilidade maior que Critica (sinal dominante)
    assert previsoes[0]["probabilidade_fp"] > previsoes[1]["probabilidade_fp"]


def test_prever_fp_tolerante_a_categorias_desconhecidas():
    """Incidentes de tipo/ambiente ineditos nao derrubam a previsao."""
    estranho = [
        {
            "incidente_id": "T-9",
            "tipo": "Tipo Novo",
            "severidade": "Media",
            "tatica_mitre": "T9999",
            "ambiente": "Staging",
            "criticidade": "Baixa",
            "sistema_operacional": "Container",
            "exposto_internet": "Nao",
        }
    ]
    previsoes = ml.prever_falso_positivo(estranho)
    assert len(previsoes) == 1
    assert 0.0 <= previsoes[0]["probabilidade_fp"] <= 1.0


def test_ferramenta_ml_filtra_e_registra_trace():
    trace: list[dict] = []
    contexto = _executar_ml(
        "probabilidade de falso positivo em incidentes de Engenharia Social severidade Baixa", trace
    )
    evento = next(t for t in trace if t["tipo"] == "ml")
    assert evento["incidentes"] > 0
    assert evento["prob_media"] is not None
    assert "tipo" in evento["filtro"] and "severidade" in evento["filtro"]
    assert "Previsão do modelo de ML" in contexto
    assert "PRIORIZAR" in contexto  # guardrail de interpretacao sempre presente


def test_ferramenta_ml_sem_correspondencia_avisa():
    """Filtros contraditorios (tipo x tatica que nunca coexistem) avisam, sem inventar."""
    trace: list[dict] = []
    contexto = _executar_ml(
        "probabilidade de falso positivo em incidentes de Malware "
        "com tatica T1598 - Phishing for Information",
        trace,
    )
    assert "nenhum incidente historico" in contexto
    evento = next(t for t in trace if t["tipo"] == "ml")
    assert evento["incidentes"] == 0


def test_ferramenta_ml_sem_valor_conhecido_avalia_tudo():
    """Termo que nao casa nenhum valor real do esquema: avalia todos os incidentes."""
    trace: list[dict] = []
    contexto = _executar_ml("probabilidade de falso positivo em ataques quanticos", trace)
    assert "todos os incidentes" in contexto


def test_rota_ml_no_agente_alimenta_resposta_final():
    llm = FakeLLM(
        complete_responses=[
            rota_consultar([{"tipo": "ml", "consulta": "incidentes de Engenharia Social"}]),
        ],
        stream_chunks=["Segundo o modelo, ", "revisar primeiro os de severidade Baixa."],
    )
    agente = AgenteSOC(llm=llm)
    saida = "".join(agente.answer("qual a probabilidade de falso positivo em phishing?"))
    assert "severidade Baixa" in saida
    tipos = [t["tipo"] for t in agente.last_trace]
    assert "ml" in tipos
    # o contexto ML efetivamente chegou ao prompt final
    prompt_final = llm.stream_calls[0][-1]["content"]
    assert "Previsão do modelo de ML" in prompt_final


def test_guarda_de_domínio_forca_ml_quando_roteador_falha():
    """Roteador insistindo em 'direto' em pergunta de previsao: guarda forca ML."""
    llm = FakeLLM(
        complete_responses=[
            json.dumps({"acao": "direto", "resposta": "nao sei"}),
            json.dumps({"acao": "direto", "resposta": "nao sei"}),
        ],
        stream_chunks=["Resposta com contexto ML."],
    )
    agente = AgenteSOC(llm=llm)
    saida = "".join(agente.answer("qual a chance de estes incidentes serem falso positivo?"))
    assert saida
    decisoes = [t for t in agente.last_trace if t["tipo"] == "direto"]
    assert any("ML" in d["decisao"] for d in decisoes)
    assert "ml" in [t["tipo"] for t in agente.last_trace]


def test_regex_previsao_discrimina_fato_de_modo():
    previsao = [
        "qual a probabilidade de falso positivo?",
        "quais incidentes podem ser falso positivo?",
        "me dá a chance de falso positivo dos alerts de phishing",
        "priorize os falsos positivos mais prováveis",
    ]
    fato = [
        "quantos falsos positivos tivemos?",
        "liste os incidentes que são falsos positivos",
        "qual o total de incidentes?",
    ]
    for frase in previsao:
        assert _RE_PREVISAO_FP.search(frase), frase
    for frase in fato:
        assert not _RE_PREVISAO_FP.search(frase), frase
