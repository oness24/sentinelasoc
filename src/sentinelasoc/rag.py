"""Camada RAG: embeddings multilingues + ChromaDB sobre os documentos internos.

Modelo padrao `paraphrase-multilingual-MiniLM-L12-v2`, escolhido por benchmark
no golden set (evals/report.md): hit@1 92%, hit@3 100%, MRR 0.96 — alem de 4x
menor e mais rapido que a alternativa e5. Modelos da familia e5 sao suportados
via EMBED_MODEL e recebem prefixos query/passage automaticamente.

A recuperacao e HIBRIDA: vetores (semantica) + BM25 (identificadores exatos,
como T1566 e '15/2024') fundidos por reciprocal rank — medido em evals/.
"""

import contextlib
import re
import threading
from pathlib import Path

import chromadb
from rank_bm25 import BM25Okapi
from sentence_transformers import SentenceTransformer

from sentinelasoc.settings import get_settings
from sentinelasoc.telemetry import get_logger

log = get_logger(__name__)

_model: SentenceTransformer | None = None


def _get_model() -> SentenceTransformer:
    global _model
    if _model is None:
        _model = SentenceTransformer(get_settings().embed_model)
    return _model


class Embedder:
    """Funcao de embedding compativel com as interfaces antiga e nova do ChromaDB.

    Modelos da familia e5 exigem prefixos `query:`/`passage:`; os demais recebem
    o texto puro (comportamento validado no benchmark de evals/).
    """

    def __call__(self, input: list[str]) -> list[list[float]]:
        return self._encode(input)

    def embed_documents(self, input: list[str]) -> list[list[float]]:
        prefixo = "passage: " if "e5" in get_settings().embed_model else ""
        return self._encode([f"{prefixo}{t}" for t in input])

    def embed_query(self, input) -> list[list[float]]:  # ChromaDB 1.x passa lista
        if isinstance(input, str):
            input = [input]
        prefixo = "query: " if "e5" in get_settings().embed_model else ""
        return self._encode([f"{prefixo}{t}" for t in input])

    def _encode(self, textos: list[str]) -> list[list[float]]:
        vetores = _get_model().encode(textos, normalize_embeddings=True, show_progress_bar=False)
        return [list(v) for v in vetores]

    def name(self) -> str:
        return get_settings().embed_model

    @staticmethod
    def is_legacy() -> bool:
        return False


def get_collection() -> chromadb.Collection:
    s = get_settings()
    client = chromadb.PersistentClient(path=str(s.chroma_dir))
    return client.get_or_create_collection(
        name=s.collection_name,
        embedding_function=Embedder(),  # type: ignore[arg-type]  # duck-typed EF
        metadata={"hnsw:space": "cosine"},
    )


def retrieve(query: str, k: int | None = None) -> list[dict]:
    """Busca hibrida: vetores (semantica) + BM25 (identificadores exatos) com RRF.

    Embeddings borram identificadores (CVE-2025-2183, T1566, '15/2024'); o BM25
    acerta termos exatos e a fusao por reciprocal rank combina os dois.
    """
    s = get_settings()
    col = get_collection()
    if col.count() == 0:
        return []
    n = min(k or s.retrieval_k, col.count())
    res = col.query(query_texts=[query], n_results=n)
    log.info("rag.query k=%d chunks=%d modo=hibrido", n, col.count())
    ids_res, metas_res, dists_res, docs_res = (
        res["ids"],
        res["metadatas"],
        res["distances"],
        res["documents"],
    )
    assert ids_res and metas_res and dists_res and docs_res  # narrowing stubs ChromaDB

    distancia_por_id = {ids_res[0][i]: dists_res[0][i] for i in range(len(ids_res[0]))}

    # ---- fusao reciprocal rank (vetor + bm25) ----
    pontuacao: dict[str, float] = {}
    for rank, cid in enumerate(ids_res[0]):
        pontuacao[cid] = pontuacao.get(cid, 0.0) + 1.0 / (60 + rank + 1)
    for cid, rrf in _bm25_rrf(query, n):
        pontuacao[cid] = pontuacao.get(cid, 0.0) + rrf

    top = sorted(pontuacao.keys(), key=lambda cid: pontuacao[cid], reverse=True)[:n]

    indice = _indice_bm25()
    chunks = []
    for cid in top:
        md = indice.metadados.get(cid, {}) if indice else {}
        distancia = distancia_por_id.get(cid)
        chunks.append(
            {
                "chunk_id": cid,
                "texto": indice.documentos.get(cid, "") if indice else "",
                "fonte": md.get("fonte", "desconhecida"),
                "secao": md.get("secao", ""),
                "distancia": round(float(distancia), 3) if distancia is not None else -1,
            }
        )
    return chunks


