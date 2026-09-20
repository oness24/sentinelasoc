"""Orquestracao do agente: roteia perguntas entre RAG, SQL e resposta direta.

Design:
- O cliente LLM e injetado (Protocol `LLMClient`), viabilizando testes unitarios sem rede.
- Cada resposta produz um `trace` auditavel: decisao de roteamento, SQL executado,
  fontes RAG, tempos por etapa e falhas de ferramenta.
- Falha em uma ferramenta nao derruba a resposta: o erro entra no contexto e o
  LLM final responde com a limitacao explicita.
"""

import json
import re
from collections.abc import Iterator

from sentinelasoc import db, rag
from sentinelasoc.llm import LLMClient, OpenAILLMClient
from sentinelasoc.prompts import (
    FACTS_PROMPT,
    FINAL_PROMPT,
    REWRITE_PROMPT,
    ROUTER_PROMPT,
    SQL_PROMPT,
    SYSTEM_PROMPT,
)
from sentinelasoc.telemetry import get_logger, request_context, timed

log = get_logger(__name__)
MAX_HISTORIA = 6

# Perguntas que exigem razao (divisao) na consulta
_RE_TAXA = re.compile(r"\b(taxa|percentual|propor[cç][ãa]o|porcentagem)\b", re.IGNORECASE)

# Guarda de dominio: termos de seguranca que JAMAIS respondem 'direto'
_RE_DOMINIO = re.compile(
    r"\b(incidente|phishing|malware|ddos|ransomware|vulnerabilidad\w*|cve\b|cvss|"
    r"senha|password|pol[ií]tica|playbook|ataque|breach|exfiltr\w*|amea[çc]a|"
    r"exploit|patch|mitre|t[áa]tica|lgpd|anpd|triagem|severidade|falsos? positiv\w*|"
    r"incident|attack|threat|breached?)\b",
    re.IGNORECASE,
)


def _exige_razao(pergunta: str, sql: str) -> bool:
    """Heuristica: pergunta pede taxa/percentual mas o SQL nao calcula divisao alguma."""
    return bool(_RE_TAXA.search(pergunta)) and "/" not in sql


def _denominador_suspeito(sql: str) -> bool:
    """Heuristica: numerador filtra um grupo (2+ condicoes no CASE) mas o denominador
    e um COUNT(*) sem filtro — razao com escopo errado."""
    if "/" not in sql or "COUNT(*)" not in sql.upper():
        return False
    denominador_limpo = re.sub(r"\s+", "", sql.upper()).count("/COUNT(*)")
    if not denominador_limpo:
        return False
    caso = re.search(r"CASE WHEN ([^)]+)", sql, re.IGNORECASE)
    if not caso:
        return False
    return caso.group(1).upper().count(" AND ") >= 1


def extrair_json(texto: str) -> dict:
    """Extrai o primeiro objeto JSON valido de uma resposta do LLM."""
    match = re.search(r"\{.*\}", texto, re.DOTALL)
    if not match:
        raise ValueError(f"Resposta sem JSON: {texto[:200]}")
    return json.loads(match.group(0))


def _historico_mensagens(history: list[dict]) -> list[dict]:
    msgs = []
    for m in history[-MAX_HISTORIA:]:
        conteudo = m.get("content", "")
        if conteudo:
            papel = "user" if m.get("role") == "user" else "assistant"
            msgs.append({"role": papel, "content": conteudo})
    return msgs


def _historico_texto(history: list[dict]) -> str:
    """Historico compacto para prompts de reescrita (papel: conteudo)."""
    linhas = []
    for m in history[-MAX_HISTORIA:]:
        conteudo = str(m.get("content", "")).strip()
        if conteudo:
            papel = "analista" if m.get("role") == "user" else "assistente"
            linhas.append(f"{papel}: {conteudo[:300]}")
    return "\n".join(linhas)


def _reformular(pergunta: str, history: list[dict], cliente: LLMClient) -> str:
    """Reescreve um seguimento em pergunta autonoma (resolve referencias)."""
    if not history:
        return pergunta
    plano = extrair_json(
        cliente.complete(
            [
                {
                    "role": "system",
                    "content": REWRITE_PROMPT.format(
                        historico=_historico_texto(history), pergunta=pergunta
                    ),
                },
                {"role": "user", "content": pergunta},
            ],
            temperature=0.0,
            max_tokens=400,
            json_mode=True,
        )
    )
    independente = str(plano.get("pergunta_independente", pergunta)).strip()
    return independente or pergunta


