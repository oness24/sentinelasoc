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
  --canvas: #07050a;
  --deep: #140f22;
  --surface-1: rgba(245,184,0,.035);
  --surface-2: rgba(245,184,0,.065);
  --surface-3: rgba(245,184,0,.11);
  --violeta: #241d10;
  --violeta-forte: #3a2e12;
  --bd: #363021;
  --bd-strong: #4d4430;
  --text: #f7f4ec;
  --text-2: #b5ac97;
  --text-3: #7a7260;
  --ouro: #f5b800;
  --ouro-hover: #ffd02e;
  --ouro-fraco: rgba(245,184,0,.14);
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
    radial-gradient(700px 520px at 108% -8%, rgba(245, 186, 20, .30), transparent 62%),
    radial-gradient(1200px 900px at 104% -4%, rgba(196, 141, 12, .13), transparent 65%),
    radial-gradient(900px 700px at -6% 104%, rgba(245, 186, 20, .08), transparent 60%),
    #07050a;
}
html, body { background: #07050a !important; }
body, .stApp, .main, [class*="css"], [data-testid="stHeader"], header { background: transparent !important; }
section[data-testid="stSidebar"] { background: #0d0a12 !important; }
#MainMenu, footer, div[data-testid="stToolbar"] {visibility: hidden; height: 0;}

/* ── App bar ─────────────────────────────────────────── */
.appbar {
  display: flex; align-items: center; gap: 14px; height: 50px;
  padding: 0 6px 0 22px; margin: 0 0 1.1rem;
  border-bottom: 1px solid var(--bd); background: var(--deep);
  border-radius: 10px 10px 0 0;
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
.pill .dot {width: 6px; height: 6px; border-radius: 50%; background: var(--ouro); box-shadow: 0 0 6px rgba(245,184,0,.6);}
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
  background: var(--ouro-fraco); border-color: rgba(245,184,0,.4); color: var(--ouro);
  box-shadow: none;
}
section[data-testid="stSidebar"] [data-testid="stButton"] button[kind="primary"]:hover {
  background: rgba(245,184,0,.22);
}
section[data-testid="stSidebar"] [data-testid="stButton"] button[kind="secondary"]:not(:hover) {
  border-left: 2px solid transparent;
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
  background: var(--surface-2); color: var(--text-2);
  border: 1px solid var(--bd); border-radius: 8px; padding: 6px 14px;
  font-family: var(--ui); font-size: 12px; font-weight: 600;
  letter-spacing: .04em; box-shadow: rgba(0,0,0,.24) 0px 1px 3px 0px inset;
  transition: background .12s ease;
}
.stButton > button:hover {background: var(--surface-3); border-color: var(--bd-strong); color: var(--text);}
.stButton > button[kind="primary"] {
  background: var(--ouro); color: #191204; border-color: #c99700;
  box-shadow: rgba(0,0,0,.2) 0px 1px 3px 0px inset; font-weight: 600;
}
.stButton > button[kind="primary"]:hover {background: var(--ouro-hover);}

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
  border-left: 2px solid var(--ouro); padding: 2px 0 8px 16px; margin-left: 2px;
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
div[data-testid="stChatInput"]:focus-within textarea {border-color: rgba(245,184,0,.55) !important; box-shadow: 0 0 0 3px rgba(245,184,0,.08) !important;}
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
.tk-rag {background: rgba(245,184,0,.14); color: var(--ouro);}
.tk-ctx {background: rgba(124,183,255,.12); color: var(--azul);}
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
.metric .value.ok {color: var(--ouro);}
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
.conv-row .ativo {border-color: var(--ouro); background: var(--surface-2);}
.divider {height: 1px; background: var(--bd); margin: 20px 0;}

/* ── Misc ────────────────────────────────────────────── */
.block-container {padding: 0 1.4rem 5rem; max-width: 1100px;}
h2 {font-size: 19px; font-weight: 600; letter-spacing: -0.015em;}
a {color: var(--ouro-hover);}
[data-testid="stMetric"] {background: var(--surface-1); border: 1px solid var(--bd);
  border-radius: 10px; padding: 12px 14px;}
[data-testid="stMetricLabel"] p {font-family: var(--ui) !important; font-size: 10px !important;
  font-weight: 600 !important; letter-spacing: .12em !important; text-transform: uppercase !important;
  color: var(--text-3) !important;}
[data-testid="stMetricValue"] {font-weight: 600 !important; color: var(--text) !important;}
[data-testid="stStatusWidget"] {display: none;}
/* Scrollbars finas escuras */
*::-webkit-scrollbar {width: 9px; height: 9px;}
*::-webkit-scrollbar-track {background: transparent;}
*::-webkit-scrollbar-thumb {background: #2b2415; border-radius: 8px; border: 2px solid #07050a;}
*::-webkit-scrollbar-thumb:hover {background: #443821;}
html {scrollbar-color: #2b2415 #07050a; scrollbar-width: thin;}
::selection {background: rgba(245,184,0,.30); color: #fff;}
@keyframes msg-in {from {opacity: 0; transform: translateY(6px);} to {opacity: 1; transform: none;}}
[data-testid="stChatMessage"] {animation: msg-in .26s ease both;}
[data-testid="stChatMessage"] h1, [data-testid="stChatMessage"] h2,
[data-testid="stChatMessage"] h3, [data-testid="stChatMessage"] h4 {
  font-size: 14.5px; font-weight: 600; margin: 14px 0 6px; color: var(--text);}
[data-testid="stChatMessage"] ul, [data-testid="stChatMessage"] ol {
  padding-left: 20px; margin: 8px 0;}
[data-testid="stChatMessage"] li {margin: 3px 0;}
[data-testid="stChatMessage"] blockquote {
  border-left: 2px solid var(--bd-strong); color: var(--text-2);
  padding: 2px 0 2px 12px; margin: 8px 0;}
[data-testid="stChatMessage"] hr {border: none; border-top: 1px solid var(--bd); margin: 14px 0;}
[data-testid="stChatMessage"] strong {color: var(--text); font-weight: 600;}
div[data-testid="stChatInput"] {
  background: #0d0a12; border: 1px solid var(--bd-strong); border-radius: 12px;
  padding: 6px 8px 6px 14px; box-shadow: 0 10px 28px -14px rgba(0,0,0,.65);
  transition: border-color .15s ease, box-shadow .15s ease;}
div[data-testid="stChatInput"]:focus-within {
  border-color: rgba(245,184,0,.5);
  box-shadow: 0 0 0 3px rgba(245,184,0,.07), 0 10px 28px -14px rgba(0,0,0,.65);}
[data-testid="stChatInput"] textarea, div[data-testid="stChatInput"] textarea {
  border: none !important; background: transparent !important;
  box-shadow: none !important; padding: 8px 0 !important;}
div[data-testid="stChatInput"] button {
  background: var(--ouro) !important; color: #191204 !important;
  border: none !important; border-radius: 8px !important; padding: 6px 10px !important;}
div[data-testid="stChatInput"] button:hover {background: var(--ouro-hover) !important;}
.composer-hint {
  text-align: center; font-family: var(--mono); font-size: 10px;
  color: var(--text-3); letter-spacing: .08em; margin-top: 8px; text-transform: uppercase;}
[data-testid="stStatus"] {
  background: var(--surface-1) !important; border: 1px solid var(--bd) !important;
  border-radius: 9px !important;}
.hero-mark {margin-bottom: 18px;
  filter: drop-shadow(0 0 26px rgba(245,184,0,.28));}
.hero-mark svg {display: block;}
/* Controles de colapso/expansao da sidebar — sempre visiveis e estilizados */
[data-testid="stSidebarCollapseButton"] {visibility: visible !important; opacity: 1 !important;}
[data-testid="stSidebarCollapseButton"] button {
  color: var(--text-3) !important; border-radius: 7px !important; padding: 5px !important;}
[data-testid="stSidebarCollapseButton"] button:hover {
  color: var(--ouro) !important; background: var(--surface-2) !important;}
[data-testid="stSidebarCollapsedControl"] {
  visibility: visible !important; opacity: 1 !important; z-index: 1000 !important;
  margin: 10px 0 0 10px !important;}
[data-testid="stSidebarCollapsedControl"] button {
  background: var(--deep) !important; border: 1px solid var(--bd-strong) !important;
  border-radius: 9px !important; padding: 7px !important; color: var(--ouro) !important;
  box-shadow: 0 6px 18px -8px rgba(0,0,0,.7) !important;}
[data-testid="stSidebarCollapsedControl"] button:hover {
  border-color: rgba(245,184,0,.5) !important; color: var(--ouro-hover) !important;}
body:has(section[data-testid="stSidebar"][aria-expanded="false"]) .appbar {padding-left: 64px;}
/* Sidebar colapsada: o botao de reabrir fica FIXO no canto sup-esq, dourado */
section[data-testid="stSidebar"][aria-expanded="false"] {
  transform: none !important; width: 0 !important; min-width: 0 !important;
  overflow: visible !important;}
section[data-testid="stSidebar"][aria-expanded="false"] [data-testid="stSidebarContent"] {
  visibility: hidden;}
section[data-testid="stSidebar"][aria-expanded="false"] [data-testid="stSidebarCollapseButton"] {
  position: fixed !important; left: 10px !important; top: 10px !important;
  z-index: 2000 !important; transform: none !important;}
section[data-testid="stSidebar"][aria-expanded="false"] [data-testid="stSidebarCollapseButton"] button {
  background: var(--deep) !important; border: 1px solid var(--bd-strong) !important;
  border-radius: 9px !important; color: var(--ouro) !important; padding: 7px !important;
  box-shadow: 0 6px 18px -8px rgba(0,0,0,.7) !important;}
section[data-testid="stSidebar"][aria-expanded="false"] [data-testid="stSidebarCollapseButton"] button:hover {
  border-color: rgba(245,184,0,.55) !important; color: var(--ouro-hover) !important;}
</style>
"""

# Marca Quimera: o clarao dourado da imagem de referencia, geometrico (4 pontas + nucleo)
LOGO_SVG = """<svg width="20" height="20" viewBox="0 0 24 24" fill="none">
<circle cx="12" cy="12" r="9.5" fill="#f5b800" opacity=".14"/>
<path d="M12 2.5 Q13.6 10.4 21.5 12 Q13.6 13.6 12 21.5 Q10.4 13.6 2.5 12 Q10.4 10.4 12 2.5 Z"
 fill="#f5b800"/>
<circle cx="12" cy="12" r="1.4" fill="#fff3c4"/>
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
    from sentinelasoc import memory as _mem

    recentes = _mem.listar_conversas(3)
    if recentes:
        st.markdown("<div class='side-h microlabel'>Recentes</div>", unsafe_allow_html=True)
        for conv in recentes:
            atual = conv["id"] == st.session_state.get("conversa_id")
            if st.button(
                (conv["titulo"][:34] + ("…" if len(conv["titulo"]) > 34 else "")),
                key=f"rec_{conv['id']}",
                use_container_width=True,
                type="primary" if atual else "secondary",
            ):
                st.session_state["conversa_id"] = conv["id"]
                st.session_state["mensagens"] = _mem.carregar_mensagens(conv["id"])
                st.query_params["page"] = "copiloto"
                st.rerun()
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
