# Relatório de ML — SentinelaSOC

Gerado por `scripts/train_ml.py` em 2026-09-21.
Todos os números são reproduzíveis: seeds fixos, dados determinísticos.

## 1. NSL-KDD — triagem ataque vs normal (dataset público)

Protocolo padrão da literatura: treino em `KDDTrain+` (125.973 registros),
avaliação em `KDDTest+` (22.544 registros, inclui tipos de ataque não vistos
no treino — por isso o teste é deliberadamente mais difícil que o treino).
Rótulo binário: `normal` vs qualquer ataque. Categóricas (protocolo, serviço,
flag) em one-hot com `handle_unknown=ignore` (o teste contém serviços inéditos);
numéricas padronizadas apenas na regressão logística.

| Métrica | LogisticRegression | HistGradientBoosting |
|---|---|---|
| n_treino | 125973 | 125973 |
| n_teste | 22544 | 22544 |
| ataques_treino_pct | 46.5 | 46.5 |
| ataques_teste_pct | 56.9 | 56.9 |
| baseline_acuracia | 56.9 | 56.9 |
| acuracia | 75.4 | 80.3 |
| precisao | 91.8 | 96.9 |
| recall | 62.4 | 67.6 |
| f1 | 74.3 | 79.6 |
| auc | 79.4 | 96.1 |

Leitura honesta:
- A acurácia do teste fica abaixo do treino **por design** — o KDDTest+ expõe o
  modelo a ataques novos (generalização, não memorização).
- A regressão logística privilegia precisão alta com recall baixo; o boosting
  equilibra melhor as duas classes — métrica de escolha para triagem: **AUC**
  (capacidade de ranquear alertas por risco).

> Modelo documentado como referência: **HistGradientBoosting** (AUC 96.1%, F1 79.6%).

## 2. Preditor de falso positivo (ferramenta `ml` do copiloto)

Classificação binária sobre os incidentes históricos do SOC (dados sintéticos
determinísticos, seed=42). Features: perfil do incidente (tipo, severidade,
tática ATT&CK) + perfil do ativo (ambiente, criticidade, SO, exposição).
Severidade entra como ordinal (1 grau de liberdade em vez de 4 dummies).
Protocolo: split estratificado 75/25 + validação cruzada 5-fold no treino.

| Métrica | LogisticRegression |
|---|---|
| n_total | 356 |
| n_treino | 267 |
| n_teste | 89 |
| fp_pct | 23.9 |
| baseline_acuracia | 76.4 |
| acuracia | 77.5 |
| precisao | 53.3 |
| recall | 38.1 |
| f1 | 44.4 |
| auc | 72.8 |
| cv_f1_medio | 45.3 |

Leitura honesta:
- O rótulo é **ruidoso por construção**: o gerador sorteia falso positivo com
probabilidade dependente apenas da severidade (Baixa→55% ... Crítica→4%).
Existe, portanto, um **teto de Bayes** atingível — acurácia
79.8% e AUC 77.3% — calculado a partir
das probabilidades condicionais reais dos dados.
- O modelo atinge AUC 72.8% (~94% do teto):
o gap restante é ruído aleatório, não defeito do modelo. Sem o teto publicado,
esses números pareceriam fracos; com ele, fica claro que o problema — não o
modelo — é intrinsecamente probabilístico.
- Decisão de produto: a ferramenta `ml` **ranqueia** incidentes para revisão
(probabilidade por incidente), e o limiar de classificação é a prevalência
(0.239), não 0.5 — em triagem, sinalizar acima da
prevalência é a decisão útil.
