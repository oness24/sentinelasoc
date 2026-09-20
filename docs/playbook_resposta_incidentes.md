# Playbook de Resposta a Incidentes — SOC Aurora Tecnologia

Versão 3.0 | Mantido pelo SOC | Classificação: Uso Interno | Revisão: semestral

## 1. Referências normativas

Este playbook adota as práticas reconhecidas do setor e deve ser lido junto com:

- **NIST SP 800-61 Rev. 2** — Computer Security Incident Handling Guide (ciclo de resposta).
- **SANS/GIAC PICERL** — Preparation, Identification, Containment, Eradication, Recovery, Lessons Learned.
- **MITRE ATT&CK Enterprise** — taxonomia de táticas e técnicas usada na classificação de incidentes.
- **FIRST CVSS v4.0** (com legado v3.1) — pontuação de severidade técnica de vulnerabilidades.
- **ISO/IEC 27035** — gestão de incidentes de segurança da informação.
- **ISO/IEC 27037** — identificação, coleta e preservação de evidências digitais.
- **LGPD (Lei 13.709/2018), art. 48** e **Resolução CD/ANPD 15/2024** — comunicação de incidentes com dados pessoais.

Divergências entre este documento e as normas citadas são resolvidas a favor das normas.

## 2. Papéis e responsabilidades (RACI)

| Papel | Triagem | Contenção | Erradicação | Comunicação | Pós-mortem |
|---|---|---|---|---|---|
| Analista N1 | R | C | I | I | C |
| Analista N2 | A | R | R | C | R |
| Coordenador SOC | I | A | A | R | A |
| CISO | I | C | C | A | I |
| DPO (dados pessoais) | I | I | I | C (ANPD) | C |
| Infraestrutura/Apps | I | C | R | I | C |
| Jurídico | I | I | I | C (externa) | I |

R = responsável, A = aprova, C = consultado, I = informado. Nenhum analista executa contenção em produção sem registro no ticket, exceto ransomware ativo e exfiltração em andamento, em que a ação imediata prevalece e o registro ocorre em até 1 hora.

## 3. Fases da resposta (PICERL → NIST 800-61)

1. **Preparação (Preparation)**: runbooks atualizados, contatos de emergência, acessos de emergência custodiados, laboratório para reprodução, integrações EDR/SIEM validadas.
2. **Identificação (Identification)**: triagem do alerta, enriquecimento com contexto do ativo, classificação ATT&CK, decisão verdadeiro/falso positivo, definição de severidade e escopo.
3. **Contenção (Containment)**: ações para interromper o dano preservando evidências (isolamento, bloqueio, desabilitação de conta). Estratégia definida por N2.
4. **Erradicação (Eradication)**: remoção da causa raiz (malware, conta comprometida, vulnerabilidade explorada) e endurecimento para evitar reincidência.
5. **Recuperação (Recovery)**: restauração validada pelo dono do ativo, monitoramento intensificado por 14 dias, retorno ao normal declarado pelo coordenador.
6. **Lições Aprendidas (Lessons Learned)**: post-mortem blameless em até 5 dias úteis, com itens de ação rastreados até o fechamento.

## 4. Classificação de severidade

A severidade combina impacto ao negócio e confiança na evidência (alinhada à prática FIRST):

- **Crítica** — impacto confirmado: dados restritos comprometidos, ransomware ativo, exfiltração em andamento, indisponibilidade de serviço externo. Plantão acionado imediatamente; contenção em até 1 hora; CISO informado em até 30 minutos.
- **Alta** — comprometimento provável: conta privilegiada suspeita, exploração em serviço exposto, malware ativo contido pelo EDR. Primeira resposta em até 4 horas; N2 assume em até 15 minutos.
- **Média** — impacto limitado: política violada sem vazamento, alerta consistente em homologação. Primeira resposta em até 24 horas.
- **Baixa** — eventos informativos e varreduras oportunísticas. Primeira resposta em até 72 horas.

Severidade é reavaliada a cada mudança de escopo; qualquer upgrade para Crítica abre sala de crise.

## 5. Playbooks por cenário

### 5.1 Phishing — ATT&CK T1566 (T1566.001 spearphishing com anexo; T1566.002 com link)

