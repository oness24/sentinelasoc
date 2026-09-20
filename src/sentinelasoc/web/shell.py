"""Shell da interface: design system, app bar e navegacao.

Identidade derivada do sistema Sentry (data-dense dark): canvas roxo-preto quente
(nunca cinza neutro), bordas roxas, acento lima como cor de sinal, rotulos micro
em caixa alta com letter-spacing, botoes tateis com sombra interna e densidade de
ferramenta profissional. Fontes auto-hospedadas (base64) — sem CDN.
"""

import streamlit as st

import sentinelasoc
from sentinelasoc.settings import get_settings

NAV = [
    ("copiloto", "Copiloto", ""),
    ("painel", "Painel", ""),
    ("memoria", "Memória", ""),
]


CSS = """
<style>
:root {
  --canvas: #060409;
  --deep: #140f22;
  --surface-1: rgba(139,116,255,.045);
  --surface-2: rgba(139,116,255,.08);
  --surface-3: rgba(139,116,255,.13);
  --violeta: #2b2050;
  --violeta-forte: #422082;
  --bd: #332a52;
  --bd-strong: #4a3d73;
  --text: #f4f2fa;
  --text-2: #a79fc2;
  --text-3: #6e6591;
  --roxo: #8b7dfb;
  --roxo-hover: #a89bff;
  --lima: #c2ef4e;
  --coral: #ffb287;
  --rosa: #fa7faa;
  --azul: #7cb7ff;
  --mono: 'JetBrains Mono', ui-monospace, Menlo, Consolas, monospace;
  --ui: 'Rubik', system-ui, -apple-system, 'Segoe UI', sans-serif;
}
html, body, .stApp, .main, [class*="css"] {
  color: var(--text);
  font-family: var(--ui); letter-spacing: -0.005em;
}
/* Fundo Quimera: flare dourado sobre negro — camada fixa ATRAS de tudo
   (body::before com z-index -9999: nenhum container do Streamlit pinta por cima). */
body::before {
  content: "";
  position: fixed;
  inset: 0;
  z-index: -9999;
  pointer-events: none;
  background:
    radial-gradient(90px 90px at 63% 56%, rgba(255, 214, 80, .38), transparent 70%),
    radial-gradient(340px 280px at 62% 55%, rgba(245, 186, 20, .17), transparent 65%),
    radial-gradient(950px 720px at 62% 52%, rgba(176, 131, 8, .10), transparent 62%),
    #060409;
}
html, body { background: #060409 !important; }
body, .stApp, .main, [class*="css"], [data-testid="stHeader"], header { background: transparent !important; }
section[data-testid="stSidebar"] { background: #0c0813 !important; }
#MainMenu, footer, div[data-testid="stToolbar"] {visibility: hidden; height: 0;}

/* ── App bar ─────────────────────────────────────────── */
.appbar {
  display: flex; align-items: center; gap: 14px; height: 50px;
  padding: 0 6px 0 22px; margin: -1rem -1.2rem 1.1rem -1.2rem;
  border-bottom: 1px solid var(--bd); background: var(--deep);
}
.appbar .brand {display: flex; align-items: center; gap: 10px; font-weight: 600; font-size: 14px;}
.appbar .crumb {color: var(--text-3); font-size: 12.5px;}
.appbar .crumb b {color: var(--text-2); font-weight: 500;}
.appbar .spacer {flex: 1;}
.pill {
  display: inline-flex; align-items: center; gap: 6px;
  font-family: var(--mono); font-size: 10.5px; letter-spacing: .06em;
  color: var(--text-2); border: 1px solid var(--bd); border-radius: 6px;
  padding: 3px 9px; background: var(--surface-1); text-transform: uppercase;
}
.pill .dot {width: 6px; height: 6px; border-radius: 50%; background: var(--lima);}
.pill b {color: var(--text); font-weight: 500;}

/* ── Rotulos micro (sistema caixa alta) ──────────────── */
.microlabel {
  font-family: var(--ui); font-size: 10px; font-weight: 600;
  letter-spacing: .14em; text-transform: uppercase; color: var(--text-3);
}

/* ── Sidebar ─────────────────────────────────────────── */
section[data-testid="stSidebar"] {background: var(--deep); border-right: 1px solid var(--bd);}
section[data-testid="stSidebar"] .block-container {padding-top: 1.1rem;}
.side-h {margin: 20px 0 7px 2px;}
section[data-testid="stSidebar"] [data-testid="stButton"] button {
  background: transparent; color: var(--text-2);
  border: 1px solid transparent; border-radius: 7px; padding: 6px 10px;
  font-family: var(--ui); font-size: 11.5px; font-weight: 600;
  letter-spacing: .08em; text-transform: uppercase; text-align: left; width: 100%;
  box-shadow: none;
}
section[data-testid="stSidebar"] [data-testid="stButton"] button:hover {
  background: var(--surface-2); border-color: var(--bd); color: var(--text);
}
section[data-testid="stSidebar"] [data-testid="stButton"] button[kind="primary"] {
  background: var(--violeta); border-color: var(--bd-strong); color: var(--text);
  box-shadow: rgba(0,0,0,.28) 0px 1px 3px 0px inset;
}
section[data-testid="stSidebar"] [data-testid="stButton"] button[kind="primary"]:hover {
  background: var(--violeta-forte);
}
section[data-testid="stSidebar"] [data-testid="stButton"] button[kind="secondary"]:not(:hover) {
  padding-left: 16px; border-left: 2px solid transparent;
}
.side-kv {display: flex; justify-content: space-between; align-items: baseline;
  font-size: 12px; padding: 3px 2px;}
.side-kv .k {color: var(--text-3); font-size: 11.5px;}
.side-kv .v {font-family: var(--mono); font-size: 11px; color: var(--text-2);}
.side-note {font-size: 11px; color: var(--text-3); line-height: 1.65; margin-top: 10px;}
.fact {font-size: 12px; color: var(--text-2); padding: 5px 0 5px 11px;
  border-left: 2px solid var(--bd-strong); line-height: 1.5; margin-bottom: 5px;}

/* ── Botoes globais (tateis, inset) ──────────────────── */
.stButton > button {
  background: var(--violeta); color: var(--text);
  border: 1px solid var(--bd-strong); border-radius: 8px; padding: 6px 14px;
  font-family: var(--ui); font-size: 12px; font-weight: 600;
  letter-spacing: .04em; box-shadow: rgba(0,0,0,.24) 0px 1px 3px 0px inset;
  transition: background .12s ease;
}
.stButton > button:hover {background: var(--violeta-forte); color: var(--text);}
.stButton > button[kind="primary"] {
  background: var(--lima); color: #171226; border-color: #a8cc3a;
  box-shadow: rgba(0,0,0,.18) 0px 1px 3px 0px inset;
}
.stButton > button[kind="primary"]:hover {background: #d3f56e;}

/* ── Hero ────────────────────────────────────────────── */
.hero {padding: 6vh 0 2vh 0; max-width: 740px; margin: 0 auto;}
.hero h1 {font-size: 28px; font-weight: 600; letter-spacing: -0.02em;
  margin: 8px 0 10px; color: var(--text);}
.hero p {color: var(--text-2); font-size: 14px; line-height: 1.65;}
.sug {
  text-align: left; padding: 11px 13px; border: 1px solid var(--bd);
  border-radius: 10px; background: var(--surface-1);
  color: var(--text-2); font-size: 12.5px; line-height: 1.45; cursor: pointer;
}
.sug:hover {border-color: var(--bd-strong); background: var(--surface-2); color: var(--text);}

/* ── Chat ────────────────────────────────────────────── */
[data-testid="stChatMessage"] {
  background: transparent; border: none; padding: 0 0 4px 0; margin-bottom: 6px;
}
[data-testid="stChatMessage"]:has(> div:first-child [data-testid="chatAvatarIcon-user"]) {
  background: var(--surface-1); border: 1px solid var(--bd); border-radius: 12px;
  padding: 13px 15px; margin: 0 0 14px 8%;
}
[data-testid="stChatMessage"]:has(> div:first-child [data-testid="chatAvatarIcon-assistant"]) {
  border-left: 2px solid var(--roxo); padding: 2px 0 8px 16px; margin-left: 2px;
}
[data-testid="stChatMessage"] p {font-size: 14px; line-height: 1.66; color: var(--text);}
[data-testid="stChatMessage"] code {
  font-family: var(--mono); font-size: 12px; background: var(--violeta);
  border: 1px solid var(--bd-strong); border-radius: 4px; padding: 1px 5px; color: #e8e4ff;
}
[data-testid="stChatMessage"] pre {border: 1px solid var(--bd); border-radius: 9px; background: var(--deep);}
[data-testid="stChatMessage"] table {font-size: 12.5px; border-collapse: collapse;}
[data-testid="stChatMessage"] th {
  font-family: var(--ui); font-size: 10px; text-transform: uppercase; letter-spacing: .1em;
  color: var(--text-3); border-bottom: 1px solid var(--bd-strong);
}
[data-testid="stChatMessage"] td {border-bottom: 1px solid var(--bd); padding: 5px 10px;}
[data-testid="stChatInput"] textarea, div[data-testid="stChatInput"] textarea {
  background: var(--deep) !important; border: 1px solid var(--bd-strong) !important;
  border-radius: 10px !important; color: var(--text) !important;
  font-family: var(--ui) !important; font-size: 13.5px !important;
  box-shadow: rgba(0,0,0,.25) 0px 1px 4px inset !important;
}
div[data-testid="stChatInput"]:focus-within textarea {border-color: var(--roxo) !important;}
div[data-testid="stChatInput"] {border: none; background: transparent;}

/* ── Rastro (trace) ──────────────────────────────────── */
[data-testid="stExpander"] {
  border: 1px solid var(--bd-strong) !important; border-radius: 9px !important;
  background: var(--violeta) !important;
}
[data-testid="stExpander"] summary {padding: 8px 12px !important;}
[data-testid="stExpander"] summary:hover {background: var(--surface-2) !important;
  border-radius: 9px !important;}
[data-testid="stExpander"] summary p {font-family: var(--mono); font-size: 11px;
  letter-spacing: .08em; text-transform: uppercase; color: var(--text-2) !important; font-weight: 500;}
.trace-row {
  display: flex; gap: 10px; align-items: baseline;
  font-family: var(--mono); font-size: 11px; padding: 3px 0;
  border-bottom: 1px dashed rgba(139,116,255,.12);
}
.trace-row .k {flex: 0 0 72px; text-align: center; border-radius: 4px; padding: 1px 0;
  font-size: 9.5px; font-weight: 500; letter-spacing: .06em; text-transform: uppercase;}
.tk-sql {background: rgba(124,183,255,.14); color: var(--azul);}
.tk-rag {background: rgba(194,239,78,.12); color: var(--lima);}
.tk-ctx {background: rgba(139,125,251,.16); color: var(--roxo-hover);}
.tk-retry {background: rgba(255,178,135,.14); color: var(--coral);}
.tk-erro {background: rgba(250,127,170,.14); color: var(--rosa);}
.tk-meta {background: var(--surface-2); color: var(--text-3);}
.trace-row .v {color: var(--text-2); word-break: break-word; line-height: 1.5;}

/* ── Metricas ────────────────────────────────────────── */
.metric-grid {display: grid; grid-template-columns: repeat(4, 1fr); gap: 10px;}
.metric {
  border: 1px solid var(--bd); border-radius: 11px; background: var(--surface-1);
  padding: 13px 15px; box-shadow: rgba(9,6,20,.35) 0px 8px 14px -8px;
}
.metric .label {margin-bottom: 9px;}
.metric .value {font-size: 25px; font-weight: 600; letter-spacing: -0.02em; color: var(--text);}
.metric .value small {font-size: 12px; font-weight: 500; color: var(--text-3); margin-left: 2px;}
.metric .sub {font-size: 11px; color: var(--text-3); margin-top: 6px;}
.metric .value.warn {color: var(--coral);}
.metric .value.crit {color: var(--rosa);}
.metric .value.ok {color: var(--lima);}
.panel-h {
  font-family: var(--ui); font-size: 11px; font-weight: 600; letter-spacing: .12em;
  text-transform: uppercase; color: var(--text-2);
  margin: 24px 0 10px; display: flex; align-items: center; gap: 10px;
}
.panel-h::after {content: ""; flex: 1; height: 1px; background: var(--bd);}

/* ── Dataframes / conversas ──────────────────────────── */
[data-testid="stDataFrame"] {font-size: 12px; border: 1px solid var(--bd); border-radius: 9px;}
.conv-row {
  display: flex; align-items: center; gap: 10px; padding: 9px 12px;
  border: 1px solid var(--bd); border-radius: 9px; background: var(--surface-1);
  margin-bottom: 7px;
}
.conv-row .titulo {flex: 1; font-size: 13px; color: var(--text); font-weight: 500;}
.conv-row .meta {font-family: var(--mono); font-size: 10px; color: var(--text-3); letter-spacing: .04em;}
.conv-row .ativo {border-color: var(--roxo); background: var(--surface-2);}
.divider {height: 1px; background: var(--bd); margin: 20px 0;}

/* ── Misc ────────────────────────────────────────────── */
.block-container {padding: 1.3rem 1.4rem 5rem; max-width: 1100px;}
h2 {font-size: 19px; font-weight: 600; letter-spacing: -0.015em;}
a {color: var(--roxo-hover);}
[data-testid="stMetric"] {background: var(--surface-1); border: 1px solid var(--bd);
  border-radius: 10px; padding: 12px 14px;}
[data-testid="stMetricLabel"] p {font-family: var(--ui) !important; font-size: 10px !important;
  font-weight: 600 !important; letter-spacing: .12em !important; text-transform: uppercase !important;
  color: var(--text-3) !important;}
[data-testid="stMetricValue"] {font-weight: 600 !important; color: var(--text) !important;}
[data-testid="stStatusWidget"] {display: none;}
</style>
"""

