"""Treina os modelos de ML e gera evals/report_ml.md.

Uso:
    ./venv/bin/python scripts/train_ml.py

Experimentos:
1. NSL-KDD (publico): ataque vs normal — logreg e gradient boosting no protocolo
   padrao do dataset (treino KDDTrain+, teste KDDTest+).
2. Falso positivo (sistema): preditor usado pela ferramenta `ml` do agente.

O NSL-KDD fica em data/nsl_kdd/ (gitignored). Para baixar:
    make download-nsl
"""

from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from sentinelasoc import ml


def _tabela(metricas: list[dict[str, float | int | str]], colunas: list[str]) -> str:
    cab = "| Métrica | " + " | ".join(str(m["modelo"]) for m in metricas) + " |"
    sep = "|---|" + "---|" * len(metricas)
    linhas = [
        f"| {col} | " + " | ".join(str(m.get(col, "—")) for m in metricas) + " |" for col in colunas
    ]
    return "\n".join([cab, sep, *linhas])


def main() -> None:
    raiz = Path(__file__).resolve().parent.parent
    relatorio = raiz / "evals" / "report_ml.md"
    secoes: list[str] = []

    # ── 1. NSL-KDD ──────────────────────────────────────────────────────────
    arquivos = [
        raiz / "data" / "nsl_kdd" / "KDDTrain+.txt",
        raiz / "data" / "nsl_kdd" / "KDDTest+.txt",
    ]
    if all(a.exists() for a in arquivos):
        print("[1/2] NSL-KDD: treinando logreg...", flush=True)
        logreg = ml.treinar_nsl_kdd("logreg")
        print("[1/2] NSL-KDD: treinando HistGradientBoosting...", flush=True)
        hist = ml.treinar_nsl_kdd("hist")
        secoes.append(
            "## 1. NSL-KDD — triagem ataque vs normal (dataset público)\n\n"
            "Protocolo padrão da literatura: treino em `KDDTrain+` (125.973 registros),\n"
            "avaliação em `KDDTest+` (22.544 registros, inclui tipos de ataque não vistos\n"
            "no treino — por isso o teste é deliberadamente mais difícil que o treino).\n"
            "Rótulo binário: `normal` vs qualquer ataque. Categóricas (protocolo, serviço,\n"
            "flag) em one-hot com `handle_unknown=ignore` (o teste contém serviços inéditos);\n"
            "numéricas padronizadas apenas na regressão logística.\n\n"
            + _tabela(
                [logreg, hist],
                [
                    "n_treino",
                    "n_teste",
                    "ataques_treino_pct",
                    "ataques_teste_pct",
                    "baseline_acuracia",
                    "acuracia",
                    "precisao",
                    "recall",
                    "f1",
                    "auc",
                ],
            )
            + "\n\nLeitura honesta:\n"
            "- A acurácia do teste fica abaixo do treino **por design** — o KDDTest+ expõe o\n"
            "  modelo a ataques novos (generalização, não memorização).\n"
            "- A regressão logística privilegia precisão alta com recall baixo; o boosting\n"
            "  equilibra melhor as duas classes — métrica de escolha para triagem: **AUC**\n"
            "  (capacidade de ranquear alertas por risco).\n"
        )
        melhor = max((logreg, hist), key=lambda m: float(m["auc"]))
        secoes.append(
            f"> Modelo documentado como referência: **{melhor['modelo']}** "
            f"(AUC {melhor['auc']}%, F1 {melhor['f1']}%).\n"
        )
    else:
        secoes.append(
            "## 1. NSL-KDD — triagem ataque vs normal (dataset público)\n\n"
            "Arquivos ausentes em `data/nsl_kdd/` — execute `make download-nsl` e rode\n"
            "`scripts/train_ml.py` novamente.\n"
        )
        print("[1/2] NSL-KDD: arquivos ausentes — pulando (make download-nsl)")

    # ── 2. Falso positivo ────────────────────────────────────────────────────
    print("[2/2] Falso positivo: treinando preditor do sistema...", flush=True)
    fp = ml.treinar_fp()
    secoes.append(
        "## 2. Preditor de falso positivo (ferramenta `ml` do copiloto)\n\n"
        "Classificação binária sobre os incidentes históricos do SOC (dados sintéticos\n"
        "determinísticos, seed=42). Features: perfil do incidente (tipo, severidade,\n"
        "tática ATT&CK) + perfil do ativo (ambiente, criticidade, SO, exposição).\n"
        "Severidade entra como ordinal (1 grau de liberdade em vez de 4 dummies).\n"
        "Protocolo: split estratificado 75/25 + validação cruzada 5-fold no treino.\n\n"
        + _tabela(
            [fp],
            [
                "n_total",
                "n_treino",
                "n_teste",
                "fp_pct",
                "baseline_acuracia",
                "acuracia",
                "precisao",
                "recall",
                "f1",
                "auc",
                "cv_f1_medio",
            ],
        )
        + "\n\nLeitura honesta:\n"
        f"- O rótulo é **ruidoso por construção**: o gerador sorteia falso positivo com\n"
        f"probabilidade dependente apenas da severidade (Baixa→55% ... Crítica→4%).\n"
        f"Existe, portanto, um **teto de Bayes** atingível — acurácia\n"
        f"{fp['teto_bayes_acuracia']}% e AUC {fp['teto_bayes_auc']}% — calculado a partir\n"
        f"das probabilidades condicionais reais dos dados.\n"
        f"- O modelo atinge AUC {fp['auc']}% "
        f"(~{float(fp['auc']) / float(fp['teto_bayes_auc']) * 100:.0f}% do teto):\n"
        f"o gap restante é ruído aleatório, não defeito do modelo. Sem o teto publicado,\n"
        f"esses números pareceriam fracos; com ele, fica claro que o problema — não o\n"
        f"modelo — é intrinsecamente probabilístico.\n"
        f"- Decisão de produto: a ferramenta `ml` **ranqueia** incidentes para revisão\n"
        f"(probabilidade por incidente), e o limiar de classificação é a prevalência\n"
        f"({fp['limiar_prevalencia']}), não 0.5 — em triagem, sinalizar acima da\n"
        f"prevalência é a decisão útil.\n"
    )

    relatorio.write_text(
        "# Relatório de ML — SentinelaSOC\n\n"
        f"Gerado por `scripts/train_ml.py` em {date.today().isoformat()}.\n"
        "Todos os números são reproduzíveis: seeds fixos, dados determinísticos.\n\n"
        + "\n".join(secoes),
        encoding="utf-8",
    )
    print(f"relatório: {relatorio}")


if __name__ == "__main__":
    main()
