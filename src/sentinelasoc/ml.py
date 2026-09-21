"""Camada de ML do SentinelaSOC.

Dois modelos, dois propositos:

1. **NSL-KDD (requisito publico)**: classificador binario ataque/normal no
   dataset classico de deteccao de intrusao (UCI/UNB). Nao roda no copiloto —
   e o experimento reproducivel de triagem automatica de alertas, com metricas
   publicadas em `evals/report_ml.md`.

2. **Preditor de falso positivo (no sistema)**: classificador binario treinado
   nos incidentes historicos do SOC (dados sinteticos, seed=42) usando o perfil
   do incidente + do ativo. Exposto ao agente como ferramenta `ml`.

Principios:
- Determinismo: seeds fixos; mesmo dado de entrada, mesmos numeros.
- Honestidade: metricas incluem baseline (classe majoritaria) para contexto.
- Zero dependencias novas alem de scikit-learn (ja presente via chromadb).
"""

from __future__ import annotations

import json
import unicodedata
from functools import lru_cache
from pathlib import Path

import joblib
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, f1_score, precision_score, recall_score, roc_auc_score
from sklearn.model_selection import StratifiedKFold, cross_val_score, train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

from sentinelasoc.settings import get_settings

SEED = 42

# ─────────────────────────────────────────────────────────────────────────────
# 1) NSL-KDD — triagem ataque vs normal (experimento publico)
# ─────────────────────────────────────────────────────────────────────────────

# 41 atributos classicos do KDD99/NSL-KDD + rotulo + dificuldade
COLUNAS_KDD = [
    "duration",
    "protocol_type",
    "service",
    "flag",
    "src_bytes",
    "dst_bytes",
    "land",
    "wrong_fragment",
    "urgent",
    "hot",
    "num_failed_logins",
    "logged_in",
    "num_compromised",
    "root_shell",
    "su_attempted",
    "num_root",
    "num_file_creations",
    "num_shells",
    "num_access_files",
    "num_outbound_cmds",
    "is_host_login",
    "is_guest_login",
    "count",
    "srv_count",
    "serror_rate",
    "srv_serror_rate",
    "rerror_rate",
    "srv_rerror_rate",
    "same_srv_rate",
    "diff_srv_rate",
    "srv_diff_host_rate",
    "dst_host_count",
    "dst_host_srv_count",
    "dst_host_same_srv_rate",
    "dst_host_diff_srv_rate",
    "dst_host_same_src_port_rate",
    "dst_host_srv_diff_host_rate",
    "dst_host_serror_rate",
    "dst_host_srv_serror_rate",
    "dst_host_rerror_rate",
    "dst_host_srv_rerror_rate",
    "label",
    "difficulty",
]
CAT_KDD = ["protocol_type", "service", "flag"]
ALVO_KDD = "ataque"  # 1 = ataque, 0 = normal


def _carregar_kdd(caminho: Path) -> pd.DataFrame:
    df = pd.read_csv(caminho, names=COLUNAS_KDD, header=None)
    df[ALVO_KDD] = (df["label"] != "normal").astype(int)
    return df


def _pipeline_kdd(modelo: str) -> Pipeline:
    if modelo == "hist":
        clf: LogisticRegression | HistGradientBoostingClassifier = HistGradientBoostingClassifier(
            random_state=SEED, max_iter=200
        )
        pre = ColumnTransformer(
            [("cat", OneHotEncoder(handle_unknown="ignore"), CAT_KDD)],
            remainder="passthrough",
        )
    else:  # logreg
        clf = LogisticRegression(max_iter=1000, random_state=SEED)
        numericas = [c for c in COLUNAS_KDD if c not in [*CAT_KDD, "label", "difficulty", ALVO_KDD]]
        pre = ColumnTransformer(
            [
                ("cat", OneHotEncoder(handle_unknown="ignore"), CAT_KDD),
                ("num", StandardScaler(), numericas),
            ]
        )
    return Pipeline([("pre", pre), ("clf", clf)])


