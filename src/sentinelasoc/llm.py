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
        self, messages: list[dict], temperature: float = 0.2, max_tokens: int = 900
    ) -> str: ...

    def stream(
        self, messages: list[dict], temperature: float = 0.3, max_tokens: int = 1200
    ) -> Iterator[str]: ...


class OpenAILLMClient:
    """Cliente para qualquer provedor compativel com a API OpenAI
    (OpenAI, OpenRouter, Groq, Together, Ollama, vLLM...), com retry exponencial."""

    def __init__(self) -> None:
        s = get_settings()
        if not s.openai_api_key:
            raise RuntimeError(
                "OPENAI_API_KEY nao configurada. Copie .env.example para .env e informe sua chave."
            )
        self._client = OpenAI(api_key=s.openai_api_key, base_url=s.openai_base_url)
        self.model = s.llm_model
        self._retries = s.llm_max_retries

    def _call_with_retries(
        self, messages: list[dict], temperature: float, max_tokens: int, stream: bool
    ):
        ultimo_erro: Exception | None = None
        for tentativa in range(self._retries + 1):
            try:
                return self._client.chat.completions.create(
                    model=self.model,
                    messages=messages,  # type: ignore[arg-type]
                    temperature=temperature,
                    max_tokens=max_tokens,
                    stream=stream,
                )
            except OpenAIError as exc:  # transitorias: rate limit, timeout, 5xx
                ultimo_erro = exc
                log.warning("tentativa %d falhou (%s); repetindo...", tentativa + 1, exc)
                time.sleep(1.5**tentativa)
        raise ultimo_erro  # type: ignore[misc]

    def complete(
        self, messages: list[dict], temperature: float = 0.2, max_tokens: int = 900
    ) -> str:
        resp = self._call_with_retries(messages, temperature, max_tokens, stream=False)
        return resp.choices[0].message.content or ""

    def stream(
        self, messages: list[dict], temperature: float = 0.3, max_tokens: int = 1200
    ) -> Iterator[str]:
        resp = self._call_with_retries(messages, temperature, max_tokens, stream=True)
        for delta in resp:
            piece = delta.choices[0].delta.content
            if piece:
                yield piece