def _executar_sql(
    pergunta: str, trace: list[dict], cliente: LLMClient, history: list[dict], original: str = ""
) -> str:
    """Gera SQL via LLM, valida contra o guarda somente-leitura e executa no DuckDB.

    Auto-correcao: erros de execucao (coluna inexistente, sintaxe) sao devolvidos
    ao LLM para regeneracao, em ate 3 tentativas — padrao text-to-SQL robusto.
    """
    import duckdb

    mensagens = [
        {"role": "system", "content": SQL_PROMPT.format(schema=db.schema_descritivo())},
        *_historico_mensagens(history),
        {"role": "user", "content": pergunta},
    ]
    ultimo_erro: Exception | None = None
    for tentativa in range(3):
        try:
            plano = extrair_json(cliente.complete(mensagens, temperature=0.0, json_mode=True))
            sql = str(plano["sql"]).strip()
        except (ValueError, KeyError) as exc:  # JSON malformado: tenta novamente
            ultimo_erro = exc
            log.warning("sql.retry tentativa=%d erro_json=%s", tentativa + 1, exc)
            trace.append(
                {"tipo": "retry", "detalhe": f"sql json (tentativa {tentativa + 1}): {exc}"}
            )
            mensagens.append(
                {
                    "role": "user",
                    "content": (
                        "A resposta anterior nao foi um JSON valido. "
                        'Responda SOMENTE com JSON: {"sql": "SELECT ..."}'
                    ),
                }
            )
            continue
        if _exige_razao(f"{original} {pergunta}", sql) or _denominador_suspeito(sql):
            motivo = (
                "pergunta pede taxa, consulta nao divide"
                if _exige_razao(f"{original} {pergunta}", sql)
                else "denominador sem o filtro do grupo"
            )
            trace.append(
                {
                    "tipo": "retry",
                    "detalhe": (f"sql (tentativa {tentativa + 1}): {motivo}"),
                }
            )
            mensagens.append({"role": "assistant", "content": sql})
            mensagens.append(
                {
                    "role": "user",
                    "content": (
                        "A pergunta pede uma TAXA/PERCENTUAL, mas a consulta acima nao calcula"
                        " divisao alguma, ou divide pelo escopo errado. A razao deve usar o"
                        " MESMO escopo da pergunta (ex.: taxa DE falsos positivos DE Forca Bruta"
                        " = falsos positivos de Forca Bruta / total de incidentes de Forca Bruta),"
                        " na forma 100.0 * SUM(CASE WHEN cond THEN 1 ELSE 0 END) / COUNT(*). "
                        'Responda SOMENTE com JSON: {"sql": "SELECT ..."}'
                    ),
                }
            )
            continue
        try:
            colunas, linhas = db.run_select(sql)
            log.info("sql.executed linhas=%d sql=%s", len(linhas), sql.replace("\n", " "))
            trace.append({"tipo": "sql", "sql": sql, "linhas": len(linhas)})
            if not linhas and (proximos := db.literal_proximo(sql)):
                literal, sugestao = proximos[0]
                log.info("sql.enum.hint %r -> %r", literal, sugestao)
                trace.append(
                    {
                        "tipo": "retry",
                        "detalhe": (
                            f"sql: zero linhas e literal '{literal}' nao existe na tabela"
                            f" da consulta — valor proximo '{sugestao}'"
                        ),
                    }
                )
                mensagens.append({"role": "assistant", "content": sql})
                mensagens.append(
                    {
                        "role": "user",
                        "content": (
                            f"A consulta retornou ZERO linhas e o valor '{literal}' nao"
                            f" existe nessa tabela — o valor correto provavel e '{sugestao}'."
                            " Corrija a consulta com os valores EXATOS do esquema. "
                            'Responda SOMENTE com JSON: {"sql": "SELECT ..."}'
                        ),
                    }
                )
                continue
            if tentativa:
                trace.append(
                    {"tipo": "direto", "decisao": f"sql autocorrigido na tentativa {tentativa + 1}"}
                )
            return _formatar_resultado(colunas, linhas)
        except duckdb.Error as exc:  # binder/sintaxe/conversao: regenera com o erro
            ultimo_erro = exc
            log.warning("sql.retry tentativa=%d erro=%s", tentativa + 1, exc)
            trace.append({"tipo": "retry", "detalhe": f"sql (tentativa {tentativa + 1}): {exc}"})
            mensagens.append({"role": "assistant", "content": sql})
            mensagens.append(
                {
                    "role": "user",
                    "content": (
                        f"A consulta acima falhou com o erro:\n{exc}\n\n"
                        "Corrija usando EXATAMENTE os nomes de tabelas e colunas do esquema "
                        "(colunas em portugues, ex.: horas_para_resolver). "
                        'Responda novamente SOMENTE com JSON: {"sql": "SELECT ..."}'
                    ),
                }
            )
    raise ValueError(f"SQL falhou apos 3 tentativas: {ultimo_erro}")


