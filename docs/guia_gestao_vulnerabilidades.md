# Guia de Gestão de Vulnerabilidades — Aurora Tecnologia

Versão 2.1 | Emitido pela equipe de Infraestrutura e Security | Classificação: Uso Interno

## 1. Objetivo e escopo

Definir o ciclo de identificação, classificação, correção e verificação de vulnerabilidades técnicas nos ativos da Aurora Tecnologia, cobrindo servidores, estações, serviços expostos e componentes de rede.

## 2. Fontes de detecção

- Varreduras automatizadas autenticadas a cada 7 dias na rede interna e a cada 3 dias na DMZ.
- Varreduras de aplicação web após cada deploy em produção.
- Boletins de segurança de fornecedores monitorados diariamente.
- Resultados de testes de intrusão anuais e avaliações de código.

## 3. Prazos de correção (SLA)

| CVSS | Classificação | SLA de correção |
|------|---------------|-----------------|
| 9.0 a 10.0 | Crítica | 7 dias |
| 7.0 a 8.9 | Alta | 14 dias |
| 4.0 a 6.9 | Média | 30 dias |
| 0.1 a 3.9 | Baixa | 90 dias ou janela padrão |

Exceções ao SLA exigem registro formal de risco aceito, assinado pelo dono do ativo e pelo CISO, com compensação de controle (por exemplo, regra de bloqueio virtual ou isolamento de rede) e data limite para revisão.

## 4. Priorização

A prioridade de correção considera quatro fatores, em ordem:

1. Exposição do ativo à internet (DMZ primeiro).
2. Criticidade do ativo para o negócio.
3. Existência de exploração ativa conhecida (KEV) ou de prova de conceito pública.
4. Idade da vulnerabilidade — vulneridades além do SLA entram na lista de cobrança semanal.

## 5. Janela de correção

- Produção: terças-feiras, das 22h às 2h, com aprovação da mudança até segunda-feira ao meio-dia.
- DMZ e serviços expostos: janela diária de 30 minutos para correções críticas, agendada com no mínimo 4 horas de antecedência.
- Homologação: aplicação livre durante o horário comercial, preferencialmente pela manhã.

## 6. Verificação e fechamento

Após aplicar a correção, uma nova varredura deve confirmar a remediação em até 3 dias. A vulnerabilidade só muda para status "Corrigida" com essa evidência. Correções por mitigação parcial permanecem "Em correção" até a solução definitiva.

## 7. Métricas e reporte

O comitê mensal de segurança acompanha: total de vulnerabilidades abertas por classificação, percentual dentro do SLA, idade média por departamento e reincidência (mesma CVE no mesmo ativo após correção). Ativos com reincidência entram em plano de ação com a Infraestrutura.

## 8. Integração com o SOC

Vulnerabilidades com CVSS 9+ em ativos expostos são notificadas automaticamente ao SOC, que monitora os logs desses ativos por 14 dias em busca de tentativas de exploração. Um incidente do tipo "Vulnerabilidade Explorada" só é aberto com evidência de exploração, não pela mera existência da falha.
