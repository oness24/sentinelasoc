"""Tripulacao (crew) do SentinelaSOC: dois agentes especializados no mesmo chat.

Padrao CrewAI-equivalente, documentado no ARCHITECTURE.md (ADR 12):
- AGENTE TRIADOR: reescreve seguimentos, decide as evidencias necessarias
  (roteamento RAG/SQL/ML), coleta e monta o dossie. E o unico que fala com
  as ferramentas.
- AGENTE REDATOR: recebe o dossie + guardrails de redacao e produz a resposta
  final ao analista, com streaming.

A orquestracao e leve (sem framework externo): as etapas ficam no mesmo chat,
com a entrega entre agentes visivel no rastro (`tipo: "agente"`), e cada fase
rotulada para a instrumentacao (agente/etapa em `instrumentacao.py`).
"""

from collections.abc import Iterator

from sentinelasoc.agent import (
    _RE_DOMINIO,
    _RE_PREVISAO_FP,
    _executar_ml,
    _executar_rag,
    _executar_sql,
    _historico_mensagens,
    _reformular,
    extrair_json,
)
from sentinelasoc.instrumentacao import contexto_llm
from sentinelasoc.llm import LLMClient
from sentinelasoc.prompts import (
    FINAL_PROMPT,
    REDATOR_PROMPT,
    ROUTER_PROMPT,
    SYSTEM_PROMPT,
    TRIADOR_PROMPT,
)
from sentinelasoc.telemetry import get_logger, timed

log = get_logger(__name__)

Papel = str  # "triador" | "redator" — rotulo curto para trace/instrumentacao


class AgenteTriador:
    """Especialista em evidencias: decide ferramentas e coleta o dossie.

    Conversa social curta ("oi", "obrigado") e respondida pelo proprio triador,
    sem acionar o redator — decisao visivel no rastro (`decisao: resposta direta`).
    """

    def __init__(self, cliente: LLMClient) -> None:
        self.cliente = cliente

    def coletar(
        self,
        pergunta: str,
        pergunta_efetiva: str,
        history: list[dict],
        trace: list[dict],
    ) -> tuple[str | None, str]:
        """Executa a fase de coleta. Retorna (resposta_direta | None, dossie).

        `resposta_direta` não-None significa que o redator não é necessário
        (conversa social); `dossie` é o contexto de evidências para o redator.
        """
        # 0) Seguimentos: reescreve a pergunta em forma autonoma
        pergunta_efetiva = self._reformular_se_necessario(
            pergunta, pergunta_efetiva, history, trace
        )

        # 1) Decisao de evidencias (roteamento): JSON estrito, temperatura 0
        rota = self._decidir(pergunta_efetiva, history, trace)
        if rota is None:  # roteamento mal-sucedido: mensagem util, sem estourar
            return (
                "Nao consegui estruturar a consulta agora. "
                "Tente reformular a pergunta (ex.: cite o tipo de incidente ou o documento).",
                "",
            )

        # 1b) Guarda de dominio: pergunta de seguranca jamais responde 'direto'
        rota = self._guarda_dominio(rota, pergunta_efetiva, trace)

        if rota.get("acao") == "direto":
            trace.append({"tipo": "direto", "decisao": "resposta direta sem ferramentas"})
            return str(rota.get("resposta", "Como posso ajudar na triagem?")), ""

        # 2) Execucao das ferramentas escolhidas — somente o triador coleta
        partes: list[str] = []
        for ferramenta in rota.get("ferramentas", []):
            tipo = str(ferramenta.get("tipo", ""))
            try:
                with contexto_llm(agente="triador", etapa=tipo), timed(f"ferramenta:{tipo}", trace):
                    if tipo == "sql":
                        partes.append(
                            _executar_sql(
                                str(ferramenta.get("pergunta", pergunta_efetiva)),
                                trace,
                                self.cliente,
                                history,
                                original=pergunta_efetiva,
                            )
                        )
                    elif tipo == "rag":
                        partes.append(
                            _executar_rag(str(ferramenta.get("consulta", pergunta_efetiva)), trace)
                        )
                    elif tipo == "ml":
                        partes.append(
                            _executar_ml(str(ferramenta.get("consulta", pergunta_efetiva)), trace)
                        )
            except Exception as exc:  # falha isolada nao derruba a resposta
                log.warning("tool.failed tipo=%s erro=%s", tipo, exc)
                trace.append({"tipo": "erro", "detalhe": f"{tipo}: {exc}"})
                partes.append(f"Ferramenta {tipo} falhou: {exc}")

        dossie = "\n\n---\n\n".join(partes) if partes else "Nenhuma ferramenta retornou contexto."
        usadas = sorted({f.get("tipo", "?") for f in rota.get("ferramentas", [])})
        ferramentas_txt = ", ".join(usadas) or "sem ferramentas"
        trace.append(
            {
                "tipo": "agente",
                "papel": "triador",
                "acao": f"dossiê de evidências entregue ao redator ({ferramentas_txt})",
            }
        )
        return None, dossie

    def _reformular_se_necessario(
        self, pergunta: str, pergunta_efetiva: str, history: list[dict], trace: list[dict]
    ) -> str:
        if not history:
            return pergunta_efetiva
        with timed("reformulacao", trace):
            try:
                with contexto_llm(agente="triador", etapa="reformulacao"):
                    pergunta_efetiva = _reformular(pergunta, history, self.cliente)
            except (ValueError, KeyError) as exc:
                log.warning("rewrite.failed erro=%s", exc)
        if pergunta_efetiva != pergunta:
            trace.append({"tipo": "contexto", "seguimento": True, "reescrita": pergunta_efetiva})
            log.info("rewrite.done pergunta=%r -> %r", pergunta, pergunta_efetiva[:100])
        return pergunta_efetiva

    def _decidir(
        self, pergunta_efetiva: str, history: list[dict], trace: list[dict]
    ) -> dict | None:
        with timed("roteamento", trace):
            try:
                with contexto_llm(agente="triador", etapa="roteamento"):
                    return extrair_json(
                        self.cliente.complete(
                            [
                                {"role": "system", "content": TRIADOR_PROMPT},
                                *_historico_mensagens(history),
                                {"role": "user", "content": pergunta_efetiva},
                            ],
                            temperature=0.0,
                            json_mode=True,
                        )
                    )
            except (ValueError, KeyError) as exc:
                log.warning("route.failed erro=%s", exc)
                trace.append({"tipo": "erro", "detalhe": f"roteamento: {exc}"})
                return None

    def _guarda_dominio(self, rota: dict, pergunta_efetiva: str, trace: list[dict]) -> dict:
        """O roteador 7B varia entre execucoes; a guarda e deterministica."""
        if rota.get("acao") != "direto" or not _RE_DOMINIO.search(pergunta_efetiva):
            return rota
        log.info("route.guard dominio=true acao=direto — reconsultando")
        trace.append(
            {
                "tipo": "retry",
                "detalhe": "rota 'direto' em pergunta de domínio — reconsultando roteador",
            }
        )
        with timed("roteamento-guarda", trace):
            try:
                with contexto_llm(agente="triador", etapa="roteamento"):
                    rota2 = extrair_json(
                        self.cliente.complete(
                            [
                                {"role": "system", "content": ROUTER_PROMPT},
                                {
                                    "role": "user",
                                    "content": (
                                        f"{pergunta_efetiva}\n\n"
                                        "ATENCAO: esta pergunta e do dominio de seguranca "
                                        'e EXIGE ferramentas. Nao use "direto".'
                                    ),
                                },
                            ],
                            temperature=0.0,
                            json_mode=True,
                        )
                    )
            except (ValueError, KeyError):
                rota2 = {"acao": "direto"}
        if rota2.get("acao") != "direto":
            log.info(
                "route.guard corrigido pelo roteador ferramentas=%s",
                [f.get("tipo") for f in rota2.get("ferramentas", [])],
            )
            return rota2
        if _RE_PREVISAO_FP.search(pergunta_efetiva):
            trace.append(
                {"tipo": "direto", "decisao": "rota corrigida para ML pela guarda de domínio"}
            )
            log.info("route.guard forcou ml (intencao de previsao de falso positivo)")
            return {
                "acao": "consultar",
                "ferramentas": [{"tipo": "ml", "consulta": pergunta_efetiva}],
            }
        trace.append(
            {"tipo": "direto", "decisao": "rota corrigida para RAG pela guarda de domínio"}
        )
        log.info("route.guard forcou rag")
        return {
            "acao": "consultar",
            "ferramentas": [{"tipo": "rag", "consulta": pergunta_efetiva}],
        }