def _formatar_resultado(colunas: list[str], linhas: list[tuple]) -> str:
    if not linhas:
        return "Resultado da consulta SQL: nenhum registro encontrado."
    cabecalho = " | ".join(colunas)
    corpo = "\n".join(
        " | ".join("" if v is None else str(v) for v in linha) for linha in linhas[:15]
    )
    extra = f"\n... (+{len(linhas) - 15} linhas)" if len(linhas) > 15 else ""
    resumo = f"Resultado da consulta SQL executada no DuckDB ({len(linhas)} linhas):"
    return f"{resumo}\n{cabecalho}\n{corpo}{extra}"


def _executar_rag(consulta: str, trace: list[dict]) -> str:
    chunks = rag.retrieve(consulta)
    log.info("rag.retrieved k=%d top=%s", len(chunks), chunks[0]["fonte"] if chunks else "-")
    trace.append(
        {
            "tipo": "rag",
            "consulta": consulta,
            "fontes": [f"{c['fonte']} :: {c['secao']} (dist {c['distancia']})" for c in chunks],
        }
    )
    if not chunks:
        return "Busca nos documentos: nenhum trecho relevante encontrado."
    trechos = "\n\n".join(
        f"[Fonte: {c['fonte']} | Secao: {c['secao']}]\n{c['texto']}" for c in chunks
    )
    return f"Trechos dos documentos internos recuperados por busca semantica:\n\n{trechos}"