def treinar_nsl_kdd(modelo: str = "logreg") -> dict[str, float | int | str]:
    """Treina no KDDTrain+ e avalia no KDDTest+ (protocolo padrao do dataset).

    `modelo`: "logreg" (regressao logistica) ou "hist" (gradient boosting).
    Retorna metricas da classe positiva (ataque) no conjunto de teste.
    """
    raiz = get_settings().data_dir / "nsl_kdd"
    treino = _carregar_kdd(raiz / "KDDTrain+.txt")
    teste = _carregar_kdd(raiz / "KDDTest+.txt")

    pipe = _pipeline_kdd(modelo)
    pipe.fit(treino.drop(columns=["label", "difficulty", ALVO_KDD]), treino[ALVO_KDD])

    x_teste = teste.drop(columns=["label", "difficulty", ALVO_KDD])
    y_teste = teste[ALVO_KDD]
    prev = pipe.predict(x_teste)
    prob = pipe.predict_proba(x_teste)[:, 1]
    return {
        "modelo": "HistGradientBoosting" if modelo == "hist" else "LogisticRegression",
        "n_treino": len(treino),
        "n_teste": len(teste),
        "ataques_treino_pct": round(float(treino[ALVO_KDD].mean()) * 100, 1),
        "ataques_teste_pct": round(float(y_teste.mean()) * 100, 1),
        "baseline_acuracia": round(float(max(y_teste.mean(), 1 - y_teste.mean())) * 100, 1),
        "acuracia": round(float(accuracy_score(y_teste, prev)) * 100, 1),
        "precisao": round(float(precision_score(y_teste, prev)) * 100, 1),
        "recall": round(float(recall_score(y_teste, prev)) * 100, 1),
        "f1": round(float(f1_score(y_teste, prev)) * 100, 1),
        "auc": round(float(roc_auc_score(y_teste, prob)) * 100, 1),
    }


# ─────────────────────────────────────────────────────────────────────────────
# 2) Preditor de falso positivo (ferramenta `ml` do agente)
# ─────────────────────────────────────────────────────────────────────────────

FEATURES_FP = [
    "tipo",
    "severidade",
    "tatica_mitre",
    "ambiente",
    "criticidade",
    "sistema_operacional",
    "exposto_internet",
]
ALVO_FP = "falso_positivo"  # 1 = Sim
# Severidade e ordinal: Baixa < Media < Alta < Critica. Como feature numerica
# da ao modelo relacao monotona com 1 grau de liberdade (vs 4 dummies).
NIVEL_SEVERIDADE = {"Baixa": 0, "Media": 1, "Alta": 2, "Critica": 3}


def _carregar_incidentes() -> pd.DataFrame:
    """incidentes.csv + perfil do ativo (join por ativo_id), com alvo binario."""
    dados = get_settings().data_dir
    incidentes = pd.read_csv(dados / "incidentes.csv")
    ativos = pd.read_csv(dados / "ativos.csv")
    df = incidentes.merge(
        ativos[["ativo_id", "ambiente", "criticidade", "sistema_operacional", "exposto_internet"]],
        on="ativo_id",
        how="left",
    )
    df[ALVO_FP] = (df[ALVO_FP].str.strip().str.lower() == "sim").astype(int)
    df["severidade_nivel"] = df["severidade"].map(NIVEL_SEVERIDADE).fillna(1).astype(int)
    return df


def _teto_bayes(df: pd.DataFrame) -> dict[str, float]:
    """Teto teorico (classificador de Bayes) dado o ruido irreduzivel do rotulo.

    O gerador sintetico sorteia `falso_positivo` com probabilidade dependente
    apenas da severidade — logo existe um limite superior alcancavel: acuracia
    de Bayes e AUC do score P(FP|severidade). Publicar o teto ao lado da metrica
    do modelo separa "modelo fraco" de "problema ruidoso por construcao".
    """
    p_fp = df.groupby("severidade")[ALVO_FP].mean()
    dist = df["severidade"].value_counts(normalize=True)
    pi = float(df[ALVO_FP].mean())
    teto_acc = float(sum(dist[s] * max(p_fp[s], 1 - p_fp[s]) for s in dist.index))
    pos = {s: float(dist[s] * p_fp[s]) / pi for s in dist.index}
    neg = {s: float(dist[s] * (1 - p_fp[s])) / (1 - pi) for s in dist.index}
    ordem = sorted(dist.index, key=lambda s: -p_fp[s])
    auc = sum(pos[a] * neg[b] for i, a in enumerate(ordem) for b in ordem[i + 1 :]) + 0.5 * sum(
        pos[s] * neg[s] for s in dist.index
    )
    return {"teto_bayes_acuracia": round(teto_acc * 100, 1), "teto_bayes_auc": round(auc * 100, 1)}


