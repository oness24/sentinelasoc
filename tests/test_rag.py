"""Testes de integracao da camada RAG (carregam modelo de embeddings + indice).

Execucao: pytest -m integration   (requer `python ingest.py` previamente)
"""

import pytest

from sentinelasoc.rag import get_collection, retrieve

CASOS = [
    (
        "qual o prazo para comunicar a ANPD em incidente com dados pessoais?",
        "playbook_resposta_incidentes.md",
    ),
    ("quantos caracteres deve ter uma senha?", "politica_de_seguranca.md"),
    ("qual o primeiro passo ao receber um alerta?", "faq_triagem.md"),
    ("qual o SLA para corrigir vulnerabilidade critica?", "guia_gestao_vulnerabilidades.md"),
    ("como responder a um incidente de ransomware", "playbook_resposta_incidentes.md"),
    ("posso usar pen drive na empresa?", "politica_de_seguranca.md"),
    ("quem valida excecao de SLA de correcao?", "guia_gestao_vulnerabilidades.md"),
    ("o que fazer se phishing sem clique?", "playbook_resposta_incidentes.md"),
]


@pytest.mark.integration
def test_colecao_populada():
    assert get_collection().count() >= 40


@pytest.mark.integration
@pytest.mark.parametrize(
    "consulta,doc_esperado",
    [
        ("como responder a um incidente com a tecnica T1110?", "playbook_resposta_incidentes.md"),
        ("playbook para o indicador T1041", "playbook_resposta_incidentes.md"),
        ("o que e KEV na priorizacao de correcao?", "guia_gestao_vulnerabilidades.md"),
        ("Resolucao CD/ANPD 15/2024", "playbook_resposta_incidentes.md"),
    ],
)
def test_hibrido_acerta_identificadores_exatos(consulta, doc_esperado):
    """Identificadores exatos (T1110, KEV, 15/2024) sao forca do BM25 na fusao."""
    chunks = retrieve(consulta, k=3)
    fontes = [c["fonte"] for c in chunks]
    assert doc_esperado in fontes, f"{doc_esperado} ausente de {fontes}"
    assert chunks[0]["texto"], "chunks hibridos devem trazer o texto do documento"
