"""Pagina Observabilidade: diario de chamadas LLM (equivalente-local ao Langfuse).

KPIs de volume/latencia/sucesso, quebra por agente+etapa do pipeline e as
chamadas recentes com request_id — a mesma correlacao dos logs, agora em painel.
"""

import streamlit as st

from sentinelasoc import instrumentacao
from sentinelasoc.web.shell import app_bar


def _fmt_ms(ms: object) -> str:
    try:
        v = float(str(ms))
    except (TypeError, ValueError):
        return "—"
    return f"{v / 1000:.2f}s" if v >= 1000 else f"{v:.0f}ms"


def _fmt_tokens(n: object) -> str:
    if n is None:
        return "—"
    try:
        v = int(str(n))
    except (TypeError, ValueError):
        return "—"
    return f"{v / 1000:.1f}k" if v >= 1000 else str(v)


def _metrica(label: str, valor: str, sub: str = "") -> None:
    sub_html = f"<div class='sub'>{sub}</div>" if sub else ""
    st.markdown(
        f"<div class='metric'><div class='label microlabel'>{label}</div>"
        f"<div class='value'>{valor}</div>{sub_html}</div>",
        unsafe_allow_html=True,
    )


def render() -> None:
    app_bar("Observabilidade")
    resumo = instrumentacao.resumo()

    if not resumo["chamadas"]:
        st.markdown(
            "<div class='hero' style='padding-top:12vh'><div class='microlabel' "
            "style='color:#f5b800'>Instrumentação</div><h1>Diário de chamadas LLM</h1>"
            "<p>Nenhuma chamada registrada ainda. Pergunte algo no "
            "<b>Copiloto</b> — cada chamada de LLM (roteamento, ferramentas, redação)"
            " é registrada aqui com agente, etapa, latência, tokens e status.</p></div>",
            unsafe_allow_html=True,
        )
        return

    taxa_ok = resumo["ok"] / resumo["chamadas"] * 100
    st.markdown(
        "<div class='microlabel' style='color:#f5b800'>Instrumentação · SQLite local</div>",
        unsafe_allow_html=True,
    )
    st.markdown("## Diário de chamadas LLM")
    st.markdown(
        "<p style='color:var(--text-2);font-size:13.5px;margin-top:-4px'>"
        "Cada chamada do pipeline — do roteamento do <b>triador</b> à redação do "
        "<b>redator</b> — com request_id correlacionado aos logs "
        "(<code>logs/sentinelasoc.log</code>).</p>",
        unsafe_allow_html=True,
    )

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        _metrica(
            "Chamadas",
            f"{resumo['chamadas']:,}".replace(",", "."),
            f"{resumo['requests']} requests",
        )
    with c2:
        _metrica(
            "Sucesso",
            f"{taxa_ok:.0f}%",
            f"{resumo['falhas']} falha(s)",
        )
    with c3:
        _metrica(
            "Latência média",
            _fmt_ms(resumo["latencia_media"]),
            f"pico {_fmt_ms(resumo['latencia_max'])}",
        )
    with c4:
        pt, ct = resumo["prompt_tokens"], resumo["completion_tokens"]
        total = (pt or 0) + (ct or 0)
        sub = (
            f"in {_fmt_tokens(pt)} · out {_fmt_tokens(ct)}"
            if pt is not None
            else "streaming não conta tokens"
        )
        _metrica("Tokens", _fmt_tokens(total) if pt is not None else "—", sub)

    st.markdown("<div class='panel-h'>Por agente · etapa</div>", unsafe_allow_html=True)
    etapas = instrumentacao.por_etapa()
    if etapas:
        cab = (
            "<div class='trace-row'>"
            "<span class='k tk-agente' style='flex:0 0 150px'>AGENTE</span>"
            "<span class='k tk-meta' style='flex:0 0 130px'>ETAPA</span>"
            "<span class='k tk-meta' style='flex:0 0 80px'>CHAMADAS</span>"
            "<span class='k tk-meta' style='flex:0 0 110px'>LATÊNCIA MÉD</span>"
            "<span class='v'>OK</span></div>"
        )
        linhas = [cab]
        for e in etapas:
            lat = _fmt_ms(e["latencia_media"])
            linhas.append(
                "<div class='trace-row'>"
                f"<span class='k tk-agente' style='flex:0 0 150px'>{e['agente']}</span>"
                f"<span class='k tk-meta' style='flex:0 0 130px'>{e['etapa']}</span>"
                f"<span class='k tk-meta' style='flex:0 0 80px'>{e['chamadas']}</span>"
                f"<span class='k tk-meta' style='flex:0 0 110px'>{lat}</span>"
                f"<span class='v'>{e['ok']}/{e['chamadas']}</span></div>"
            )
        st.markdown("".join(linhas), unsafe_allow_html=True)

    st.markdown("<div class='panel-h'>Chamadas recentes</div>", unsafe_allow_html=True)
    ultimas = instrumentacao.ultimas(20)
    if ultimas:
        cab = (
            "<div class='trace-row'>"
            "<span class='k tk-meta' style='flex:0 0 70px'>REQ</span>"
            "<span class='k tk-agente' style='flex:0 0 150px'>AGENTE</span>"
            "<span class='k tk-meta' style='flex:0 0 120px'>ETAPA</span>"
            "<span class='k tk-meta' style='flex:0 0 90px'>LATÊNCIA</span>"
            "<span class='k tk-meta' style='flex:0 0 80px'>TOKENS</span>"
            "<span class='v'>STATUS</span></div>"
        )
        linhas = [cab]
        for u in ultimas:
            status = "ok" if u["sucesso"] else f"falhou · {str(u['erro'] or '')[:60]}"
            tokens = (
                f"{u['prompt_tokens'] or '—'}/{u['completion_tokens'] or '—'}"
                if u["prompt_tokens"] is not None or u["completion_tokens"] is not None
                else "—"
            )
            linhas.append(
                "<div class='trace-row'>"
                f"<span class='k tk-meta' style='flex:0 0 70px'>{u['request_id']}</span>"
                f"<span class='k tk-agente' style='flex:0 0 150px'>{u['agente']}</span>"
                f"<span class='k tk-meta' style='flex:0 0 120px'>{u['etapa']}</span>"
                f"<span class='k tk-meta' style='flex:0 0 90px'>{_fmt_ms(u['duracao_ms'])}</span>"
                f"<span class='k tk-meta' style='flex:0 0 80px'>{tokens}</span>"
                f"<span class='v'>{status}</span></div>"
            )
        st.markdown("".join(linhas), unsafe_allow_html=True)
    st.markdown(
        "<div class='side-note'>Diário em <code>sentinelasoc.db</code> (tabela "
        "<code>llm_chamadas</code>) · correlação por request_id com "
        "<code>logs/sentinelasoc.log</code> · streaming não expõe tokens na API OpenAI.</div>",
        unsafe_allow_html=True,
    )
