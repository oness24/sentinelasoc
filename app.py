"""SentinelaSOC — copiloto de chat para analistas de SOC (interface Streamlit).

Design: sistema Linear (dark-mode nativo, bordas semi-transparentes, empilhamento
de luminancia, um unico acento cromatico). Execucao: streamlit run app.py
"""

import streamlit as st

import sentinelasoc
from sentinelasoc import db, rag
from sentinelasoc.agent import AgenteSOC
from sentinelasoc.settings import get_settings

st.set_page_config(page_title="SentinelaSOC", page_icon="assets/favicon.png", layout="wide")

settings = get_settings()

# ─────────────────────────────────────────────────────────────────────────────
# Design tokens (Linear) — um bloco HTML continuo, sem linhas em branco
# ─────────────────────────────────────────────────────────────────────────────
CSS = """<link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">
<style>
  :root {
    --bg: #08090a; --panel: #0f1011; --surface: #191a1b;
    --surface-2: rgba(255,255,255,.02); --surface-4: rgba(255,255,255,.04);
    --text: #f7f8f8; --text-2: #d0d6e0; --muted: #8a8f98; --faint: #62666d;
    --accent: #10b981; --accent-hi: #34d399;
    --danger: #f0564a; --warn: #f0b429;
    --bd: rgba(255,255,255,.08); --bd-subtle: rgba(255,255,255,.05);
    --mono: 'JetBrains Mono', ui-monospace, SFMono-Regular, Menlo, monospace;
  }
  html, body, .stApp { background: var(--bg); color: var(--text-2);
    font-family: 'Inter', system-ui, -apple-system, 'Segoe UI', sans-serif;
    font-feature-settings: 'cv01', 'ss03'; font-size: 15px; }
  [data-testid="stHeader"] { background: transparent; height: 0; }
  [data-testid="stToolbar"] { display: none; }
  footer { display: none; }
  [data-testid="stStatusWidget"] { display: none; }
  #MainMenu, .stDeployButton { visibility: hidden; }
  .block-container { padding-top: 1.1rem; max-width: 880px; margin: 0 auto; }
  ::-webkit-scrollbar { width: 10px; }
  ::-webkit-scrollbar-thumb { background: rgba(255,255,255,.06); border-radius: 8px; }
  ::selection { background: rgba(16,185,129,.25); }
  .hero { text-align: center; padding: 3.2rem 1rem 1.4rem; }
  .hero .logo { display: inline-block; margin-bottom: .9rem; }
  .hero h1 { font-size: 2.4rem; font-weight: 600; letter-spacing: -1.05px;
    line-height: 1.05; margin: 0 0 .5rem; color: var(--text); }
  .hero h1 span { color: var(--accent); }
  .hero p { color: var(--muted); font-size: .95rem; max-width: 520px;
    margin: 0 auto 1.4rem; line-height: 1.6; }
  .hero .tags { display: flex; gap: .45rem; justify-content: center; flex-wrap: wrap; }
  .tag { font-family: var(--mono); font-size: .68rem; color: var(--text-2);
    border: 1px solid var(--bd); border-radius: 9999px; padding: .26rem .68rem;
    background: var(--surface-2); }
  .topbar { display: flex; align-items: center; justify-content: space-between;
    border-bottom: 1px solid var(--bd-subtle); padding: .6rem 0; margin-bottom: 1.3rem; }
  .topbar .brand { display: flex; align-items: center; gap: .55rem; font-weight: 600;
    letter-spacing: -.01em; color: var(--text); font-size: .95rem; }
  .topbar .brand .dot { width: 7px; height: 7px; border-radius: 50%; background: var(--accent); }
  .topbar .meta { font-family: var(--mono); font-size: .68rem; color: var(--faint); }
  .topbar .meta b { color: var(--muted); font-weight: 500; }
  .quick-h { font-size: .68rem; letter-spacing: .1em; text-transform: uppercase;
    color: var(--faint); font-weight: 500; margin: 0 0 .5rem; }
  .quick button { background: var(--surface-2) !important; color: var(--text-2) !important;
    border: 1px solid var(--bd) !important; border-radius: 6px; padding: .62rem .85rem;
    text-align: left; font-size: .85rem; font-weight: 400;
    transition: background .15s, border-color .15s; font-family: 'Inter', sans-serif; }
  .quick button:hover { background: var(--surface-4) !important;
    border-color: rgba(255,255,255,.14) !important; }
  [data-testid="stChatMessage"] { background: var(--surface-2);
    border: 1px solid var(--bd); border-radius: 8px;
    padding: .8rem 1rem; margin: .35rem 0 .85rem; }
  [data-testid="stChatMessage"] [data-testid="chatAvatarIcon"] {
    font-size: 1.05rem; color: var(--muted); }
  [data-testid="stChatMessage"] p { font-size: .92rem; line-height: 1.65;
    margin-bottom: .5rem; color: var(--text-2); }
  [data-testid="stChatMessage"] strong { color: var(--text); font-weight: 600; }
  .cursor { display: inline-block; color: var(--accent); animation: blink 1s step-start infinite; }
  @keyframes blink { 50% { opacity: 0; } }
  [data-testid="stExpander"] { background: var(--surface-2);
    border: 1px solid var(--bd-subtle); border-radius: 8px; }
  [data-testid="stExpander"] summary { font-family: var(--mono); font-size: .72rem; }
  [data-testid="stExpander"] summary span { color: var(--muted) !important; }
  .trace-head { font-family: var(--mono); font-size: .7rem; color: var(--faint);
    padding: .2rem 0 .4rem; border-bottom: 1px dashed var(--bd-subtle); margin-bottom: .3rem; }
  .trace-head b { color: var(--accent); font-weight: 500; }
  .trace-row { font-family: var(--mono); font-size: .7rem; color: var(--muted);
    padding: .14rem 0; display: flex; gap: .6rem; align-items: baseline; }
  .trace-row .k { color: var(--accent); min-width: 58px; font-weight: 500; }
  .trace-row .k.err { color: var(--danger); }
  .trace-row .k.retry { color: var(--warn); }
  .trace-row .k.tempo { color: var(--faint); }
  .stCodeBlock { border-radius: 6px; }
  code { font-family: var(--mono) !important; }
  [data-testid="stChatInput"] { border-color: var(--bd); }
  [data-testid="stChatInput"] textarea { background: var(--surface-2) !important;
    color: var(--text) !important; font-family: 'Inter', sans-serif;
    border-radius: 6px; border-color: var(--bd); }
  [data-testid="stChatInput"] textarea:focus { border-color: rgba(16,185,129,.45) !important; }
  section[data-testid="stSidebar"] { background: var(--panel);
    border-right: 1px solid var(--bd-subtle); }
  section[data-testid="stSidebar"] * { color: var(--text-2); }
  .side-brand { display: flex; align-items: center; gap: .5rem; font-weight: 600;
    font-size: .98rem; letter-spacing: -.01em; padding: .15rem 0 .1rem; color: var(--text); }
  .side-brand .dot { width: 7px; height: 7px; border-radius: 50%; background: var(--accent); }
  .side-sub { color: var(--faint) !important; font-size: .72rem; font-family: var(--mono); }
  .side-h { font-size: .64rem; letter-spacing: .12em; text-transform: uppercase;
    color: var(--faint) !important; font-weight: 500; margin: 1.25rem 0 .45rem; }
  .side-kv { display: flex; justify-content: space-between; font-size: .8rem;
    padding: .28rem 0; border-bottom: 1px solid var(--bd-subtle); }
  .side-kv .k { color: var(--muted); }
  .side-kv .v { font-family: var(--mono); font-size: .7rem; color: var(--text-2); }
  .side-note { font-size: .72rem; color: var(--faint) !important; line-height: 1.55; margin-top: .7rem; }
  .side-note code { font-size: .68rem; color: var(--muted); }
  div[data-testid="stStatus"] { background: var(--surface);
    border: 1px solid var(--bd); border-radius: 8px;
    font-family: var(--mono); font-size: .72rem; }
  div[data-testid="stAlert"] { border-radius: 8px; }
</style>"""
st.markdown(CSS, unsafe_allow_html=True)

