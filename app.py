"""SentinelaSOC — copiloto de chat para analistas de SOC (interface Streamlit).

Execucao: streamlit run app.py
"""

import streamlit as st

import sentinelasoc
from sentinelasoc import db, rag
from sentinelasoc.agent import AgenteSOC
from sentinelasoc.settings import get_settings

st.set_page_config(page_title="SentinelaSOC", page_icon="🛡️", layout="centered")

settings = get_settings()

# ---------- Estado da sessao ----------
if "mensagens" not in st.session_state:
    st.session_state.mensagens = []
if "pergunta_pendente" not in st.session_state:
    st.session_state.pergunta_pendente = None


@st.cache_resource(show_spinner="Inicializando camadas do SentinelaSOC...")
def carregar_camadas() -> AgenteSOC:
    db.conectar()  # garante o DuckDB criado a partir dos CSVs
    rag.get_collection()  # aquece o modelo de embeddings + ChromaDB
    return AgenteSOC()


# ---------- Barra lateral ----------
with st.sidebar:
    st.title("🛡️ SentinelaSOC")
    st.caption(f"AI copilot for Security Operations Centers — v{sentinelasoc.__version__}")
    st.divider()

    st.markdown(
        """
        **Camadas de inteligência**

        💬 Chat com streaming de tokens

        📚 **RAG** — ChromaDB + embeddings multilingues
        sobre 4 documentos internos (política, playbook,
        FAQ e guia de vulnerabilidades)

        🗄️ **Dados** — DuckDB com 3 tabelas relacionadas
        (ativos, incidentes, vulnerabilidades)

        🔐 Segredos via `.env` — nada hardcoded
        """
    )
    st.divider()

    try:
        colecao = rag.get_collection()
        st.markdown(
            f"""
            **Status do sistema**

            Modelo LLM: `{settings.llm_model}`

            Embeddings: `{settings.embed_model}`

            Chunks indexados: `{colecao.count()}`

            Tabelas: ativos · incidentes · vulnerabilidades
            """
        )
    except Exception:
        st.warning("Camada RAG ainda não inicializada. Execute `python ingest.py`.")

    st.divider()
    st.caption("MIT License · Streamlit · DuckDB · ChromaDB")

# ---------- Cabeçalho ----------
st.title("🛡️ SentinelaSOC — Copiloto do SOC")
st.caption(
    "Pergunte sobre políticas e procedimentos (RAG) ou consulte incidentes, ativos e "
    "vulnerabilidades em linguagem natural (SQL sobre DuckDB)."
)

# ---------- Perguntas de exemplo ----------
st.markdown("")
exemplos = [
    "📚 Qual o SLA de correção para uma CVE com CVSS 9.5 em ativo exposto?",
    "📊 Quantos incidentes críticos estão abertos agora e em quais ativos?",
    "📚 Como devo responder a um incidente de phishing?",
    "📊 Qual a taxa de falsos positivos por tipo de incidente?",
]
grade = st.columns(2)
for i, texto in enumerate(exemplos):
    if grade[i % 2].button(texto, key=f"ex{i}", use_container_width=True):
        st.session_state.pergunta_pendente = texto

st.markdown("---")

# ---------- Verificacao de chave ----------
if not settings.openai_api_key:
    st.error(
        "**OPENAI_API_KEY não configurada.** Copie `.env.example` para `.env`, "
        "informe sua chave e reinicie a aplicação."
    )
    st.stop()

agente = carregar_camadas()


def renderizar_trace(trace: list[dict]) -> None:
    """Painel de rastreabilidade: ferramentas usadas na resposta."""
    with st.expander("🔍 Rastro da resposta (ferramentas RAG/SQL)"):
        for item in trace:
            if item["tipo"] == "sql":
                st.markdown(f"**SQL gerado** ({item['linhas']} linhas):")
                st.code(item["sql"], language="sql")
            elif item["tipo"] == "rag":
                st.markdown("**Documentos recuperados:**")
                for fonte in item["fontes"]:
                    st.markdown(f"- {fonte}")
            elif item["tipo"] == "direto":
                st.markdown(f"**Decisão:** {item['decisao']}")
            elif item["tipo"] == "tempo":
                st.markdown(f"⏱️ {item['etapa']}: {item['segundos']}s")
            elif item["tipo"] == "erro":
                st.warning(f"Falha: {item['detalhe']}")


# ---------- Historico ----------
for msg in st.session_state.mensagens:
    with st.chat_message(msg["role"], avatar="🧑‍💻" if msg["role"] == "user" else "🛡️"):
        st.markdown(msg["content"])
        if msg["role"] == "assistant" and msg.get("trace"):
            renderizar_trace(msg["trace"])

# ---------- Entrada ----------
pergunta = st.chat_input("Faça sua pergunta ao SentinelaSOC...")
if st.session_state.pergunta_pendente:
    pergunta = st.session_state.pergunta_pendente
    st.session_state.pergunta_pendente = None

if pergunta:
    st.session_state.mensagens.append({"role": "user", "content": pergunta})
    with st.chat_message("user", avatar="🧑‍💻"):
        st.markdown(pergunta)

    with st.chat_message("assistant", avatar="🛡️"):
        try:
            resposta = st.write_stream(agente.answer(pergunta, st.session_state.mensagens[:-1]))
        except Exception as exc:
            resposta = f"⚠️ Erro ao processar: `{exc}`"
            st.error(resposta)
        st.session_state.mensagens.append(
            {"role": "assistant", "content": resposta, "trace": agente.last_trace}
        )
        renderizar_trace(agente.last_trace)