def _tokenizar(texto: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", texto.lower())


class _IndiceBM25:
    """Corpus espelhado do ChromaDB para busca lexica exata."""

    def __init__(self, ids: list[str], documentos: dict[str, str], metadados: dict[str, dict]):
        self.ids = ids
        self.documentos = documentos
        self.metadados = metadados
        corpus = [_tokenizar(documentos[cid]) for cid in ids]
        self.bm25 = BM25Okapi(corpus) if any(corpus) else None


_bm25_lock = threading.Lock()
_bm25_cache: tuple[int, _IndiceBM25 | None] | None = None


def _indice_bm25() -> _IndiceBM25 | None:
    """Indice BM25 lazy, invalidado quando a colecao muda de tamanho."""
    global _bm25_cache
    with _bm25_lock:
        col = get_collection()
        total = col.count()
        if _bm25_cache and _bm25_cache[0] == total:
            return _bm25_cache[1]
        try:
            dados = col.get(include=["documents", "metadatas"])  # type: ignore[arg-type]
            ids = list(dados["ids"])
            documentos = {cid: doc for cid, doc in zip(ids, dados["documents"] or [], strict=False)}
            metadados = {
                cid: dict(meta or {})
                for cid, meta in zip(ids, dados["metadatas"] or [], strict=False)
            }
            indice = _IndiceBM25(ids, documentos, metadados)
        except Exception as exc:  # degrada para busca vetorial pura
            log.warning("rag.bm25.indisponivel erro=%s", exc)
            indice = None
        _bm25_cache = (total, indice)
        return indice


def _bm25_rrf(query: str, k: int) -> list[tuple[str, float]]:
    """Ranking BM25 ja convertido em contribuicoes RRF (vazio se indisponivel)."""
    indice = _indice_bm25()
    if indice is None or indice.bm25 is None:
        return []
    pontos = indice.bm25.get_scores(_tokenizar(query))
    ordenados = sorted(range(len(pontos)), key=lambda i: -pontos[i])
    resultado = []
    for rank_pos, i in enumerate(ordenados):
        if pontos[i] <= 0 or rank_pos >= k * 3:
            break
        resultado.append((indice.ids[i], 1.0 / (60 + rank_pos + 1)))
    return resultado


# ---------------- Ingestao ----------------


def dividir_secoes(texto: str) -> list[tuple[str, str]]:
    """Divide o documento por cabecalhos de nivel 2 e 3 (## e ###)."""
    partes: list[tuple[str, str]] = []
    atual_titulo = "Introducao"
    atual_linhas: list[str] = []
    for linha in texto.splitlines():
        if linha.startswith("## ") or linha.startswith("### "):
            if atual_linhas:
                partes.append((atual_titulo, "\n".join(atual_linhas).strip()))
            atual_titulo = linha.lstrip("# ").strip()
            atual_linhas = [linha]
        else:
            atual_linhas.append(linha)
    if atual_linhas:
        partes.append((atual_titulo, "\n".join(atual_linhas).strip()))
    return partes


def dividir_chunk_longo(texto: str, tamanho: int, sobreposicao: int) -> list[str]:
    """Quebra secoes muito longas em blocos menores com sobreposicao.

    Bug historico: quando o bloco final atingia o fim do texto, o avanco
    `fim - sobreposicao` voltava atras e reemitia o trecho final dezenas de
    vezes. O laco agora termina ao alcancar o fim.
    """
    if len(texto) <= tamanho + 200:
        return [texto]
    blocos, inicio = [], 0
    while inicio < len(texto):
        fim = min(inicio + tamanho, len(texto))
        if fim < len(texto):
            corte = texto.rfind("\n", inicio + tamanho // 2, fim)
            if corte > inicio:
                fim = corte
        bloco = texto[inicio:fim].strip()
        if bloco:
            blocos.append(bloco)
        if fim >= len(texto):
            break
        inicio = max(fim - sobreposicao, inicio + 1)
    return blocos


def ingest() -> int:
    """(Re)indexa todos os .md de docs/ no ChromaDB. Idempotente. Retorna n. de chunks."""
    s = get_settings()
    docs = sorted(Path(s.docs_dir).glob("*.md"))
    if not docs:
        raise FileNotFoundError(f"Nenhum .md encontrado em {s.docs_dir}")

    client = chromadb.PersistentClient(path=str(s.chroma_dir))
    with contextlib.suppress(Exception):  # colecao inexistente na primeira execucao
        client.delete_collection(s.collection_name)

    col = get_collection()
    ids: list[str] = []
    textos: list[str] = []
    metadados: list[dict[str, str]] = []
    for doc in docs:
        conteudo = doc.read_text(encoding="utf-8")
        for titulo, secao in dividir_secoes(conteudo):
            for bloco in dividir_chunk_longo(secao, s.chunk_chars, s.chunk_overlap):
                if len(bloco.strip()) < 40:
                    continue
                ids.append(f"{doc.stem}::{len(ids):03d}")
                textos.append(bloco)
                metadados.append({"fonte": doc.name, "secao": titulo})

    col.add(ids=ids, documents=textos, metadatas=metadados)  # type: ignore[arg-type]
    return len(ids)