LOGO_SVG = """<svg width="52" height="52" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
<path d="M12 2l8 3v6c0 5-3.4 9.2-8 11-4.6-1.8-8-6-8-11V5l8-3z" stroke="#10b981" stroke-width="1.2" fill="rgba(16,185,129,0.06)"/>
<path d="M8.8 12.2l2.2 2.2 4.2-4.6" stroke="#10b981" stroke-width="1.2" stroke-linecap="round" stroke-linejoin="round"/>
</svg>"""

# ─────────────────────────────────────────────────────────────────────────────
# Estado
# ─────────────────────────────────────────────────────────────────────────────
if "mensagens" not in st.session_state:
    st.session_state.mensagens = []
if "pergunta_pendente" not in st.session_state:
    st.session_state.pergunta_pendente = None


@st.cache_resource(show_spinner=False)
def carregar_camadas() -> AgenteSOC:
    db.conectar()
    rag.get_collection()
    return AgenteSOC()


def _chunks_indexados() -> int | None:
    try:
        return rag.get_collection().count()
    except Exception:
        return None


# ─────────────────────────────────────────────────────────────────────────────
# Sidebar
# ─────────────────────────────────────────────────────────────────────────────
SIDEBAR = f"""
<div class="side-brand"><span class="dot"></span> SentinelaSOC</div>
<div class="side-sub">SOC copilot · v{sentinelasoc.__version__}</div>
<div class="side-h">Runtime</div>
<div class="side-kv"><span class="k">LLM</span><span class="v">{settings.llm_model}</span></div>
<div class="side-kv"><span class="k">Embeddings</span><span class="v">MiniLM-L12</span></div>
<div class="side-kv"><span class="k">Vector store</span><span class="v">ChromaDB</span></div>
<div class="side-kv"><span class="k">Analytics</span><span class="v">DuckDB</span></div>
<div class="side-h">Base de conhecimento</div>
<div class="side-kv"><span class="k">Chunks indexados</span><span class="v">{_chunks_indexados() or "—"}</span></div>
<div class="side-kv"><span class="k">Documentos</span><span class="v">4</span></div>
<div class="side-kv"><span class="k">Tabelas</span><span class="v">3 relacionadas</span></div>
<div class="side-note">Toda resposta traz rastro auditável. Logs estruturados por módulo em <code>logs/sentinelasoc.log</code>, correlacionados pelo <code>request_id</code> exibido no rastro.</div>
<div class="side-note" style="opacity:.7">MIT License · dados sintéticos determinísticos</div>
"""
with st.sidebar:
    st.markdown(SIDEBAR, unsafe_allow_html=True)

