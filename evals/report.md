# Avaliacao do pipeline RAG — SentinelaSOC

Golden set: 12 perguntas reais de triagem (evals/golden.json).
Metricas sobre a recuperacao semantica (sem LLM no circuito).

| Modelo | Chunks | hit@1 | hit@3 | MRR | dist. media top-1 | tempo (s) |
|---|---|---|---|---|---|---|
| `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2` | 48 | 92% | 100% | 0.96 | 0.438 | 4.8 |
| `intfloat/multilingual-e5-small` | 48 | 83% | 100% | 0.92 | 0.115 | 6.1 |

## Detalhe por pergunta (modelo avaliado por ultimo)

| Pergunta | Doc esperado | Rank | Top-1 | Dist. top-1 |
|---|---|---|---|---|
| qual o prazo para comunicar a ANPD em incidente com dados pe | playbook_resposta_incidentes.md | 1 | playbook_resposta_incidentes.md | 0.129 |
| quantos caracteres deve ter uma senha e com quais requisitos | politica_de_seguranca.md | 1 | politica_de_seguranca.md | 0.091 |
| qual o primeiro passo ao receber um alerta? | faq_triagem.md | 1 | faq_triagem.md | 0.072 |
| qual o SLA para corrigir vulnerabilidade critica? | guia_gestao_vulnerabilidades.md | 1 | guia_gestao_vulnerabilidades.md | 0.117 |
| como responder a um incidente de ransomware? | playbook_resposta_incidentes.md | 2 | faq_triagem.md | 0.119 |
| posso usar pen drive na empresa? | politica_de_seguranca.md | 1 | politica_de_seguranca.md | 0.148 |
| quem aprova excecao ao SLA de correcao de vulnerabilidade? | guia_gestao_vulnerabilidades.md | 1 | guia_gestao_vulnerabilidades.md | 0.136 |
| phishing sem clique em anexo: qual severidade inicial? | playbook_resposta_incidentes.md | 1 | playbook_resposta_incidentes.md | 0.108 |
| para quais acessos o MFA e obrigatorio? | politica_de_seguranca.md | 1 | politica_de_seguranca.md | 0.131 |
| em quanto tempo o CISO deve ser comunicado em incidente crit | playbook_resposta_incidentes.md | 2 | politica_de_seguranca.md | 0.122 |
| qual a janela de correcao em producao? | guia_gestao_vulnerabilidades.md | 1 | guia_gestao_vulnerabilidades.md | 0.12 |
| como decido entre falso positivo e incidente verdadeiro? | faq_triagem.md | 1 | faq_triagem.md | 0.089 |
