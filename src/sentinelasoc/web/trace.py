"""Formatacao pura dos eventos de rastro para exibicao (sem Streamlit)."""


def formatar_evento(item: dict) -> tuple[str, str] | None:
    """Converte um evento de trace em (chip, texto) legivel; None para ocultar.

    Chip e a classe visual (tk-*); texto e o conteudo humano. Nunca expoe o dict
    cru — eventos desconhecidos viram resumo curto.
    """
    tipo = str(item.get("tipo", "?"))
    if tipo == "request":
        return None
    if tipo == "tempo":
        etapa = str(item.get("etapa", "etapa"))
        try:
            seg = float(item.get("segundos", 0))
        except (TypeError, ValueError):
            seg = 0.0
        return "tempo", f"{etapa} · {seg:.1f}s"
    if tipo == "sql":
        return "sql", f"{str(item.get('sql', ''))[:130]} · {item.get('linhas', 0)} linha(s)"
    if tipo == "rag":
        consulta = str(item.get("consulta", ""))[:60]
        return "rag", f"consulta: {consulta} · {item.get('chunks', 0)} trechos"
    if tipo == "ml":
        filtro = str(item.get("filtro", ""))[:60]
        prob = item.get("prob_media")
        prev = f"{float(prob):.0f}%" if isinstance(prob, (int, float)) else "—"
        return "ml", f"filtro: {filtro} · {item.get('incidentes', 0)} incidentes · FP médio {prev}"
    if tipo == "ctx":
        return "ctx", f"seguimento reformulado → {str(item.get('reescrita', ''))[:90]}"
    if tipo in ("retry", "erro"):
        return tipo, str(item.get("detalhe", ""))[:120]
    if tipo == "direto":
        return "direto", str(item.get("decisao", ""))[:90]
    # desconhecido: resumo curto e legivel, nunca o dict cru
    return tipo, " · ".join(f"{k}={str(v)[:40]}" for k, v in item.items() if k != "tipo")