# ─────────────────────────────────────────────────────────────────────────────
# Topbar / hero
# ─────────────────────────────────────────────────────────────────────────────
st.markdown(
    f"""
<div class="topbar">
  <div class="brand"><span class="dot"></span> SentinelaSOC</div>
  <div class="meta">llm <b>{settings.llm_model}</b> · local · rag <b>chromadb</b> · sql <b>duckdb</b> · read-only</div>
</div>
""",
    unsafe_allow_html=True,
)

if not st.session_state.mensagens:
    st.markdown(
        LOGO_SVG
        + """
<div class="hero">
  <h1>Sentinela<span>SOC</span></h1>
  <p>Copiloto para analistas de Security Operations. Consulte políticas e procedimentos internos ou pergunte sobre incidentes, ativos e vulnerabilidades em linguagem natural.</p>
  <div class="tags">
    <span class="tag">rag com citação de fonte</span><span class="tag">sql somente-leitura</span>
    <span class="tag">rastro auditável</span><span class="tag">execução local</span>
  </div>
</div>
""",
        unsafe_allow_html=True,
    )

EXEMPLOS = [
    "Qual o SLA de correção para uma CVE com CVSS 9.5 em ativo exposto?",
    "Quantos incidentes críticos estão abertos e em quais ativos?",
    "Como devo responder a um incidente de phishing?",
    "Qual a taxa de falsos positivos por tipo de incidente?",
]

st.markdown('<div class="quick-h">Comece com uma pergunta</div>', unsafe_allow_html=True)
grade = st.columns(2, gap="small")
for i, texto in enumerate(EXEMPLOS):
    if grade[i % 2].button(texto, key=f"ex{i}", use_container_width=True):
        st.session_state.pergunta_pendente = texto

# ─────────────────────────────────────────────────────────────────────────────
# Chave de API
# ─────────────────────────────────────────────────────────────────────────────
if not settings.openai_api_key:
    st.error("**OPENAI_API_KEY não configurada.** Copie `.env.example` para `.env` e reinicie.")
    st.stop()

agente = carregar_camadas()

AVATAR_ASSISTENTE = ":material/security:"
AVATAR_USUARIO = ":material/person:"


