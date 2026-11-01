# Avaliacao end-to-end — SentinelaSOC

Agente completo (roteamento -> ferramentas -> resposta) sobre o golden set de 10 casos, 3 corrida(s) por caso (media entre corridas; 'pior' = pior cobertura).
Juiz: LLM local, temperatura 0. Casos SQL verificam numeros contra consulta de referencia executada ao vivo.

| Metrica | Valor |
|---|---|
| Cobertura de fatos (media) | 79% |
| Roteamento correto | 80% |
| Citacao do documento correto | 100% |
| Respostas com alucinacao | 0% |
| Nota media do juiz (1-5) | 4.2 |
| Latencia media por resposta | 6.3s |

## Metricas DeepEval-equivalente

| Metrica | Definicao | Valor |
|---|---|---|
| **Faithfulness** | afirmacoes da resposta sustentadas pelas evidencias recuperadas | 98% |
| **Answer relevancy** | resposta endereca o que a pergunta pede (0-1) | 98% |
| **SQL correctness** | consulta gerada == consulta de referencia (executadas ao vivo) | 100% |

| Caso | Tipo | Rota | Cita | Fidel. | Relev. | SQL | Cobertura | Aluc. | Nota | s |
|---|---|---|---|---|---|---|---|---|---|---|
| anpd | rag | ok | ok | 100% | 100% | — | 33% (pior 0%) | nao | 2.0 | 6.1 |
| senha | rag | ok | ok | 100% | 100% | — | 83% (pior 50%) | nao | 4.3 | 7.0 |
| sla_cvss | rag | ok | ok | 100% | 100% | — | 100% (pior 100%) | nao | 5.0 | 4.7 |
| phishing_passos | rag | ok | ok | 90% | 100% | — | 78% (pior 67%) | nao | 3.7 | 9.2 |
| janela_prod | rag | ok | ok | 100% | 100% | — | 100% (pior 100%) | nao | 5.0 | 4.8 |
| criticos_abertos | sql | ok | — | 100% | 100% | 100% | 100% (pior 100%) | nao | 5.0 | 4.7 |
| fp_forca_bruta | sql | NAO | — | 100% | 100% | — | 100% (pior 100%) | nao | 5.0 | 7.0 |
| dmz_expostos | sql | ok | — | 100% | 100% | 100% | 100% (pior 100%) | nao | 5.0 | 4.4 |
| vulns_criticas | sql | NAO | — | 92% | 83% | — | 0% (pior 0%) | nao | 2.0 | 9.6 |
| incidentes_2026 | sql | ok | — | 100% | 100% | 100% | 100% (pior 100%) | nao | 5.0 | 4.9 |

## Fatos nao cobertos

- anpd: prazo de 2 dias úteis
- anpd: Resolução CD/ANPD 15/2024
- senha: letras maiúsculas, minúsculas, números e símbolos
- phishing_passos: monitorar por 7 dias
- vulns_criticas: 7 vulnerabilidades críticas abertas

## Tendencia entre execucoes

| Execucao | Runs | Cobertura | Fidel. | Relev. | SQL | Aluc. | Nota | Lat. |
|---|---|---|---|---|---|---|---|---|
| 2026-11-01T10:30-03:00 | 3 | 83% | 99% | 97% | 100% | 0% | 4.4 | 6.8s |
| 2026-11-01T10:37-03:00 | 3 | 80% | 98% | 98% | 100% | 0% | 4.2 | 6.3s |
