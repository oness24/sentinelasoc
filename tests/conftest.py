"""Fixtures compartilhadas: cliente LLM falso para testes unitarios sem rede."""

import json

import pytest


class FakeLLM:
    """LLM deterministico para testes: devolve respostas enfileiradas por chamada."""

    def __init__(self, complete_responses: list[str], stream_chunks: list[str] | None = None):
        self._responses = list(complete_responses)
        self._stream_chunks = stream_chunks or ["Resposta ", "de ", "teste."]
        self.complete_calls: list[list[dict]] = []
        self.stream_calls: list[list[dict]] = []

    def complete(self, messages, temperature=0.2, max_tokens=900) -> str:
        self.complete_calls.append(messages)
        return self._responses.pop(0)

    def stream(self, messages, temperature=0.3, max_tokens=1200):
        self.stream_calls.append(messages)
        yield from self._stream_chunks


@pytest.fixture
def fake_llm() -> FakeLLM:
    return FakeLLM(complete_responses=["{}"])


def rota_consultar(ferramentas: list[dict]) -> str:
    return json.dumps({"acao": "consultar", "ferramentas": ferramentas}, ensure_ascii=False)