# ─────────────────────────────────────────────────────────────────────────────
# Renderizacao
# ─────────────────────────────────────────────────────────────────────────────
def renderizar_trace(trace: list[dict]) -> None:
    rid = next((t["id"] for t in trace if t["tipo"] == "request"), None)
    with st.expander("Rastro da resposta (roteamento · sql · rag · tempos)"):
        if rid:
            st.markdown(
                f"<div class='trace-head'>request <b>{rid}</b> · espelha as linhas "
                f"<b>req={rid}</b> de logs/sentinelasoc.log</div>",
                unsafe_allow_html=True,
            )
        for item in trace:
            if item["tipo"] == "sql":
                st.markdown(
                    f"<div class='trace-row'><span class='k'>sql</span>"
                    f"<span>{item['linhas']} linhas retornadas</span></div>",
                    unsafe_allow_html=True,
                )
                st.code(item["sql"], language="sql")
            elif item["tipo"] == "rag":
                for fonte in item["fontes"]:
                    st.markdown(
                        f"<div class='trace-row'><span class='k'>rag</span><span>{fonte}</span></div>",
                        unsafe_allow_html=True,
                    )
            elif item["tipo"] == "direto":
                st.markdown(
                    f"<div class='trace-row'><span class='k'>rota</span><span>{item['decisao']}</span></div>",
                    unsafe_allow_html=True,
                )
            elif item["tipo"] == "retry":
                st.markdown(
                    f"<div class='trace-row'><span class='k retry'>retry</span>"
                    f"<span>{item['detalhe']}</span></div>",
                    unsafe_allow_html=True,
                )
            elif item["tipo"] == "erro":
                st.markdown(
                    f"<div class='trace-row'><span class='k err'>erro</span>"
                    f"<span>{item['detalhe']}</span></div>",
                    unsafe_allow_html=True,
                )
            elif item["tipo"] == "tempo":
                st.markdown(
                    f"<div class='trace-row'><span class='k tempo'>tempo</span>"
                    f"<span>{item['etapa']}: {item['segundos']}s</span></div>",
                    unsafe_allow_html=True,
                )


def _resumo_status(trace: list[dict]) -> str:
    """Rotulo vivo do pipeline conforme o trace cresce."""
    for item in reversed(trace):
        if item["tipo"] == "sql":
            return f"consultando duckdb… {item['linhas']} linhas"
        if item["tipo"] == "rag":
            return "buscando documentos…"
        if item["tipo"] == "erro":
            return "falha isolada em ferramenta"
    return "roteando pergunta…"


for msg in st.session_state.mensagens:
    avatar = AVATAR_USUARIO if msg["role"] == "user" else AVATAR_ASSISTENTE
    with st.chat_message(msg["role"], avatar=avatar):
        st.markdown(msg["content"], unsafe_allow_html=True)
        if msg["role"] == "assistant" and msg.get("trace"):
            renderizar_trace(msg["trace"])

pergunta = st.chat_input("Pergunte sobre políticas, incidentes, ativos ou vulnerabilidades…")
if st.session_state.pergunta_pendente:
    pergunta = st.session_state.pergunta_pendente
    st.session_state.pergunta_pendente = None

if pergunta:
    st.session_state.mensagens.append({"role": "user", "content": pergunta})
    with st.chat_message("user", avatar=AVATAR_USUARIO):
        st.markdown(pergunta, unsafe_allow_html=True)

    with st.chat_message("assistant", avatar=AVATAR_ASSISTENTE):
        caixa_status = st.status("roteando pergunta…", expanded=False)
        placeholder = st.empty()
        texto = ""
        vistos = 0
        try:
            for chunk in agente.answer(pergunta, st.session_state.mensagens[:-1]):
                texto += chunk
                if len(agente.last_trace) != vistos:
                    vistos = len(agente.last_trace)
                    caixa_status.update(label=_resumo_status(agente.last_trace))
                placeholder.markdown(
                    texto + '<span class="cursor">▌</span>', unsafe_allow_html=True
                )
            caixa_status.update(label="resposta concluída", state="complete", expanded=False)
        except Exception as exc:
            texto = f"Erro ao processar: `{exc}`"
        placeholder.markdown(texto, unsafe_allow_html=True)
        st.session_state.mensagens.append(
            {"role": "assistant", "content": texto, "trace": agente.last_trace}
        )
        renderizar_trace(agente.last_trace)
