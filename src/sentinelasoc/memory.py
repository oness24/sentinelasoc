"""Memoria persistente do SentinelaSOC (SQLite, sem dependencias extras).

Tres camadas:
- Episodica: conversas e mensagens (com rastro) — retomaveis e exportaveis.
- Semantica: fatos duraveis sobre o analista, com teto e deduplicacao.
- Tudo local em sentinelasoc.db (gitignored); nenhum dado sai da maquina.
"""

import json
import sqlite3
from datetime import datetime
from pathlib import Path

from sentinelasoc.settings import get_settings
from sentinelasoc.telemetry import get_logger

log = get_logger(__name__)

MAX_FATOS = 12
TITULO_MAX = 60


def _agora() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def _conectar() -> sqlite3.Connection:
    caminho: Path = get_settings().memory_path
    con = sqlite3.connect(str(caminho))
    con.execute("PRAGMA journal_mode=WAL")
    con.execute(
        """
        CREATE TABLE IF NOT EXISTS conversas (
            id TEXT PRIMARY KEY,
            titulo TEXT NOT NULL,
            criada_em TEXT NOT NULL,
            atualizada_em TEXT NOT NULL
        )
        """
    )
    con.execute(
        """
        CREATE TABLE IF NOT EXISTS mensagens (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            conversa_id TEXT NOT NULL REFERENCES conversas(id) ON DELETE CASCADE,
            papel TEXT NOT NULL CHECK (papel IN ('user','assistant')),
            conteudo TEXT NOT NULL,
            trace TEXT,
            criada_em TEXT NOT NULL
        )
        """
    )
    con.execute(
        """
        CREATE TABLE IF NOT EXISTS perfil (
            fato TEXT PRIMARY KEY,
            criado_em TEXT NOT NULL,
            atualizado_em TEXT NOT NULL
        )
        """
    )
    return con


# ───────────────────────── Conversas ─────────────────────────


def nova_conversa(titulo: str) -> str:
    """Cria uma conversa e retorna seu id (hex curto)."""
    import secrets

    cid = secrets.token_hex(6)
    agora = _agora()
    with _conectar() as con:
        con.execute(
            "INSERT INTO conversas (id, titulo, criada_em, atualizada_em) VALUES (?,?,?,?)",
            (cid, titulo[:TITULO_MAX], agora, agora),
        )
    log.info("memory.conversation.created id=%s titulo=%r", cid, titulo[:TITULO_MAX])
    return cid


def listar_conversas(limite: int = 8) -> list[dict]:
    with _conectar() as con:
        cur = con.execute(
            "SELECT id, titulo, atualizada_em FROM conversas ORDER BY atualizada_em DESC LIMIT ?",
            (limite,),
        )
        return [{"id": r[0], "titulo": r[1], "atualizada_em": r[2]} for r in cur.fetchall()]


def carregar_mensagens(cid: str) -> list[dict]:
    with _conectar() as con:
        cur = con.execute(
            "SELECT papel, conteudo, trace FROM mensagens WHERE conversa_id = ? ORDER BY id",
            (cid,),
        )
        mensagens = []
        for papel, conteudo, trace in cur.fetchall():
            msg = {"role": papel, "content": conteudo}
            if trace:
                try:
                    msg["trace"] = json.loads(trace)
                except json.JSONDecodeError:
                    msg["trace"] = []
            mensagens.append(msg)
        return mensagens


def salvar_mensagem(cid: str, papel: str, conteudo: str, trace: list[dict] | None = None) -> None:
    agora = _agora()
    with _conectar() as con:
        con.execute(
            "INSERT INTO mensagens (conversa_id, papel, conteudo, trace, criada_em) VALUES (?,?,?,?,?)",
            (cid, papel, conteudo, json.dumps(trace or [], ensure_ascii=False), agora),
        )
        con.execute("UPDATE conversas SET atualizada_em = ? WHERE id = ?", (agora, cid))
    log.info("memory.message.saved conversa=%s papel=%s chars=%d", cid, papel, len(conteudo))


def apagar_conversa(cid: str) -> None:
    with _conectar() as con:
        con.execute("PRAGMA foreign_keys=ON")
        con.execute("DELETE FROM mensagens WHERE conversa_id = ?", (cid,))
        con.execute("DELETE FROM conversas WHERE id = ?", (cid,))
    log.info("memory.conversation.deleted id=%s", cid)


def contar_trocas(cid: str) -> int:
    """Numero de perguntas do analista na conversa."""
    with _conectar() as con:
        cur = con.execute(
            "SELECT COUNT(*) FROM mensagens WHERE conversa_id = ? AND papel = 'user'", (cid,)
        )
        return int(cur.fetchone()[0])


# ───────────────────────── Perfil (memoria semantica) ─────────────────────────


def fatos_perfil() -> list[str]:
    with _conectar() as con:
        cur = con.execute(
            "SELECT fato FROM perfil ORDER BY atualizado_em DESC LIMIT ?", (MAX_FATOS,)
        )
        return [r[0] for r in cur.fetchall()]


def atualizar_fatos(fatos: list[str]) -> int:
    """Adiciona fatos novos (dedup case-insensitive). Retorna quantos entraram."""
    existentes = {f.strip().lower() for f in fatos_perfil()}
    agora = _agora()
    adicionados = 0
    with _conectar() as con:
        for fato in fatos:
            limpo = fato.strip().rstrip(".")
            if len(limpo) < 4 or len(limpo) > 200 or limpo.lower() in existentes:
                continue
            con.execute(
                "INSERT INTO perfil (fato, criado_em, atualizado_em) VALUES (?,?,?) "
                "ON CONFLICT(fato) DO UPDATE SET atualizado_em = excluded.atualizado_em",
                (limpo, agora, agora),
            )
            existentes.add(limpo.lower())
            adicionados += 1
    if adicionados:
        log.info("memory.profile.updated novos=%d total_limite=%d", adicionados, MAX_FATOS)
    return adicionados


def limpar_perfil() -> None:
    with _conectar() as con:
        con.execute("DELETE FROM perfil")
    log.info("memory.profile.cleared")
