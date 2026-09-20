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
from sentinelasoc.prompts import FINAL_PROMPT, ROUTER_PROMPT, SQL_PROMPT, SYSTEM_PROMPT
from sentinelasoc.telemetry import get_logger, timed

log = get_logger(__name__)
MAX_HISTORIA = 6


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


def _executar_sql(pergunta: str, trace: list[dict], cliente: LLMClient) -> str:
    """Gera SQL via LLM, valida contra o guarda somente-leitura e executa no DuckDB."""
    s_json = {"role": "system", "content": SQL_PROMPT.format(schema=db.schema_descritivo())}
    plano = extrair_json(
        cliente.complete([s_json, {"role": "user", "content": pergunta}], temperature=0.0)
    )
    sql = str(plano["sql"]).strip()
    colunas, linhas = db.run_select(sql)
    trace.append({"tipo": "sql", "sql": sql, "linhas": len(linhas)})

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

    def answer(self, pergunta: str, history: list[dict] | None = None) -> Iterator[str]:
        """Gerador que transmite a resposta em streaming e popula `self.last_trace`."""
        history = history or []
        self.last_trace = []
        trace = self.last_trace
        cliente = self._cliente()

        # 1) Roteamento (sem streaming, temperatura 0, JSON estrito)
        with timed("roteamento", trace):
            try:
                rota = extrair_json(
                    cliente.complete(
                        [
                            {"role": "system", "content": ROUTER_PROMPT},
                            *_historico_mensagens(history),
                            {"role": "user", "content": pergunta},
                        ],
                        temperature=0.0,
                        max_tokens=300,
                    )
                )
            except (ValueError, KeyError) as exc:
                # roteamento mal-sucedido: degrada com mensagem util em vez de estourar
                log.warning("roteamento falhou: %s", exc)
                trace.append({"tipo": "erro", "detalhe": f"roteamento: {exc}"})
                yield (
                    "Nao consegui estruturar a consulta agora. "
                    "Tente reformular a pergunta (ex.: cite o tipo de incidente ou o documento)."
                )
                return

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
                            _executar_sql(str(ferramenta.get("pergunta", pergunta)), trace, cliente)
                        )
                    elif tipo == "rag":
                        partes.append(
                            _executar_rag(str(ferramenta.get("consulta", pergunta)), trace)
                        )
            except Exception as exc:  # falha isolada nao derruba a resposta
                log.warning("ferramenta %s falhou: %s", tipo, exc)
                trace.append({"tipo": "erro", "detalhe": f"{tipo}: {exc}"})
                partes.append(f"Ferramenta {tipo} falhou: {exc}")

        contexto = "\n\n---\n\n".join(partes) if partes else "Nenhuma ferramenta retornou contexto."

        # 3) Resposta final com streaming
        mensagens = [
            {"role": "system", "content": SYSTEM_PROMPT},
            *_historico_mensagens(history),
            {"role": "user", "content": FINAL_PROMPT.format(pergunta=pergunta, contexto=contexto)},
        ]
        yield from cliente.stream(mensagens)