LOGO_SVG = """<svg width="20" height="20" viewBox="0 0 24 24" fill="none">
<path d="M12 2L20 5.5V11c0 5-3.4 8.9-8 11-4.6-2.1-8-6-8-11V5.5L12 2z"
 stroke="#c2ef4e" stroke-width="1.6" stroke-linejoin="round"/>
<path d="M8.6 12l2.3 2.3 4.5-4.6" stroke="#c2ef4e" stroke-width="1.7"
 stroke-linecap="round" stroke-linejoin="round"/>
</svg>"""


def inject_css() -> None:
    """Injeta o design system. Fontes Rubik/JetBrains Mono vem do sistema
    (instaladas em ~/.local/share/fonts) — sem payload embutido, sem vazamento
    de data-URI no markdown."""
    st.markdown(CSS, unsafe_allow_html=True)


@st.cache_resource(show_spinner=False)
def _contar_chunks() -> int:
    """Contagem de chunks cacheada por processo: o Chroma nao e aberto a cada rerun
    (abertura concorrente travava o render de sessoes ativas)."""
    from sentinelasoc import rag  # import local evita ciclo

    try:
        return rag.get_collection().count()
    except Exception:  # indicador cosmético
        return 0


def sidebar_shell(page: str) -> None:
    """Navegacao lateral com estado ativo e resumo de runtime."""
    st.markdown(
        f"""
        <div style="display:flex;align-items:center;gap:9px;padding:2px 4px 14px">
          {LOGO_SVG}<span style="font-weight:600;font-size:13.5px;letter-spacing:-.01em">SentinelaSOC</span>
        </div>
        """,
        unsafe_allow_html=True,
    )
    for chave, titulo, _icone in NAV:
        if st.button(
            titulo,
            key=f"nav_{chave}",
            use_container_width=True,
            type="primary" if chave == page else "secondary",
        ):
            st.query_params["page"] = chave
            st.rerun()

    from sentinelasoc import memory  # import local evita ciclo

    st.markdown("<div class='side-h microlabel'>Runtime</div>", unsafe_allow_html=True)
    st.markdown(
        f"<div class='side-kv'><span class='k'>LLM</span>"
        f"<span class='v'>{get_settings().llm_model}</span></div>"
        "<div class='side-kv'><span class='k'>Embeddings</span>"
        "<span class='v'>MiniLM-L12</span></div>"
        "<div class='side-kv'><span class='k'>Recuperação</span>"
        "<span class='v'>híbrida BM25+vetor</span></div>",
        unsafe_allow_html=True,
    )
    st.markdown("<div class='side-h microlabel'>Base</div>", unsafe_allow_html=True)
    chunks = _contar_chunks()
    st.markdown(
        f"<div class='side-kv'><span class='k'>Chunks</span><span class='v'>{chunks}</span></div>"
        f"<div class='side-kv'><span class='k'>Conversas</span>"
        f"<span class='v'>{len(memory.listar_conversas(50))}</span></div>"
        f"<div class='side-kv'><span class='k'>Fatos de perfil</span>"
        f"<span class='v'>{len(memory.fatos_perfil())}</span></div>",
        unsafe_allow_html=True,
    )
    st.markdown(
        "<div class='side-note'>Execução 100% local · memória em SQLite · "
        "logs por request_id em <code>logs/</code></div>",
        unsafe_allow_html=True,
    )


def app_bar(page: str) -> None:
    """Barra superior: marca, migalha e pildes de status em tempo real."""
    st.markdown(
        f"""
        <div class="appbar">
          <div class="brand">{LOGO_SVG} SentinelaSOC</div>
          <span class="crumb">/ <b>{page}</b></span>
          <div class="spacer"></div>
          <span class="pill"><span class="dot"></span> {get_settings().llm_model}</span>
          <span class="pill">v{sentinelasoc.__version__}</span>
        </div>
        """,
        unsafe_allow_html=True,
    )
