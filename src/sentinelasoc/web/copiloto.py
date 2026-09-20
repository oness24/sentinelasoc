"""Pagina Copiloto: chat com rastro auditavel por resposta."""

import base64
import time

import streamlit as st

from sentinelasoc import memory
from sentinelasoc.agent import AgenteSOC
from sentinelasoc.web.shell import app_bar

SUGESTOES = [
    ("Dados", "Quantos incidentes críticos estão abertos e em quais ativos?"),
    ("Dados", "Qual a taxa de falsos positivos por tipo de incidente?"),
    ("Playbook", "Como devo responder a um incidente de phishing?"),
    ("Política", "Qual o SLA de correção para uma CVE com CVSS 9.5 em ativo exposto?"),
]


def _avatar(svg: str) -> str:
    return "data:image/svg+xml;base64," + base64.b64encode(svg.encode()).decode()


AV_ASSISTENTE = _avatar(
    """<svg xmlns='http://www.w3.org/2000/svg' width='28' height='28' viewBox='0 0 28 28'
 fill='none'><rect width='28' height='28' rx='7' fill='#241d10'/>
<circle cx='14' cy='14' r='9' fill='#f5b800' opacity='.15'/>
<path d='M14 5 Q15.7 12.3 23 14 Q15.7 15.7 14 23 Q12.3 15.7 5 14 Q12.3 12.3 14 5 Z'
 fill='#f5b800'/><circle cx='14' cy='14' r='1.5' fill='#fff3c4'/></svg>"""
)
AV_USUARIO = _avatar(
    """<svg xmlns='http://www.w3.org/2000/svg' width='28' height='28' viewBox='0 0 24 24'
 fill='none'><rect width='28' height='28' rx='7' fill='#2a2519'/>
<circle cx='12' cy='9.5' r='3' stroke='#b5ac97' stroke-width='1.5'/>
<path d='M5.8 19c1.2-3 3.5-4.4 6.2-4.4S17 16 18.2 19' stroke='#b5ac97'
 stroke-width='1.5' stroke-linecap='round'/></svg>"""
)


@st.cache_resource(show_spinner=False)
def _agente() -> AgenteSOC:
    return AgenteSOC()


def _renderizar_trace(trace: list[dict]) -> None:
    classes = {
        "sql": "tk-sql",
        "rag": "tk-rag",
        "ctx": "tk-ctx",
        "retry": "tk-retry",
        "erro": "tk-erro",
    }
    linhas = []
    for item in trace:
        tipo = item.get("tipo", "?")
        cls = classes.get(tipo, "tk-meta")
        if tipo == "request":
            continue
        if tipo == "sql":
            detalhe = f"{item['sql'][:130]} · {item['linhas']} linha(s)"
        elif tipo == "rag":
            detalhe = f"consulta: {item.get('consulta', '')[:60]} · {item.get('chunks', 0)} trechos"
        elif tipo == "ctx":
            detalhe = f"seguimento reformulado → {item.get('reescrita', '')[:90]}"
        elif tipo in ("retry", "erro"):
            detalhe = str(item.get("detalhe", ""))[:120]
        elif tipo == "direto":
            detalhe = str(item.get("decisao", ""))[:90]
        elif tipo in ("roteamento", "reformulacao", "resposta"):
            continue
        else:
            detalhe = str(item)[:100]
        linhas.append(
            f"<div class='trace-row'><span class='k {cls}'>{tipo}</span>"
            f"<span class='v'>{detalhe}</span></div>"
        )
    if linhas:
        st.markdown("".join(linhas), unsafe_allow_html=True)


def _meta(label: str, extra: str = "") -> None:
    sufixo = f" · {extra}" if extra else ""
    st.markdown(
        f"<div style='font-family:var(--mono);font-size:10.5px;color:var(--text-3);"
        f"letter-spacing:.08em;margin-bottom:6px'>{label}{sufixo}</div>",
        unsafe_allow_html=True,
    )