- **Triagem/validação**: extrair remetente, domínio, URL e hashes dos anexos; cruzar destinatários com logins das últimas 72h; conferir regras de encaminhamento novas nas caixas.
- **IOCs**: remetente/domínio, URL completa, hash SHA-256 do anexo, IP de resolução.
- **Contenção**: bloqueio no gateway de e-mail e proxy/DNS; troca de senha obrigatória de quem clicou; revogação de sessões ativas.
- **Erradicação**: remoção de regras de inbox maliciosas; varredura EDR das estações dos destinatários.
- **Recuperação**: monitorar autenticações dos afetados por 7 dias.
- **Escala para Alta/Crítica** se: credencial validada pelo atacante, acesso a dados restritos ou campanha interna em progresso (indicativo de conta comprometida usada para propagação).

### 5.2 Força Bruta — ATT&CK T1110 (T1110.001 password guessing; T1110.003 password spraying)

- **Triagem/validação**: volume e origem das tentativas (IP, ASN, geovelocidade impossível); sucesso após falhas na mesma origem é comprometimento presumido.
- **IOCs**: IP/ASN de origem, contas alvo, timestamps de sucesso.
- **Contenção**: bloqueio da origem por 24h com registro em log; habilitar rate limit/CAPTCHA no serviço alvo.
- **Erradicação**: se houve sucesso — desabilitar conta, resetar credenciais, revisar MFA adicionado por atacante; mínimo severidade Alta.
- **Recuperação**: revisar ações da conta no período; monitorar novas tentativas de spray com a mesma lista de usuários.
- **Falso positivo típico**: scanner autorizado ou integração com credencial expirada — confirmar com a Infraestrutura antes de fechar.

### 5.3 Malware (execução por usuário) — ATT&CK T1204.002, com cadeia típica T1566.001 → T1204.002 → T1547/T1546 (persistência) → T1071 (C2)

- **Triagem/validação**: confirmar com EDR o processo pai, linha de comando, hash e persistência criada; buscar o mesmo hash em toda a frota.
- **IOCs**: hash, nome do artefato, caminho, processo, domínios de C2, chaves de persistência.
- **Contenção**: isolamento de rede pela console do EDR (agente ativo); se ransomware — desligar compartilhamentos e snapshots imediatamente, severidade Crítica.
- **Erradicação**: remoção de persistências; reinstalação quando a limpeza não for confiável (padrão da Aurora); reset de credenciais locais.
- **Recuperação**: varredura completa antes de religar à rede; monitoramento intensificado por 14 dias.
- **Escala para Crítica** se: criptografia em andamento, disseminação por rede ou C2 confirmado com exfiltração (abrir T1041 em paralelo).

### 5.4 DDoS — ATT&CK T1498 (T1498.001 flood direto; T1498.002 reflexão/amplificação)

- **Triagem/validação**: vetor (volumétrico UDP, amplificação, camada 7), volumetria (bps/pps/req/s), degradação percebida; confirmar com o provedor de conectividade.
- **Contenção**: ativar mitigação do provedor (scrubbing) e/ou rate limit por geografia; priorizar rotas de serviços essenciais.
- **Erradicação/Recuperação**: normalização gradual; documentar volumetria e vetores para revisão contratual e para réplica de regras permanentes.
- **Comunicação**: atualizações às áreas de negócio a cada 30 minutos enquanto durar o evento.
- **Falso positivo típico**: pico legítimo de marketing ou teste de carga não comunicado — validar agenda com o negócio.

### 5.5 Exfiltração de Dados — ATT&CK T1041 (Exfiltration Over C2) e T1048 (canal alternativo)

- **Triagem/validação**: volume por destino/protocolo, baseline do ativo, processo e conta responsáveis, destino recém-registrado ou hostilha em inteligência.
- **IOCs**: destino IP/domínio, porta/protocolo, soma de bytes, janela temporal, processo.
- **Contenção**: bloqueio do destino, interrupção de transferências, isolamento do ativo.
- **Erradicação**: remover acesso e malware usados no canal; rotacionar credenciais e chaves de API do ativo.
- **Obrigações legais**: se dados pessoais estão envolvidos, o DPO avalia a comunicação à ANPD e aos titulares — a Resolução CD/ANPD 15/2024 fixa o prazo de **2 dias úteis** a contar da ciência do incidente com risco relevante. Preservar tráfego completo para perícia.
- **Escala**: sempre Crítica quando confirmada.

### 5.6 Acesso Anômalo (contas válidas) — ATT&CK T1078

