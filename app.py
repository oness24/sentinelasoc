"""SentinelaSOC — interface web (Streamlit).

Arquitetura de pagina unica com roteamento por query param (?page=):
mais controle sobre navegacao, sessao e design do que o modo multipagina
automatico, e sem depender de APIs experimentais de troca de pagina.
"""

import streamlit as st

st.set_page_config(
    page_title="SentinelaSOC",
    page_icon="static/favicon.svg",
    layout="wide",
    initial_sidebar_state="expanded",
)

from sentinelasoc.web import copiloto, memoria, painel  # noqa: E402
from sentinelasoc.web.shell import inject_css, sidebar_shell  # noqa: E402

PAGINAS = {
    "copiloto": ("Copiloto", copiloto.render),
    "painel": ("Painel", painel.render),
    "memoria": ("Memória", memoria.render),
}

inject_css()
chave = st.query_params.get("page", "copiloto")
titulo, renderizar = PAGINAS.get(chave, PAGINAS["copiloto"])

with st.sidebar:
    sidebar_shell(chave)

renderizar()
