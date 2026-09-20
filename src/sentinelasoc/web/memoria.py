"""Pagina Memoria: conversas retomaveis e perfil do analista (transparencia total)."""

import datetime

import streamlit as st

from sentinelasoc import memory
from sentinelasoc.web.shell import app_bar


def render() -> None:
    app_bar("Memória")
    if "perfil_fatos" not in st.session_state:
        st.session_state.perfil_fatos = memory.fatos_perfil()
    if "conversa_id" not in st.session_state:
        st.session_state.conversa_id = None
    if "mensagens" not in st.session_state:
        st.session_state.mensagens = []

    col1, col2 = st.columns([1.5, 1])

    # ── Conversas (memoria episodica) ──
    with col1:
        st.markdown("<div class='panel-h'>Conversas</div>", unsafe_allow_html=True)
        conversas = memory.listar_conversas(20)
        if not conversas:
            st.markdown(
                "<div class='side-note'>Nenhuma conversa ainda. As conversas ficam "
                "neste dispositivo (SQLite) e podem ser retomadas a qualquer momento.</div>",
                unsafe_allow_html=True,
            )
        for conv in conversas:
            atual = conv["id"] == st.session_state.conversa_id
            try:
                trocas = memory.contar_trocas(conv["id"])
            except Exception:  # contador e cosmético
                trocas = 0
            c_left, c_resume, c_del = st.columns([1, 0.28, 0.18])
            with c_left:
                st.markdown(
                    f"<div class='conv-row {'ativo' if atual else ''}'>"
                    f"<div><div class='titulo'>{conv['titulo'][:60]}</div>"
                    f"<div class='meta'>{trocas} troca(s) · "
                    f"{conv.get('atualizada_em', '')[:16]}</div></div></div>",
                    unsafe_allow_html=True,
                )
            with c_resume:
                if st.button("Abrir", key=f"abrir_{conv['id']}"):
                    st.session_state.conversa_id = conv["id"]
                    st.session_state.mensagens = memory.carregar_mensagens(conv["id"])
                    st.query_params["page"] = "copiloto"
                    st.rerun()
            with c_del:
                if st.button("Apagar", key=f"apagar_{conv['id']}"):
                    memory.apagar_conversa(conv["id"])
                    if atual:
                        st.session_state.conversa_id = None
                        st.session_state.mensagens = []
                    st.rerun()

        if st.session_state.mensagens:
            md = ["# Conversa — SentinelaSOC", ""]
            for m in st.session_state.mensagens:
                quem = "**Analista**" if m["role"] == "user" else "**SentinelaSOC**"
                md.append(f"{quem}\n\n{m['content']}\n")
            st.download_button(
                "Exportar conversa atual (.md)",
                data="\n".join(md),
                file_name=f"conversa-{datetime.date.today():%Y%m%d}.md",
                use_container_width=True,
            )

    # ── Perfil do analista (memoria semantica) ──
    with col2:
        st.markdown("<div class='panel-h'>Perfil do analista</div>", unsafe_allow_html=True)
        fatos = st.session_state.perfil_fatos
        if fatos:
            st.markdown(
                "<div class='side-note'>Fatos duradouros aprendidos nas conversas. "
                "Eles personalizam as respostas e ficam apenas neste dispositivo.</div>",
                unsafe_allow_html=True,
            )
            for fato in fatos:
                st.markdown(f"<div class='fact'>{fato}</div>", unsafe_allow_html=True)
            if st.button("Esquecer tudo", use_container_width=True):
                memory.limpar_perfil()
                st.session_state.perfil_fatos = []
                st.rerun()
        else:
            st.markdown(
                "<div class='side-note'>Ainda não aprendi nada duradouro sobre você. "
                "Conforme conversamos, captarei preferências e contexto de trabalho.</div>",
                unsafe_allow_html=True,
            )
