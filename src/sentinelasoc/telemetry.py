"""Logging estruturado simples e medicao de tempo por etapa."""

import logging
import sys
import time
from collections.abc import Iterator
from contextlib import contextmanager

_CONFIGURED = False
_FORMAT = "%(asctime)s | %(levelname)-7s | %(name)s | %(message)s"


def configure_logging(level: str = "INFO") -> None:
    global _CONFIGURED
    if _CONFIGURED:
        return
    logging.basicConfig(level=level.upper(), stream=sys.stdout, format=_FORMAT)
    logging.getLogger("chromadb").setLevel(logging.WARNING)
    logging.getLogger("sentence_transformers").setLevel(logging.WARNING)
    _CONFIGURED = True


def get_logger(name: str) -> logging.Logger:
    configure_logging()
    return logging.getLogger(name)


@contextmanager
def timed(label: str, trace: list[dict] | None = None) -> Iterator[None]:
    """Registra duracao de uma etapa; opcionalmente anexa ao trace da resposta."""
    inicio = time.perf_counter()
    try:
        yield
    finally:
        duracao = round(time.perf_counter() - inicio, 3)
        get_logger("sentinelasoc.timing").debug("%s concluido em %.3fs", label, duracao)
        if trace is not None:
            trace.append({"tipo": "tempo", "etapa": label, "segundos": duracao})