- **Triagem/validação**: comparar com a baseline do usuário (horário, geografia, user-agent, volume); confirmar com o gestor; login de país novo + MFA satisfeito por token novo é alta suspeita (MFA fatigue/bombing: T1621).
- **Contenção**: forçar reautenticação com MFA; se persistir, desabilitar a conta e revogar sessões e tokens de refresh.
- **Erradicação**: remover regras/OAuth apps maliciosos concedidos; reset de credenciais.
- **Recuperação**: revisar ações do período (downloads, mudanças de permissão, criação de contas) e reverter alterações indevidas.
- **Falso positivo típico**: viagem corporativa ou VPN nova — validar com o gestor antes de fechar.

### 5.7 Vulnerabilidade Explorada — ATT&CK T1190 (Exploit Public-Facing Application)

- **Triagem/validação**: evidência objetiva de exploração (padrões no access log, WAF, crash suspeito, shell web) — a existência da CVE sem tráfego anômalo NÃO é incidente, é gestão de vulnerabilidade.
- **IOCs**: payloads, URIs exploradas, IP de origem, timestamp, artefatos deixados.
- **Contenção**: regra de bloqueio virtual no WAF, desativação do componente vulnerável ou isolamento do ativo.
- **Erradicação**: correção emergencial com a Infraestrutura (janela crítica da DMZ) e verificação de integridade dos dados.
- **Recuperação**: nova varredura confirmando remediação em até 3 dias; monitoramento do ativo por 14 dias.
- **Escala para Crítica** se houver indício de pós-exploração (abrir T1078/T1048 em paralelo).

### 5.8 Engenharia Social — ATT&CK T1598 (Phishing for Information)

- **Triagem/validação**: registrar o relato do colaborador, identidade alegada, canais e dados solicitados; verificar se algum dado foi entregue.
- **Contenção**: alertar as áreas citadas; bloquear contatos usados (número, e-mail, perfis).
- **Erradicação/Recuperação**: classificar o dano pelo que foi entregue; se credenciais — tratar como 5.2/5.6.
- **Recuperação comportamental**: incluir o caso anonimizado no programa de conscientização; reforçar que nenhum processo da Aurora solicita senhas ou códigos MFA.

## 6. Gestão de evidências (ISO/IEC 27037)

- Toda evidência relevante é coletada com hash (SHA-256) registrado no ticket, armazenada no cofre de evidências e mantida sob cadeia de custódia (quem coletou, quando, como, quem acessou).
- Ordem de volatilidade (RFC 3227): memória → sessões/estado → discos → logs remotos/arquivos.
- Evidências de incidentes com potencial legal são retidas por 5 anos ou até ordem contrária do jurídico.
- Acesso a evidências é restrito a N2 e ao coordenador, com log de auditoria.

## 7. Comunicação

- **Interna**: sala de crise para Críticas, com ata de decisões; atualizações a cada 60 minutos ao comitê.
- **Gestão**: resumo diário de Altas e métricas da semana (MTTD, MTTR, taxa de falsos positivos).
- **Externa (clientes, imprensa, autoridades)**: responsabilidade exclusiva da diretoria com o jurídico; analistas não emitem comunicação externa.
- **Regulatória (LGPD)**: DPO conduz; prazo de 2 dias úteis para comunicação à ANPD quando houver risco relevante aos titulares.

## 8. Pós-incidente e métricas

- Post-mortem blameless em até 5 dias úteis do fechamento: linha do tempo, causa raiz, escopo, impacto, o que funcionou, o que falhou, itens de ação com dono e prazo.
- Métricas obrigatórias do SOC: MTTD (tempo médio de detecção), MTTR (tempo médio de resolução), taxa de falsos positivos por tipo, reincidência por ativo, percentual dentro dos SLAs de severidade.
- Itens de ação são revisados no comitê mensal até a verificação de eficácia; reincidência do mesmo cenário após ação fechada reabre o item com prioridade máxima.

## 9. Tabela de decisão rápida

| Situação | Severidade inicial | Ação imediata |
|---|---|---|
| Ransomware criptografando | Crítica | Isolar host + desligar compartilhamentos + sala de crise |
| Credencial privilegiada validada por atacante | Crítica | Desabilitar conta + revogar sessões + N2 |
| Exfiltração confirmada | Crítica | Bloquear destino + preservar tráfego + DPO |
| Phishing sem clique | Baixa | Bloquear campanha + conscientizar |
| Tentativas falhas de login, sem sucesso | Baixa/Média | Bloquear origem 24h + rate limit |
| CVE crítica em ativo exposto, sem tráfego anômalo | Alta (Infra) | Tratar pelo guia de vulnerabilidades |
