"""Clientes LLM com injecao de dependencia: producao (OpenAI-compativel) e testes (fake)."""

import time
from collections.abc import Iterator
from typing import Protocol

from openai import OpenAI, OpenAIError

from sentinelasoc.settings import get_settings
from sentinelasoc.telemetry import get_logger

log = get_logger(__name__)


class LLMClient(Protocol):
    """Contrato minimo de um cliente LLM (permite mock nos testes unitarios)."""

    def complete(
        self,
        messages: list[dict],
        temperature: float = 0.2,
        max_tokens: int = 1500,
        json_mode: bool = False,
    ) -> str: ...

    def stream(
        self, messages: list[dict], temperature: float = 0.3, max_tokens: int = 1200
    ) -> Iterator[str]: ...


def _sem_pensamento(texto: str) -> str:
    """Remove blocos de raciocinio <think>...</think> (modelos de raciocinio via API)."""
    if "</think>" in texto:
        texto = texto.split("</think>", 1)[1]
    return texto.strip()


class OpenAILLMClient:
    """Cliente para qualquer provedor compativel com a API OpenAI
    (OpenAI, OpenRouter, Groq, Together, Ollama, vLLM...), com retry exponencial.

    Toda chamada e registrada no diario de instrumentacao (agente/etapa correntes,
    tokens quando o provedor informa, latencia e sucesso) — ver instrumentacao.py.
    """

    def __init__(self) -> None:
        s = get_settings()
        if not s.openai_api_key:
            raise RuntimeError(
                "OPENAI_API_KEY nao configurada. Copie .env.example para .env e informe sua chave."
            )
        self._client = OpenAI(api_key=s.openai_api_key, base_url=s.openai_base_url)
        self.model = s.llm_model
        self._retries = s.llm_max_retries

    def _registrar(self, inicio: float, sucesso: bool, resp=None, erro: str | None = None) -> None:
        """Grava a chamada no diario; falha de gravacao nao propaga."""
        from sentinelasoc import instrumentacao

        prompt_tokens = getattr(getattr(resp, "usage", None), "prompt_tokens", None)
        completion_tokens = getattr(getattr(resp, "usage", None), "completion_tokens", None)
        agente, etapa = instrumentacao.contexto_corrente()
        instrumentacao.registrar_chamada(
            modelo=self.model,
            duracao_ms=(time.perf_counter() - inicio) * 1000,
            sucesso=sucesso,
            agente=agente,
            etapa=etapa,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            erro=erro,
        )

    def _call_with_retries(
        self,
        messages: list[dict],
        temperature: float,
        max_tokens: int,
        stream: bool,
        json_mode: bool = False,
    ):
        ultimo_erro: Exception | None = None
        for tentativa in range(self._retries + 1):
            try:
                kwargs: dict = {
                    "model": self.model,
                    "messages": messages,  # type: ignore[arg-type]
                    "temperature": temperature,
                    "max_tokens": max_tokens,
                    "stream": stream,
                }
                if json_mode and not stream:
                    kwargs["response_format"] = {"type": "json_object"}
                return self._client.chat.completions.create(**kwargs)  # type: ignore[arg-type]
            except OpenAIError as exc:  # transitorias: rate limit, timeout, 5xx
                ultimo_erro = exc
                if json_mode and "response_format" in str(exc):
                    # provedor/modelo sem suporte a JSON mode: cai para modo texto
                    log.warning("llm.json_mode.unsupported erro=%s", exc)
                    json_mode = False
                    continue
                log.warning("llm.retry tentativa=%d erro=%s", tentativa + 1, exc)
                time.sleep(1.5**tentativa)
        raise ultimo_erro  # type: ignore[misc]

    def complete(
        self,
        messages: list[dict],
        temperature: float = 0.2,
        max_tokens: int = 1500,
        json_mode: bool = False,
    ) -> str:
        inicio = time.perf_counter()
        try:
            resp = self._call_with_retries(
                messages, temperature, max_tokens, stream=False, json_mode=json_mode
            )
        except Exception as exc:
            self._registrar(inicio, sucesso=False, erro=f"{type(exc).__name__}: {exc}")
            raise
        self._registrar(inicio, sucesso=True, resp=resp)
        return _sem_pensamento(resp.choices[0].message.content or "")

    def stream(
        self, messages: list[dict], temperature: float = 0.3, max_tokens: int = 1200
    ) -> Iterator[str]:
        inicio = time.perf_counter()
        try:
            resp = self._call_with_retries(messages, temperature, max_tokens, stream=True)
            yield from _deltas(resp)
        except Exception as exc:
            self._registrar(inicio, sucesso=False, erro=f"{type(exc).__name__}: {exc}")
            raise
        # streaming OpenAI nao expoe usage: tokens ficam nulos no diario
        self._registrar(inicio, sucesso=True)


def _deltas(resp) -> Iterator[str]:
    for delta in resp:
        piece = delta.choices[0].delta.content
        if piece:
            yield piece
