"""Shell da interface: design system, app bar e navegacao.

Tokens visuais inspirados na pratica da Linear: canvas quase-preto, superfcies
empilhadas por luminancia, bordas rgba sutis, um unico acento (esmeralda),
Inter com avulsoes cv01/ss03 e hierarquia tipografica clara. Sem emojis.
"""

import streamlit as st

import sentinelasoc
from sentinelasoc.settings import get_settings

NAV = [
    ("copiloto", "Copiloto", ":material/forum:"),
    ("painel", "Painel", ":material/monitoring:"),
    ("memoria", "Memória", ":material/psychology:"),
]

CSS = """
<style>
:root {
  --canvas: #08090a;
  --surface-1: rgba(255,255,255,.026);
  --surface-2: rgba(255,255,255,.05);
  --surface-3: rgba(255,255,255,.075);
  --bd: rgba(255,255,255,.08);
  --bd-strong: rgba(255,255,255,.14);
  --text: #eceef0;
  --text-2: #a8b0b8;
  --text-3: #6b7480;
  --accent: #30d98c;
  --accent-dim: rgba(48,217,140,.14);
  --amber: #f5b944;
  --red: #f4708a;
  --blue: #7cb7ff;
  --mono: 'Berkeley Mono', ui-monospace, 'SF Mono', 'Cascadia Code', Menlo, Consolas, monospace;
}
html, body, [class*="css"], .stApp, .main, section.main {
  background: var(--canvas) !important; color: var(--text);
  font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
  font-feature-settings: 'cv01';
  letter-spacing: -0.006em;
}
#MainMenu, footer, header {visibility: hidden; height: 0;}
div[data-testid="stToolbar"] {display: none;}

/* ── App bar ─────────────────────────────────────────── */
.appbar {
  display: flex; align-items: center; gap: 14px;
  height: 54px; padding: 0 4px 0 0;
  border-bottom: 1px solid var(--bd);
  margin: -1rem -1rem 1.5rem -1rem; padding-left: 20px;
}
.appbar .brand {display: flex; align-items: center; gap: 10px; font-weight: 600; font-size: 14.5px;}
.appbar .brand svg {display: block;}
.appbar .env {
  font-family: var(--mono); font-size: 10.5px; letter-spacing: .08em;
  color: var(--text-2); border: 1px solid var(--bd); border-radius: 999px;
  padding: 2px 9px; text-transform: uppercase;
}
.appbar .crumb {color: var(--text-3); font-size: 13px;}
.appbar .crumb b {color: var(--text-2); font-weight: 550;}
.appbar .spacer {flex: 1;}
.pill {
  display: inline-flex; align-items: center; gap: 6px;
  font-family: var(--mono); font-size: 11px; color: var(--text-2);
  border: 1px solid var(--bd); border-radius: 6px; padding: 3.5px 9px;
  background: var(--surface-1);
}
.pill .dot {width: 6px; height: 6px; border-radius: 50%; background: var(--accent);}
.pill .dot.off {background: var(--red);}
.pill b {color: var(--text); font-weight: 550;}

/* ── Sidebar ─────────────────────────────────────────── */
section[data-testid="stSidebar"] {
  background: #0b0c0e; border-right: 1px solid var(--bd);
}
section[data-testid="stSidebar"] .block-container {padding-top: 1.2rem;}
section[data-testid="stSidebar"] nav {gap: 2px;}
section[data-testid="stSidebar"] nav span {
  font-size: 13.5px; color: var(--text-2); font-weight: 500;
}
section[data-testid="stSidebar"] nav a:hover span {color: var(--text); background: transparent;}
section[data-testid="stSidebar"] [aria-current="page"] span,
section[data-testid="stSidebar"] nav a.active span {color: var(--accent);}
.side-h {
  font-family: var(--mono); font-size: 10px; letter-spacing: .14em;
  text-transform: uppercase; color: var(--text-3);
  margin: 22px 0 8px 2px;
}
.side-kv {display: flex; justify-content: space-between; font-size: 12px; padding: 3px 2px;}
.side-kv .k {color: var(--text-3);}
.side-kv .v {font-family: var(--mono); font-size: 11px; color: var(--text-2);}
.side-note {font-size: 11.5px; color: var(--text-3); line-height: 1.6; margin-top: 10px;}
section[data-testid="stSidebar"] [data-testid="stButton"] button {
  background: transparent; color: var(--text-2);
  border: 1px solid transparent; border-radius: 6px; padding: 4px 8px;
  font-size: 12.5px; text-align: left; width: 100%;
  font-family: 'Inter', sans-serif; font-weight: 500;
}
section[data-testid="stSidebar"] [data-testid="stButton"] button:hover {
  background: var(--surface-2); border-color: var(--bd); color: var(--text);
}
section[data-testid="stSidebar"] [data-testid="stButton"] button[kind="secondary"] {padding: 5px 10px;}
.fact {font-size: 12px; color: var(--text-2); padding: 4px 0 4px 10px;
  border-left: 2px solid var(--bd-strong); line-height: 1.5; margin-bottom: 4px;}

/* ── Botoes globais ──────────────────────────────────── */
.stButton > button {
  background: var(--surface-2); color: var(--text-2);
  border: 1px solid var(--bd); border-radius: 7px; padding: 6px 14px;
  font-size: 13px; font-weight: 500; font-family: 'Inter', sans-serif;
  transition: background .12s ease, border-color .12s ease;
}
.stButton > button:hover {
  background: var(--surface-3); border-color: var(--bd-strong); color: var(--text);
}
.stButton > button[kind="primary"] {
  background: var(--accent-dim); border-color: rgba(48,217,140,.35); color: var(--accent);
}
.stButton > button[kind="primary"]:hover {background: rgba(48,217,140,.22);}

/* ── Hero / vazio ────────────────────────────────────── */
.hero {padding: 7vh 0 2vh 0; max-width: 720px; margin: 0 auto;}
.hero h1 {font-size: 30px; font-weight: 600; letter-spacing: -0.02em; margin-bottom: 10px;}
.hero p {color: var(--text-2); font-size: 14.5px; line-height: 1.65;}
.sug-grid {display: grid; grid-template-columns: 1fr 1fr; gap: 8px; margin-top: 20px;}
.sug {
  text-align: left; padding: 12px 14px; border: 1px solid var(--bd);
  border-radius: 9px; background: var(--surface-1);
  color: var(--text-2); font-size: 13px; line-height: 1.45; cursor: pointer;
}
.sug:hover {border-color: var(--bd-strong); background: var(--surface-2); color: var(--text);}
.sug b {display: block; color: var(--text); font-weight: 550; margin-bottom: 2px;}

/* ── Chat ────────────────────────────────────────────── */
[data-testid="stChatMessage"] {
  background: transparent; border: none; padding: 0 0 4px 0; margin-bottom: 6px;
}
[data-testid="stChatMessage"]:has(> div:first-child [data-testid="chatAvatarIcon-user"]) {
  background: var(--surface-1); border: 1px solid var(--bd); border-radius: 12px;
  padding: 14px 16px; margin: 0 0 18px 8%;
}
[data-testid="stChatMessage"]:has(> div:first-child [data-testid="chatAvatarIcon-assistant"]) {
  border-left: 2px solid var(--accent); padding: 2px 0 8px 18px; margin-left: 2px;
}
[data-testid="stChatMessage"] p {font-size: 14.5px; line-height: 1.68; color: var(--text);}
[data-testid="stChatMessage"] code {
  font-family: var(--mono); font-size: 12.5px; background: var(--surface-2);
  border: 1px solid var(--bd); border-radius: 4px; padding: 1px 5px;
}
[data-testid="stChatMessage"] pre {
  border: 1px solid var(--bd); border-radius: 8px; background: #0c0e10;
}
[data-testid="stChatMessage"] table {font-size: 13px; border-collapse: collapse;}
[data-testid="stChatMessage"] th {
  font-family: var(--mono); font-size: 11px; text-transform: uppercase;
  letter-spacing: .06em; color: var(--text-3); border-bottom: 1px solid var(--bd-strong);
}
[data-testid="stChatMessage"] td {border-bottom: 1px solid var(--bd); padding: 6px 10px;}
[data-testid="stChatInput"] textarea, div[data-testid="stChatInput"] textarea {
  background: #0d0f11 !important; border: 1px solid var(--bd) !important;
  border-radius: 10px !important; color: var(--text) !important;
  font-size: 14px !important; font-family: 'Inter', sans-serif !important;
  box-shadow: none !important;
}
div[data-testid="stChatInput"]:focus-within textarea {border-color: rgba(48,217,140,.45) !important;}
div[data-testid="stChatInput"] {border: none; background: transparent;}

/* ── Rastro (trace) ──────────────────────────────────── */
[data-testid="stExpander"] {
  border: 1px solid var(--bd) !important; border-radius: 9px !important;
  background: var(--surface-1) !important;
}
[data-testid="stExpander"] summary {font-size: 12px !important; color: var(--text-3);}
[data-testid="stExpander"] summary p {font-family: var(--mono); font-size: 11px;}
.trace-row {
  display: flex; gap: 10px; align-items: baseline;
  font-family: var(--mono); font-size: 11.5px; padding: 3.5px 0;
  border-bottom: 1px dashed rgba(255,255,255,.05);
}
.trace-row .k {flex: 0 0 74px; text-align: center; border-radius: 4px; padding: 1px 0; font-size: 10px;}
.tk-sql {background: rgba(124,183,255,.13); color: var(--blue);}
.tk-rag {background: rgba(48,217,140,.13); color: var(--accent);}
.tk-ctx {background: rgba(124,183,255,.1); color: var(--blue);}
.tk-retry {background: rgba(245,185,68,.13); color: var(--amber);}
.tk-erro {background: rgba(244,112,138,.13); color: var(--red);}
.tk-meta {background: var(--surface-2); color: var(--text-3);}
.trace-row .v {color: var(--text-2); word-break: break-word; line-height: 1.5;}

/* ── Metricas / dashboard ────────────────────────────── */
.metric-grid {display: grid; grid-template-columns: repeat(4, 1fr); gap: 10px;}
.metric {
  border: 1px solid var(--bd); border-radius: 10px; background: var(--surface-1);
  padding: 14px 16px;
}
.metric .label {
  font-family: var(--mono); font-size: 10.5px; letter-spacing: .1em;
  text-transform: uppercase; color: var(--text-3); margin-bottom: 8px;
}
.metric .value {font-size: 26px; font-weight: 600; letter-spacing: -0.02em;}
.metric .value small {font-size: 13px; font-weight: 500; color: var(--text-3); margin-left: 2px;}
.metric .sub {font-size: 11.5px; color: var(--text-3); margin-top: 6px;}
.metric .value.warn {color: var(--amber);}
.metric .value.crit {color: var(--red);}
.metric .value.ok {color: var(--accent);}
.panel-h {
  font-size: 13px; font-weight: 550; color: var(--text-2);
  margin: 26px 0 10px; display: flex; align-items: center; gap: 8px;
}
.panel-h::after {content: ""; flex: 1; height: 1px; background: var(--bd);}

/* ── Dataframes / graficos ───────────────────────────── */
[data-testid="stDataFrame"] {font-size: 12.5px; border: 1px solid var(--bd); border-radius: 9px;}
[data-testid="stMetric"] {
  background: var(--surface-1); border: 1px solid var(--bd); border-radius: 10px;
  padding: 12px 14px;
}
[data-testid="stMetricValue"] {font-weight: 600 !important;}
[data-testid="stMetricLabel"] {font-family: var(--mono); font-size: 10.5px !important;
  letter-spacing: .08em; text-transform: uppercase; color: var(--text-3) !important;}

/* ── Listas de conversa ──────────────────────────────── */
.conv-row {
  display: flex; align-items: center; gap: 10px; padding: 10px 12px;
  border: 1px solid var(--bd); border-radius: 9px; background: var(--surface-1);
  margin-bottom: 8px;
}
.conv-row .titulo {flex: 1; font-size: 13.5px; color: var(--text); font-weight: 500;}
.conv-row .meta {font-family: var(--mono); font-size: 10.5px; color: var(--text-3);}
.conv-row .ativo {border-color: rgba(48,217,140,.3);}
.divider {height: 1px; background: var(--bd); margin: 22px 0;}

/* ── Streamlit misc ──────────────────────────────────── */
.block-container {padding: 1.4rem 1.4rem 5rem; max-width: 1080px;}
h2 {font-size: 20px; font-weight: 600; letter-spacing: -0.015em;}
h3 {font-size: 15px; font-weight: 600;}
a {color: var(--accent);}
.status-ok {color: var(--accent); font-family: var(--mono); font-size: 11.5px;}
[data-testid="stStatusWidget"] {display: none;}
</style>
"""

