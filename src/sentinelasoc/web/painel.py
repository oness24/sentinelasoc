"""Pagina Painel: metricas operacionais do SOC direto do DuckDB."""

import pandas as pd
import streamlit as st

from sentinelasoc import db
from sentinelasoc.web.shell import app_bar


def _um(sql: str):
    _, linhas = db.run_select(sql)
    return linhas[0][0] if linhas else 0


def render() -> None:
    app_bar("Painel")

    abertos = _um("SELECT COUNT(*) FROM incidentes WHERE status IN ('Aberto','Em atendimento')")
    criticos = _um(
        "SELECT COUNT(*) FROM incidentes WHERE severidade='Critica' "
        "AND status IN ('Aberto','Em atendimento')"
    )
    fp = _um(
        "SELECT ROUND(100.0*SUM(CASE WHEN falso_positivo='Sim' THEN 1 ELSE 0 END)"
        "/COUNT(*),1) FROM incidentes"
    )
    vulns = _um("SELECT COUNT(*) FROM vulnerabilidades WHERE cvss >= 9.0 AND status = 'Aberta'")
    mttr = _um("SELECT ROUND(AVG(horas_para_resolver),1) FROM incidentes WHERE status='Resolvido'")

    st.markdown(
        f"""
        <div class="metric-grid">
          <div class="metric"><div class="label">Incidentes abertos</div>
            <div class="value">{abertos}</div>
            <div class="sub">abertos + em atendimento</div></div>
          <div class="metric"><div class="label">Críticos ativos</div>
            <div class="value {"crit" if criticos else "ok"}">{criticos}</div>
            <div class="sub">severidade crítica</div></div>
          <div class="metric"><div class="label">Taxa de falso positivo</div>
            <div class="value {"warn" if fp and float(fp) > 25 else ""}">{fp}%</div>
            <div class="sub">histórico completo</div></div>
          <div class="metric"><div class="label">CVEs críticas abertas</div>
            <div class="value {"warn" if vulns > 5 else "ok"}">{vulns}</div>
            <div class="sub">CVSS ≥ 9.0 e status aberta</div></div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.markdown("<div class='panel-h'>Incidentes por tipo</div>", unsafe_allow_html=True)
    _, linhas = db.run_select(
        "SELECT tipo, COUNT(*) AS total FROM incidentes GROUP BY tipo ORDER BY total DESC"
    )
    df = pd.DataFrame(linhas, columns=["tipo", "total"])
    st.bar_chart(df.set_index("tipo"), color="#8b7dfb", height=260)

    col1, col2 = st.columns(2)
    with col1:
        st.markdown("<div class='panel-h'>Evolução mensal</div>", unsafe_allow_html=True)
        _, linhas_mes = db.run_select(
            "SELECT strftime(data_abertura, '%Y-%m') AS mes, COUNT(*) AS total "
            "FROM incidentes GROUP BY 1 ORDER BY 1"
        )
        dfm = pd.DataFrame(linhas_mes, columns=["mes", "total"])
        st.line_chart(dfm.set_index("mes"), color="#c2ef4e", height=220)
    with col2:
        st.markdown("<div class='panel-h'>Falsos positivos por tipo</div>", unsafe_allow_html=True)
        _, linhas_fp = db.run_select(
            "SELECT tipo, ROUND(100.0*SUM(CASE WHEN falso_positivo='Sim' THEN 1 ELSE 0 END)"
            "/COUNT(*),1) AS taxa FROM incidentes GROUP BY tipo ORDER BY taxa DESC"
        )
        dff = pd.DataFrame(linhas_fp, columns=["tipo", "taxa"])
        st.bar_chart(dff.set_index("tipo"), color="#ffb287", height=220)

    st.markdown(
        f"<div class='panel-h'>Top ativos por incidentes · MTTR global {mttr}h</div>",
        unsafe_allow_html=True,
    )
    _, linhas_ativos = db.run_select(
        "SELECT a.hostname, a.ambiente, COUNT(*) AS incidentes, "
        "ROUND(100.0*SUM(CASE WHEN i.falso_positivo='Sim' THEN 1 ELSE 0 END)/COUNT(*),0) AS fp "
        "FROM incidentes i JOIN ativos a USING (ativo_id) "
        "GROUP BY 1, 2 ORDER BY incidentes DESC LIMIT 10"
    )
    st.dataframe(
        pd.DataFrame(linhas_ativos, columns=["ativo", "ambiente", "incidentes", "fp_%"]),
        use_container_width=True,
        hide_index=True,
    )
