"""Camada RAG: embeddings multilingues + ChromaDB sobre os documentos internos.

Modelo padrao `paraphrase-multilingual-MiniLM-L12-v2`, escolhido por benchmark
no golden set (evals/report.md): hit@1 92%, hit@3 100%, MRR 0.96 — alem de 4x
menor e mais rapido que a alternativa e5. Modelos da familia e5 sao suportados
via EMBED_MODEL e recebem prefixos query/passage automaticamente.
"""

import contextlib
from pathlib import Path

import chromadb
from sentence_transformers import SentenceTransformer

from sentinelasoc.settings import get_settings

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
    """Retorna os k trechos mais semelhantes, com origem, secao e distancia."""
    s = get_settings()
    col = get_collection()
    if col.count() == 0:
        return []
    n = min(k or s.retrieval_k, col.count())
    res = col.query(query_texts=[query], n_results=n)
    ids_res, metas_res, dists_res, docs_res = (
        res["ids"],
        res["metadatas"],
        res["distances"],
        res["documents"],
    )
    assert ids_res and metas_res and dists_res and docs_res  # narrowing stubs ChromaDB
    chunks = []
    for i in range(len(ids_res[0])):
        md = metas_res[0][i] or {}
        chunks.append(
            {
                "chunk_id": ids_res[0][i],
                "texto": docs_res[0][i],
                "fonte": md.get("fonte", "desconhecida"),
                "secao": md.get("secao", ""),
                "distancia": round(float(dists_res[0][i]), 3),
            }
        )
    return chunks


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
    """Quebra secoes muito longas em blocos menores com sobreposicao."""
    if len(texto) <= tamanho + 200:
        return [texto]
    blocos, inicio = [], 0
    while inicio < len(texto):
        fim = min(inicio + tamanho, len(texto))
        if fim < len(texto):
            corte = texto.rfind("\n", inicio + tamanho // 2, fim)
            if corte > inicio:
                fim = corte
        blocos.append(texto[inicio:fim].strip())
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
