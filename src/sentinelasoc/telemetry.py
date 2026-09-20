"""Observabilidade: logging estruturado com contexto de requisicao.

Cada linha de log identifica a ORIGEM (nome do logger = modulo) e a REQUISICAO
(request_id correlaciona todas as etapas de uma resposta; o mesmo id aparece no
rastro da resposta na interface).

Destinos: console (stdout) e logs/sentinelasoc.log com rotacao (1 MB x 3).
"""

import contextvars
import logging
import secrets
import sys
import time
from collections.abc import Iterator
from contextlib import contextmanager
from logging.handlers import RotatingFileHandler
from pathlib import Path

_CONFIGURED = False
_request_id: contextvars.ContextVar[str] = contextvars.ContextVar("request_id", default="—")


class _ContextoRequisicao(logging.Filter):
    """Injeta o request_id corrente em todo registro de log."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = _request_id.get()
        return True


_FORMATO = "%(asctime)s | %(levelname)-7s | %(name)s | req=%(request_id)s | %(message)s"


def _caminho_log() -> Path:
    from sentinelasoc.settings import get_settings

    pasta = get_settings().project_root / "logs"
    pasta.mkdir(parents=True, exist_ok=True)
    return pasta / "sentinelasoc.log"


def configure_logging(level: str = "INFO") -> None:
    global _CONFIGURED
    if _CONFIGURED:
        return
    raiz = logging.getLogger("sentinelasoc")
    raiz.setLevel(level.upper())

    # NB: filtros de LOGGER nao se aplicam a registros propagados de filhos;
    # o filtro de contexto deve viver nos HANDLERS.
    contexto = _ContextoRequisicao()

    console = logging.StreamHandler(sys.stdout)
    console.setFormatter(logging.Formatter(_FORMATO))
    console.addFilter(contexto)
    raiz.addHandler(console)

    try:
        arquivo = RotatingFileHandler(
            _caminho_log(), maxBytes=1_000_000, backupCount=3, encoding="utf-8"
        )
        arquivo.setFormatter(logging.Formatter(_FORMATO))
        arquivo.addFilter(contexto)
        raiz.addHandler(arquivo)
    except OSError:  # ambiente sem escrita (ex.: container read-only): console apenas
        raiz.warning("arquivo de log indisponivel; mantendo apenas console")

    # bibliotecas verbosas em warning
    for ruidoso in ("chromadb", "sentence_transformers", "httpx", "httpcore", "urllib3"):
        logging.getLogger(ruidoso).setLevel(logging.WARNING)

    _CONFIGURED = True


def get_logger(name: str) -> logging.Logger:
    configure_logging()
    if not name.startswith("sentinelasoc"):
        name = f"sentinelasoc.{name}"
    return logging.getLogger(name)


@contextmanager
def request_context() -> Iterator[str]:
    """Abre o contexto de uma requisicao: gera id curto e restaura ao final."""
    rid = secrets.token_hex(4)
    token = _request_id.set(rid)
    try:
        yield rid
    finally:
        _request_id.reset(token)


@contextmanager
def timed(label: str, trace: list[dict] | None = None) -> Iterator[None]:
    """Registra duracao de uma etapa; opcionalmente anexa ao trace da resposta."""
    inicio = time.perf_counter()
    try:
        yield
    finally:
        duracao = round(time.perf_counter() - inicio, 3)
        get_logger("sentinelasoc.timing").debug("etapa=%s duracao=%.3fs", label, duracao)
        if trace is not None:
            trace.append({"tipo": "tempo", "etapa": label, "segundos": duracao})