def render() -> None:
    app_bar("Copiloto")
    if "mensagens" not in st.session_state:
        st.session_state.mensagens = []
    if "pergunta_pendente" not in st.session_state:
        st.session_state.pergunta_pendente = None
    if "conversa_id" not in st.session_state:
        st.session_state.conversa_id = None
    if "perfil_fatos" not in st.session_state:
        st.session_state.perfil_fatos = memory.fatos_perfil()

    _botao_nova_conversa()
    agente = _agente()

    # ── Estado vazio: hero + sugestoes ──
    if not st.session_state.mensagens and not st.session_state.pergunta_pendente:
        st.markdown(
            "<div class='hero'><div class='microlabel' style='color:#f5b800'>"
            "Copiloto de segurança · 100% local</div>"
            "<h1>Pergunte. O SOC responde com dados e fontes.</h1>"
            "<p>Incidentes, ativos, vulnerabilidades, playbooks e políticas — em linguagem "
            "natural, com a origem de cada informação citada e auditável.</p></div>",
            unsafe_allow_html=True,
        )
        st.markdown("<div class='sug-grid'>", unsafe_allow_html=True)
        c1, c2 = st.columns(2)
        botoes = []
        for i, (tag, pergunta) in enumerate(SUGESTOES):
            col = c1 if i % 2 == 0 else c2
            with col:
                st.markdown(
                    f"<div style='font-family:var(--mono);font-size:10px;"
                    f"letter-spacing:.1em;color:var(--text-3);margin-bottom:-6px;"
                    f"text-transform:uppercase'>{tag}</div>",
                    unsafe_allow_html=True,
                )
                botoes.append(st.button(pergunta, key=f"sug_{i}", use_container_width=True))
        st.markdown("</div>", unsafe_allow_html=True)
        for pergunta, clicado in zip([s[1] for s in SUGESTOES], botoes, strict=False):
            if clicado:
                st.session_state.pergunta_pendente = pergunta
                st.rerun()

    # ── Historico ──
    for msg in st.session_state.mensagens:
        if msg["role"] == "user":
            with st.chat_message("user", avatar=AV_USUARIO):
                _meta("ANALISTA")
                st.markdown(msg["content"])
        else:
            with st.chat_message("assistant", avatar=AV_ASSISTENTE):
                req = ""
                tr = msg.get("trace") or []
                if tr and tr[0].get("id"):
                    req = f"req {tr[0]['id']}"
                _meta("SENTINELASOC", req)
                st.markdown(msg["content"], unsafe_allow_html=True)
                if tr:
                    with st.expander("Detalhes da execução", expanded=False):
                        _renderizar_trace(tr)

    # ── Pergunta em andamento ──
    if st.session_state.pergunta_pendente:
        pergunta = st.session_state.pergunta_pendente
        st.session_state.pergunta_pendente = None
        with st.chat_message("user", avatar=AV_USUARIO):
            _meta("ANALISTA")
            st.markdown(pergunta)
        history = [
            {"role": m["role"], "content": m["content"]} for m in st.session_state.mensagens[-6:]
        ]
        with st.chat_message("assistant", avatar=AV_ASSISTENTE):
            _meta("SENTINELASOC", "processando")
            caixa = st.status(label="pipeline", expanded=False)
            placeholder = st.empty()
            texto = ""
            inicio = time.perf_counter()
            try:
                for chunk in agente.answer(pergunta, history, st.session_state.perfil_fatos):
                    texto += chunk
                    placeholder.markdown(texto + " ▍", unsafe_allow_html=True)
            except Exception as exc:  # erro visivel para o analista
                texto = (
                    "Falha ao consultar o copiloto agora. "
                    f"Detalhe para o administrador: `{type(exc).__name__}: {exc}`"
                )
                st.error(texto)
            duracao = time.perf_counter() - inicio
            caixa.update(
                label=f"Respondido em {duracao:.1f}s",
                state="complete",
                expanded=False,
            )
            placeholder.markdown(texto, unsafe_allow_html=True)
            st.session_state.mensagens.append(
                {"role": "assistant", "content": texto, "trace": agente.last_trace}
            )
            with st.expander("Detalhes da execução", expanded=False):
                _renderizar_trace(agente.last_trace)

        # persistencia episodica + aprendizado semantico
        if st.session_state.conversa_id is None:
            st.session_state.conversa_id = memory.nova_conversa(pergunta)
        cid = st.session_state.conversa_id
        memory.salvar_mensagem(cid, "user", pergunta)
        memory.salvar_mensagem(cid, "assistant", texto, agente.last_trace)
        if memory.contar_trocas(cid) % 2 == 0:
            fatos = agente.extrair_fatos(pergunta, texto)
            if fatos and memory.atualizar_fatos(fatos):
                st.session_state.perfil_fatos = memory.fatos_perfil()

    # ── Composer ──
    nova = st.chat_input("Pergunte ao copiloto…")
    if nova:
        st.session_state.pergunta_pendente = nova
        st.rerun()


def _botao_nova_conversa() -> None:
    """Acao rapida de recomeco (encerra a conversa corrente sem apagar o historico)."""
    if st.session_state.get("mensagens") and st.button("Nova conversa", key="nova_conversa"):
        st.session_state.mensagens = []
        st.session_state.conversa_id = None
        st.rerun()
