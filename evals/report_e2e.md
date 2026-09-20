# Avaliacao end-to-end — SentinelaSOC

Agente completo (roteamento -> ferramentas -> resposta) sobre o golden set de10 casos, 3 corrida(s) por caso (media entre corridas; 'pior' = pior cobertura).
Juiz: LLM local, temperatura 0. Casos SQL verificam numeros contra consulta de referencia executada ao vivo.

| Metrica | Valor |
|---|---|
| Cobertura de fatos (media) | 86% |
| Roteamento correto | 90% |
| Citacao do documento correto | 100% |
| Respostas com alucinacao | 0% |
| Nota media do juiz (1-5) | 4.5 |
| Latencia media por resposta | 4.6s |

| Caso | Tipo | Rota | Cita | Cobertura | Aluc. | Nota | s |
|---|---|---|---|---|---|---|---|
| anpd | rag | ok | ok | 33% (pior 0%) | nao | 2.0 | 4.7 |
| senha | rag | ok | ok | 100% (pior 100%) | nao | 5.0 | 3.7 |
| sla_cvss | rag | ok | ok | 100% (pior 100%) | nao | 5.0 | 5.0 |
| phishing_passos | rag | ok | ok | 89% (pior 67%) | nao | 4.7 | 9.9 |
| janela_prod | rag | ok | ok | 100% (pior 100%) | nao | 5.0 | 3.4 |
| criticos_abertos | sql | ok | — | 100% (pior 100%) | nao | 5.0 | 2.9 |
| fp_forca_bruta | sql | ok | — | 100% (pior 100%) | nao | 5.0 | 4.1 |
| dmz_expostos | sql | ok | — | 100% (pior 100%) | nao | 5.0 | 3.2 |
| vulns_criticas | sql | NAO | — | 33% (pior 0%) | nao | 3.0 | 5.5 |
| incidentes_2026 | sql | ok | — | 100% (pior 100%) | nao | 5.0 | 3.2 |

## Fatos nao cobertos

- anpd: Resolução CD/ANPD 15/2024
- vulns_criticas: 7 vulnerabilidades críticas abertas