def treinar_fp(persistir: bool = True) -> dict[str, float | int | str]:
    """Treina o preditor de falso positivo e (por padrao) persiste o artefato.

    Protocolo: split estratificado 75/25 (seed fixa) + validacao cruzada
    5-fold no treino; metricas reportadas no holdout e baseline majoritario.
    """
    df = _carregar_incidentes()
    entrada = [*FEATURES_FP, "severidade_nivel"]
    x, y = df[entrada], df[ALVO_FP]

    x_treino, x_teste, y_treino, y_teste = train_test_split(
        x, y, test_size=0.25, random_state=SEED, stratify=y
    )
    pipe = Pipeline(
        [
            (
                "pre",
                ColumnTransformer(
                    [
                        ("num", "passthrough", ["severidade_nivel"]),
                        (
                            "cat",
                            OneHotEncoder(handle_unknown="ignore"),
                            [c for c in FEATURES_FP if c != "severidade"],
                        ),
                    ]
                ),
            ),
            ("clf", LogisticRegression(max_iter=1000, random_state=SEED)),
        ]
    )
    pipe.fit(x_treino, y_treino)

    prev = pipe.predict(x_teste)
    prob = pipe.predict_proba(x_teste)[:, 1]
    cv = cross_val_score(
        Pipeline(pipe.steps),
        x_treino,
        y_treino,
        cv=StratifiedKFold(5, shuffle=True, random_state=SEED),
        scoring="f1",
    )
    prevalencia = float(y.mean())
    metricas: dict[str, float | int | str] = {
        "modelo": "LogisticRegression",
        "n_total": len(df),
        "n_treino": len(x_treino),
        "n_teste": len(x_teste),
        "fp_pct": round(prevalencia * 100, 1),
        "baseline_acuracia": round(float(max(y_teste.mean(), 1 - y_teste.mean())) * 100, 1),
        "acuracia": round(float(accuracy_score(y_teste, prev)) * 100, 1),
        "precisao": round(float(precision_score(y_teste, prev, zero_division=0)) * 100, 1),
        "recall": round(float(recall_score(y_teste, prev, zero_division=0)) * 100, 1),
        "f1": round(float(f1_score(y_teste, prev, zero_division=0)) * 100, 1),
        "auc": round(float(roc_auc_score(y_teste, prob)) * 100, 1),
        "cv_f1_medio": round(float(cv.mean()) * 100, 1),
        "limiar_prevalencia": round(prevalencia, 3),
        **_teto_bayes(df),
    }

    if persistir:
        modelos = _dir_modelos()
        joblib.dump(pipe, modelos / "fp_model.joblib")
        (modelos / "fp_model.json").write_text(
            json.dumps(metricas, ensure_ascii=False, indent=2), encoding="utf-8"
        )
    return metricas


def _dir_modelos() -> Path:
    caminho = get_settings().project_root / "models"
    caminho.mkdir(parents=True, exist_ok=True)
    return caminho


@lru_cache(maxsize=1)
def _modelo_fp() -> tuple[Pipeline, dict]:
    """Carrega o artefato treinado; se inexistente, treina na hora (deterministico)."""
    artefato = _dir_modelos() / "fp_model.joblib"
    if not artefato.exists():
        treinar_fp(persistir=True)
    pipe = joblib.load(artefato)  # type: ignore[no-untyped-call]
    meta_path = _dir_modelos() / "fp_model.json"
    meta: dict = json.loads(meta_path.read_text(encoding="utf-8")) if meta_path.exists() else {}
    return pipe, meta


def prever_falso_positivo(linhas: list[dict]) -> list[dict]:
    """Aplica o preditor a incidentes (dicts com incidente_id + FEATURES_FP).

    Retorna por incidente: probabilidade de falso positivo, classe prevista e
    confianca (distancia da fronteira de decisao), ordenado do mais provavel.
    A classe usa o limiar da prevalencia historica (24%), nao 0.5 — em triagem,
    sinalizar "revisar primeiro" acima da prevalencia e a decisao util.
    """
    pipe, meta = _modelo_fp()
    df = pd.DataFrame(linhas)
    df["severidade_nivel"] = df["severidade"].map(NIVEL_SEVERIDADE).fillna(1).astype(int)
    ids = df["incidente_id"].astype(str).tolist()
    prob = pipe.predict_proba(df[[*FEATURES_FP, "severidade_nivel"]])[:, 1]
    limiar = float(meta.get("limiar_prevalencia", 0.5))
    saida = [
        {
            "incidente_id": ids[i],
            "probabilidade_fp": round(float(p), 3),
            "classe_prevista": "falso positivo" if p >= limiar else "incidente real",
            "confianca": round(float(max(p, 1 - p)), 3),
        }
        for i, p in enumerate(prob)
    ]
    return sorted(saida, key=lambda r: r["probabilidade_fp"], reverse=True)


def metricas_fp() -> dict:
    """Metricas do artefato em uso (transparencia para a UI/trace)."""
    _, meta = _modelo_fp()
    return meta


def normalizar(texto: str) -> str:
    """minusculo sem acentos — para casar valores do esquema em linguagem natural."""
    return "".join(
        c for c in unicodedata.normalize("NFD", texto.lower()) if not unicodedata.combining(c)
    )
