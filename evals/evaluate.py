"""Avaliacao do pipeline RAG do SentinelaSOC sobre o golden set (evals/golden.json).

Metricas: hit@1, hit@3, MRR e distancia media do top-1 (cosseno; menor = melhor).
Sem custo de LLM: mede apenas a recuperacao semantica, que e o gargalo do RAG.

Uso:
  python evals/evaluate.py                     # avalia o modelo configurado em settings
  python evals/evaluate.py --models m1 m2 ...   # compara modelos (indices temporarios)
  python evals/evaluate.py --report caminho.md  # grava relatorio (default evals/report.md)
"""

import argparse
import json
import shutil
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import chromadb
from sentence_transformers import SentenceTransformer

from sentinelasoc.rag import Embedder, dividir_chunk_longo, dividir_secoes
from sentinelasoc.settings import get_settings


def carregar_casos() -> list[dict]:
    caminho = Path(__file__).parent / "golden.json"
    return json.loads(caminho.read_text(encoding="utf-8"))["casos"]


class EmbedderAvaliacao(Embedder):
    """Embedder parametrizavel; prefixos e5 apenas para modelos da familia e5."""

    def __init__(self, modelo: str):
        self._modelo = modelo
        self._st = SentenceTransformer(modelo)

    def _encode(self, textos: list[str]) -> list[list[float]]:
        vetores = self._st.encode(textos, normalize_embeddings=True, show_progress_bar=False)
        return [list(v) for v in vetores]

    def embed_documents(self, input: list[str]) -> list[list[float]]:
        prefixo = "passage: " if "e5" in self._modelo else ""
        return self._encode([f"{prefixo}{t}" for t in input])

    def embed_query(self, input) -> list[list[float]]:
        if isinstance(input, str):
            input = [input]
        prefixo = "query: " if "e5" in self._modelo else ""
        return self._encode([f"{prefixo}{t}" for t in input])

    def name(self) -> str:
        return self._modelo


def construir_indice_temporario(modelo: str, dir_tmp: str) -> chromadb.Collection:
    s = get_settings()
    ef = EmbedderAvaliacao(modelo)
    client = chromadb.PersistentClient(path=dir_tmp)
    col = client.get_or_create_collection(
        "eval", embedding_function=ef, metadata={"hnsw:space": "cosine"}
    )
    ids, textos, metadados = [], [], []
    for doc in sorted(Path(s.docs_dir).glob("*.md")):
        for titulo, secao in dividir_secoes(doc.read_text(encoding="utf-8")):
            for bloco in dividir_chunk_longo(secao, s.chunk_chars, s.chunk_overlap):
                if len(bloco.strip()) < 40:
                    continue
                ids.append(f"{doc.stem}::{len(ids):03d}")
                textos.append(bloco)
                metadados.append({"fonte": doc.name, "secao": titulo})
    col.add(ids=ids, documents=textos, metadatas=metadados)
    return col


def avaliar_modelo(modelo: str, casos: list[dict], k: int = 3) -> dict:
    dir_tmp = tempfile.mkdtemp(prefix="eval_chroma_")
    inicio = time.perf_counter()
    try:
        col = construir_indice_temporario(modelo, dir_tmp)
        resultados = []
        for caso in casos:
            res = col.query(query_texts=[caso["pergunta"]], n_results=k)
            fontes = [(res["metadatas"][0][i] or {}).get("fonte", "?") for i in range(k)]
            distancias = [round(float(d), 3) for d in res["distances"][0]]
            rank = next((i + 1 for i, f in enumerate(fontes) if f == caso["doc"]), None)
            resultados.append(
                {
                    **caso,
                    "rank": rank,
                    "hit1": rank == 1,
                    "hit3": rank is not None,
                    "top1_doc": fontes[0],
                    "top1_dist": distancias[0],
                }
            )
        n = len(resultados)
        return {
            "modelo": modelo,
            "chunks": col.count(),
            "segundos": round(time.perf_counter() - inicio, 1),
            "hit1": sum(r["hit1"] for r in resultados) / n,
            "hit3": sum(r["hit3"] for r in resultados) / n,
            "mrr": sum(1.0 / r["rank"] if r["rank"] else 0.0 for r in resultados) / n,
            "dist_media_top1": round(sum(r["top1_dist"] for r in resultados) / n, 3),
            "casos": resultados,
        }
    finally:
        shutil.rmtree(dir_tmp, ignore_errors=True)


def gerar_relatorio(resultados: list[dict], caminho: Path) -> None:
    linhas = [
        "# Avaliacao do pipeline RAG — SentinelaSOC",
        "",
        "Golden set: 12 perguntas reais de triagem (evals/golden.json).",
        "Metricas sobre a recuperacao semantica (sem LLM no circuito).",
        "",
        "| Modelo | Chunks | hit@1 | hit@3 | MRR | dist. media top-1 | tempo (s) |",
        "|---|---|---|---|---|---|---|",
    ]
    for r in resultados:
        linhas.append(
            f"| `{r['modelo']}` | {r['chunks']} | {r['hit1']:.0%} | {r['hit3']:.0%} "
            f"| {r['mrr']:.2f} | {r['dist_media_top1']} | {r['segundos']} |"
        )
    detalhe = resultados[-1]["casos"]
    linhas += [
        "",
        "## Detalhe por pergunta (modelo avaliado por ultimo)",
        "",
        "| Pergunta | Doc esperado | Rank | Top-1 | Dist. top-1 |",
        "|---|---|---|---|---|",
    ]
    for c in detalhe:
        rank = c["rank"] if c["rank"] else "—"
        linhas.append(
            f"| {c['pergunta'][:60]} | {c['doc']} | {rank} | {c['top1_doc']} | {c['top1_dist']} |"
        )
    caminho.write_text("\n".join(linhas) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--models", nargs="+", default=[get_settings().embed_model])
    parser.add_argument("--report", default=str(Path(__file__).parent / "report.md"))
    parser.add_argument("--k", type=int, default=3)
    args = parser.parse_args()

    casos = carregar_casos()
    print(f"Avaliando {len(casos)} casos | modelos: {', '.join(args.models)}\n")
    resultados = []
    for modelo in args.models:
        r = avaliar_modelo(modelo, casos, k=args.k)
        resultados.append(r)
        print(
            f"{modelo}: hit@1={r['hit1']:.0%} hit@3={r['hit3']:.0%} MRR={r['mrr']:.2f} "
            f"dist_top1={r['dist_media_top1']} ({r['segundos']}s)"
        )

    saida = Path(args.report)
    gerar_relatorio(resultados, saida)
    print(f"\nRelatorio gravado em {saida}")


if __name__ == "__main__":
    main()