class AgenteSOC:
    """Agente conversacional com rastreabilidade total das ferramentas usadas."""

    def __init__(self, llm: LLMClient | None = None) -> None:
        self.llm = llm
        self.last_trace: list[dict] = []

    def _cliente(self) -> LLMClient:
        if self.llm is None:
            self.llm = OpenAILLMClient()
        return self.llm

    def answer(
        self,
        pergunta: str,
        history: list[dict] | None = None,
        perfil: list[str] | None = None,
    ) -> Iterator[str]:
        """Gerador que transmite a resposta em streaming e popula `self.last_trace`.

        `perfil` e a memoria semantica do analista (fatos duraveis), injetada na
        resposta final para continuidade entre conversas.
        """
        history = history or []
        self.last_trace = []
        trace = self.last_trace
        cliente = self._cliente()

        with request_context() as rid:
            trace.append({"tipo": "request", "id": rid})
            log.info("request.start pergunta=%r", pergunta[:120])
            total = 0
            for chunk in self._answer_com_contexto(pergunta, history, trace, cliente, perfil):
                total += len(chunk)
                yield chunk
            log.info("request.done chars=%d", total)

    def extrair_fatos(self, pergunta: str, resposta: str) -> list[str]:
        """Extrai fatos duraveis sobre o analista de uma troca (memoria semantica)."""
        cliente = self._cliente()
        try:
            plano = extrair_json(
                cliente.complete(
                    [
                        {
                            "role": "system",
                            "content": FACTS_PROMPT.format(
                                pergunta=pergunta[:800], resposta=resposta[:1500]
                            ),
                        },
                        {"role": "user", "content": "extrair"},
                    ],
                    temperature=0.0,
                    max_tokens=400,
                    json_mode=True,
                )
            )
            fatos = [str(f).strip() for f in plano.get("fatos", []) if str(f).strip()]
            log.info("memory.facts.extracted n=%d", len(fatos))
            return fatos[:4]
        except (ValueError, KeyError) as exc:
            log.warning("memory.facts.failed erro=%s", exc)
            return []

    def _answer_com_contexto(
        self,
        pergunta: str,
        history: list[dict],
        trace: list[dict],
        cliente: LLMClient,
        perfil: list[str] | None = None,
    ) -> Iterator[str]:
        # 0) Seguimentos: reescreve a pergunta em forma autonoma
        pergunta_efetiva = pergunta
        if history:
            with timed("reformulacao", trace):
                try:
                    pergunta_efetiva = _reformular(pergunta, history, cliente)
                except (ValueError, KeyError) as exc:
                    log.warning("rewrite.failed erro=%s", exc)
            if pergunta_efetiva != pergunta:
                trace.append(
                    {"tipo": "contexto", "seguimento": True, "reescrita": pergunta_efetiva}
                )
                log.info("rewrite.done pergunta=%r -> %r", pergunta, pergunta_efetiva[:100])

        # 1) Roteamento (sem streaming, temperatura 0, JSON estrito)
        with timed("roteamento", trace):
            try:
                rota = extrair_json(
                    cliente.complete(
                        [
                            {"role": "system", "content": ROUTER_PROMPT},
                            *_historico_mensagens(history),
                            {"role": "user", "content": pergunta_efetiva},
                        ],
                        temperature=0.0,
                        json_mode=True,
                    )
                )
            except (ValueError, KeyError) as exc:
                # roteamento mal-sucedido: degrada com mensagem util em vez de estourar
                log.warning("route.failed erro=%s", exc)
                trace.append({"tipo": "erro", "detalhe": f"roteamento: {exc}"})
                yield (
                    "Nao consegui estruturar a consulta agora. "
                    "Tente reformular a pergunta (ex.: cite o tipo de incidente ou o documento)."
                )
                return

        log.info(
            "route.decided acao=%s ferramentas=%s",
            rota.get("acao"),
            [f.get("tipo") for f in rota.get("ferramentas", [])],
        )

        # 1b) Guarda de dominio: pergunta de seguranca jamais responde 'direto'
        # (o roteador 7B varia entre execucoes; a guarda e deterministica).
        if rota.get("acao") == "direto" and _RE_DOMINIO.search(pergunta_efetiva):
            log.info("route.guard dominio=true acao=direto — reconsultando")
            trace.append(
                {
                    "tipo": "retry",
                    "detalhe": "rota 'direto' em pergunta de domínio — reconsultando roteador",
                }
            )
            with timed("roteamento-guarda", trace):
                try:
                    rota2 = extrair_json(
                        cliente.complete(
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
            if rota2.get("acao") == "direto":
                rota = {
                    "acao": "consultar",
                    "ferramentas": [{"tipo": "rag", "consulta": pergunta_efetiva}],
                }
                trace.append(
                    {"tipo": "direto", "decisao": "rota corrigida para RAG pela guarda de domínio"}
                )
                log.info("route.guard forcou rag")
            else:
                rota = rota2
                log.info(
                    "route.guard corrigido pelo roteador ferramentas=%s",
                    [f.get("tipo") for f in rota.get("ferramentas", [])],
                )

        if rota.get("acao") == "direto":
            trace.append({"tipo": "direto", "decisao": "resposta direta sem ferramentas"})
            yield rota.get("resposta", "Como posso ajudar na triagem?")
            return

        # 2) Execucao das ferramentas escolhidas
        partes: list[str] = []
        for ferramenta in rota.get("ferramentas", []):
            tipo = str(ferramenta.get("tipo", ""))
            try:
                with timed(f"ferramenta:{tipo}", trace):
                    if tipo == "sql":
                        partes.append(
                            _executar_sql(
                                str(ferramenta.get("pergunta", pergunta_efetiva)),
                                trace,
                                cliente,
                                history,
                                original=pergunta_efetiva,
                            )
                        )
                    elif tipo == "rag":
                        partes.append(
                            _executar_rag(str(ferramenta.get("consulta", pergunta_efetiva)), trace)
                        )
            except Exception as exc:  # falha isolada nao derruba a resposta
                log.warning("tool.failed tipo=%s erro=%s", tipo, exc)
                trace.append({"tipo": "erro", "detalhe": f"{tipo}: {exc}"})
                partes.append(f"Ferramenta {tipo} falhou: {exc}")

        contexto = "\n\n---\n\n".join(partes) if partes else "Nenhuma ferramenta retornou contexto."

        # 3) Resposta final com streaming (perfil do analista = memoria de longo prazo)
        system = SYSTEM_PROMPT
        if perfil:
            system += (
                "\n\nMEMORIA DE LONGO PRAZO DO ANALISTA (aprendida em conversas anteriores):\n"
            )
            system += "\n".join(f"- {f}" for f in perfil[:12])
        mensagens = [
            {"role": "system", "content": system},
            *_historico_mensagens(history),
            {"role": "user", "content": FINAL_PROMPT.format(pergunta=pergunta, contexto=contexto)},
        ]
        yield from cliente.stream(mensagens)