LOGO_SVG = """<svg width="22" height="22" viewBox="0 0 24 24" fill="none">
<path d="M12 2L20 5.5V11c0 5-3.4 8.9-8 11-4.6-2.1-8-6-8-11V5.5L12 2z"
 stroke="#30d98c" stroke-width="1.6" stroke-linejoin="round"/>
<path d="M8.6 12l2.3 2.3 4.5-4.6" stroke="#30d98c" stroke-width="1.7"
 stroke-linecap="round" stroke-linejoin="round"/>
</svg>"""


def inject_css() -> None:
    st.markdown(CSS, unsafe_allow_html=True)


def sidebar_shell(page: str) -> None:
    """Navegacao lateral com estado ativo e resumo de runtime."""
    st.markdown(
        f"""
        <div style="display:flex;align-items:center;gap:9px;padding:2px 4px 14px">
          {LOGO_SVG}<span style="font-weight:600;font-size:14px">SentinelaSOC</span>
        </div>
        """,
        unsafe_allow_html=True,
    )
    for chave, titulo, _icone in NAV:
        ativo = chave == page
        if st.button(
            titulo,
            key=f"nav_{chave}",
            use_container_width=True,
            type="primary" if ativo else "secondary",
        ):
            st.query_params["page"] = chave
            st.rerun()

    from sentinelasoc import memory, rag  # import local evita ciclo

    st.markdown("<div class='side-h'>Runtime</div>", unsafe_allow_html=True)
    st.markdown(
        f"<div class='side-kv'><span class='k'>LLM</span>"
        f"<span class='v'>{get_settings().llm_model}</span></div>"
        "<div class='side-kv'><span class='k'>Embeddings</span>"
        "<span class='v'>MiniLM-L12</span></div>"
        "<div class='side-kv'><span class='k'>Recuperação</span>"
        "<span class='v'>hibrida (BM25+vetor)</span></div>",
        unsafe_allow_html=True,
    )
    st.markdown("<div class='side-h'>Base</div>", unsafe_allow_html=True)
    try:
        chunks = rag.get_collection().count()
    except Exception:  # indicator cosmético
        chunks = 0
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
        "logs correlacionados por request_id em <code>logs/</code></div>",
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
