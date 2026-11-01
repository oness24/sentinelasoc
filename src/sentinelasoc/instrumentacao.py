"""Instrumentacao de chamadas LLM (equivalente-local ao Langfuse).

Diario de chamadas em SQLite (`llm_chamadas` no sentinelasoc.db): request_id,
agente/papel (triador/redator/sistema), etapa do pipeline, modelo, tokens
(quando o provedor informa), latencia e sucesso/falha. A correlacao por
request_id ja existe nos logs — aqui ela ganha tabela propria e painel na UI.

Design:
- O registro acontece DENTRO do cliente LLM de producao (llm.py): nenhuma
  chamada escapa, independentemente de quem chamou.
- Papel/etapa correntes via contextvars: a tripulacao (crew.py) rotula cada
  fase com `contexto_llm(agente=..., etapa=...)` — sem passar flags na assinatura.
- Falhas de gravacao NUNCA derrubam a resposta (try/except; o diario e
  observabilidade, nao caminha de dados).
"""

import contextvars
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime

from sentinelasoc.settings import get_settings
from sentinelasoc.telemetry import get_logger, request_id_corrente

log = get_logger(__name__)

_agente_corrente: contextvars.ContextVar[str] = contextvars.ContextVar(
    "agente_corrente", default="sistema"
)
_etapa_corrente: contextvars.ContextVar[str] = contextvars.ContextVar(
    "etapa_corrente", default="llm"
)


@contextmanager
def contexto_llm(agente: str, etapa: str) -> Iterator[None]:
    """Rotula as chamadas LLM do bloco com agente + etapa do pipeline."""
    ta = _agente_corrente.set(agente)
    te = _etapa_corrente.set(etapa)
    try:
        yield
    finally:
        _agente_corrente.reset(ta)
        _etapa_corrente.reset(te)


def contexto_corrente() -> tuple[str, str]:
    """(agente, etapa) vigentes — lidos pelo cliente LLM ao registrar."""
    return _agente_corrente.get(), _etapa_corrente.get()


def _agora() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def registrar_chamada(
    *,
    modelo: str,
    duracao_ms: float,
    sucesso: bool,
    agente: str | None = None,
    etapa: str | None = None,
    request_id: str | None = None,
    prompt_tokens: int | None = None,
    completion_tokens: int | None = None,
    erro: str | None = None,
    con: sqlite3.Connection | None = None,
) -> None:
    """Insere uma chamada no diario. Excecoes de gravacao sao engolidas."""
    agente = agente or contexto_corrente()[0]
    etapa = etapa or contexto_corrente()[1]
    request_id = request_id or request_id_corrente()
    fecha = con is None
    try:
        if con is None:
            con = sqlite3.connect(str(get_settings().memory_path), timeout=15)
            con.execute("PRAGMA busy_timeout=15000")
            con.execute("PRAGMA journal_mode=WAL")
        con.execute(
            """
            CREATE TABLE IF NOT EXISTS llm_chamadas (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                criada_em TEXT NOT NULL,
                request_id TEXT NOT NULL,
                agente TEXT NOT NULL,
                etapa TEXT NOT NULL,
                modelo TEXT NOT NULL,
                duracao_ms REAL NOT NULL,
                sucesso INTEGER NOT NULL,
                prompt_tokens INTEGER,
                completion_tokens INTEGER,
                erro TEXT
            )
            """,
        )
        con.execute(
            "INSERT INTO llm_chamadas (criada_em, request_id, agente, etapa, modelo,"
            " duracao_ms, sucesso, prompt_tokens, completion_tokens, erro)"
            " VALUES (?,?,?,?,?,?,?,?,?,?)",
            (
                _agora(),
                request_id,
                agente,
                etapa,
                modelo,
                round(duracao_ms, 1),
                1 if sucesso else 0,
                prompt_tokens,
                completion_tokens,
                erro[:300] if erro else None,
            ),
        )
        con.commit()
    except sqlite3.Error as exc:  # observabilidade nunca derruba a resposta
        log.warning("instrumentacao.registro.falhou erro=%s", exc)
    finally:
        if fecha and con is not None:
            con.close()


def _consultar(sql: str, params: tuple = ()) -> list[dict]:
    try:
        con = sqlite3.connect(str(get_settings().memory_path), timeout=15)
        con.execute("PRAGMA busy_timeout=15000")
        con.row_factory = sqlite3.Row
        try:
            linhas = con.execute(sql, params).fetchall()
            return [dict(linha) for linha in linhas]
        finally:
            con.close()
    except sqlite3.Error as exc:
        log.warning("instrumentacao.consulta.falhou erro=%s", exc)
        return []


def resumo() -> dict:
    """KPIs do diario: volume, latencia, sucesso, retries e tokens."""
    linhas = _consultar(
        """
        SELECT COUNT(*) AS chamadas,
               COUNT(DISTINCT request_id) AS requests,
               AVG(duracao_ms) AS latencia_media,
               MAX(duracao_ms) AS latencia_max,
               SUM(sucesso) AS ok,
               SUM(CASE WHEN sucesso=0 THEN 1 ELSE 0 END) AS falhas,
               SUM(prompt_tokens) AS prompt_tokens,
               SUM(completion_tokens) AS completion_tokens
        FROM llm_chamadas
        """
    )
    if not linhas:
        return {
            "chamadas": 0,
            "requests": 0,
            "latencia_media": 0.0,
            "latencia_max": 0.0,
            "ok": 0,
            "falhas": 0,
            "prompt_tokens": None,
            "completion_tokens": None,
        }
    r = linhas[0]
    return {
        "chamadas": r["chamadas"] or 0,
        "requests": r["requests"] or 0,
        "latencia_media": round(r["latencia_media"] or 0.0, 0),
        "latencia_max": round(r["latencia_max"] or 0.0, 0),
        "ok": r["ok"] or 0,
        "falhas": r["falhas"] or 0,
        "prompt_tokens": r["prompt_tokens"],
        "completion_tokens": r["completion_tokens"],
    }


def por_etapa() -> list[dict]:
    """Latencia e volume por etapa do pipeline (p/ painel Observabilidade)."""
    return _consultar(
        """
        SELECT agente, etapa, COUNT(*) AS chamadas,
               ROUND(AVG(duracao_ms), 0) AS latencia_media,
               ROUND(MAX(duracao_ms), 0) AS latencia_max,
               SUM(sucesso) AS ok
        FROM llm_chamadas
        GROUP BY agente, etapa
        ORDER BY chamadas DESC, etapa
        """
    )


def ultimas(n: int = 25) -> list[dict]:
    """Chamadas mais recentes (p inspecao pontual por request)."""
    return _consultar("SELECT * FROM llm_chamadas ORDER BY id DESC LIMIT ?", (int(n),))


def por_request(request_id: str) -> list[dict]:
    """Linha do tempo de chamadas de uma requisicao."""
    return _consultar("SELECT * FROM llm_chamadas WHERE request_id = ? ORDER BY id", (request_id,))