class AgenteRedator:
    """Especialista em resposta: transforma o dossie do triador em resposta final."""

    def __init__(self, cliente: LLMClient) -> None:
        self.cliente = cliente

    def redigir(
        self,
        pergunta: str,
        history: list[dict],
        dossie: str,
        trace: list[dict],
        perfil: list[str] | None = None,
    ) -> Iterator[str]:
        trace.append(
            {
                "tipo": "agente",
                "papel": "redator",
                "acao": "redigindo resposta com guardrails",
            }
        )
        system = SYSTEM_PROMPT + "\n\n" + REDATOR_PROMPT
        if perfil:
            system += (
                "\n\nMEMORIA DE LONGO PRAZO DO ANALISTA (aprendida em conversas anteriores):\n"
            )
            system += "\n".join(f"- {f}" for f in perfil[:12])
        mensagens = [
            {"role": "system", "content": system},
            *_historico_mensagens(history),
            {"role": "user", "content": FINAL_PROMPT.format(pergunta=pergunta, contexto=dossie)},
        ]
        with contexto_llm(agente="redator", etapa="redacao"):
            yield from self.cliente.stream(mensagens)


class EquipeSOC:
    """Dois agentes especializados conversando no mesmo chat (CrewAI-equivalente).

    Orquestracao explicita e auditavel: cada fase rotula agente/etapa para a
    instrumentacao e o rastro registra a entrega triador -> redator.
    """

    def __init__(self, triador: AgenteTriador, redator: AgenteRedator) -> None:
        self.triador = triador
        self.redator = redator
        self.last_contexto: str = ""  # dossie da ultima resposta (para avaliacao)

    def answer(
        self,
        pergunta: str,
        history: list[dict],
        trace: list[dict],
        cliente: LLMClient,
        perfil: list[str] | None = None,
    ) -> Iterator[str]:
        """Fluxo completo: triador coleta -> redator redige (streaming)."""
        self.last_contexto = ""
        trace.append({"tipo": "agente", "papel": "triador", "acao": "coletando evidências"})
        direta, dossie = self.triador.coletar(pergunta, pergunta, history, trace)
        if direta is not None:
            yield direta
            return
        self.last_contexto = dossie
        yield from self.redator.redigir(pergunta, history, dossie, trace, perfil)
