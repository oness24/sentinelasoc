# Política de Segurança da Informação — Aurora Tecnologia

Versão 3.2 | Aprovada pelo Comitê de Segurança em 10/01/2026 | Classificação: Uso Interno

## 1. Objetivo

Estabelecer as diretrizes de segurança da informação da Aurora Tecnologia para proteger a confidencialidade, a integridade e a disponibilidade dos ativos corporativos, dos dados dos clientes e dos serviços prestados.

Esta política é alinhada às práticas da **ISO/IEC 27001:2022** (SGSI) e do **NIST Cybersecurity Framework 2.0** (funções Govern, Identify, Protect, Detect, Respond, Recover), e cumpre a **LGPD (Lei 13.709/2018)** no tratamento de dados pessoais. Os controles operacionais detalhados seguem o guia da ISO/IEC 27002:2022.

## 2. Classificação da Informação

Toda informação da Aurora recebe uma das quatro classificações:

- **Pública**: informações liberadas para divulgação (material de marketing, vagas abertas).
- **Interna**: informações de uso corporativo cujo vazamento causa dano moderado (organogramas, processos internos).
- **Confidencial**: dados cuja exposição causa dano alto (dados financeiros, contratos, código-fonte). Acesso somente por necessidade de saber.
- **Restrita**: dados regulados (dados pessoais de clientes conforme LGPD, credenciais, chaves criptográficas, registros de auditoria de segurança). Acesso registrado em log e revisado trimestralmente.

Dados pessoais de clientes são sempre classificados como Restritos, independentemente do sistema em que estejam armazenados.

## 3. Política de Senhas e Credenciais

- Senhas devem ter no mínimo 12 caracteres, com letras maiúsculas, minúsculas, números e símbolos.
- Senhas não podem ser reutilizadas entre sistemas corporativos e pessoais.
- A troca obrigatória de senhas ocorre a cada 180 dias para contas administrativas e a cada 365 dias para contas comuns.
- Contas administrativas (admin, root) devem utilizar autenticação multifator (MFA) obrigatoriamente. Contas comuns devem utilizar MFA para acesso remoto (VPN e webmail).
- Senhas nunca são compartilhadas por e-mail, chat ou telefone. O compartilhamento de credenciais é falta grave, sujeita a sanções disciplinares.
- Cofres de senha (vault) são a única forma permitida de armazenamento compartilhado de segredos técnicos.

## 4. Controle de Acesso

- O acesso é concedido por perfil de função (RBAC) e segue o princípio do menor privilégio.
- Cada colaborador possui uma conta individual identificável. Contas genéricas são proibidas, exceto para equipamentos de fábrica, e devem ter custodiante formal.
- A revisão de acessos ocorre trimestralmente pelos gestores das áreas.
- O desligamento de colaborador exige revogação imediata de todos os acessos em até 4 horas úteis, coordenada pelo RH com a Infraestrutura.
- Terceiros e prestadores de serviço recebem acesso temporário com validade máxima de 90 dias, renovável mediante justificativa.

## 5. Uso Aceitável de Recursos

- Os recursos de TI são destinados ao trabalho. Uso pessoal moderado é tolerado, desde que não exponha a empresa a risco.
- É proibido instalar software não autorizado, desativar ferramentas de segurança (antivírus, EDR, agente de inventário) ou conectar equipamentos pessoais à rede corporativa sem aprovação da Infraestrutura.
- É proibido usar ferramentas de IA generativa com dados classificados como Confidenciais ou Restritos, exceto nas soluções homologadas pelo Comitê de Segurança.
- O uso de pen drives e mídias removíveis é restrito a dispositivos corporativos criptografados.

## 6. Segurança de Redes

- A rede corporativa é segmentada em zonas: DMZ (serviços expostos à internet), Rede Interna (estações e servidores de aplicação), Rede Administrativa (gerência de equipamentos) e Laboratório.
- Todo serviço exposto à internet deve passar por revisão de segurança e permanecer protegido por WAF quando aplicável.
- Acesso remoto somente via VPN corporativa com MFA.
- Wi-Fi de visitantes é isolado da rede interna e possui senha rotativa mensal.

## 7. Registro e Monitoramento

- Os logs de sistemas críticos (autenticação, firewalls, servidores DMZ, bancos de dados) são centralizados no SIEM e retidos por 12 meses.
- O SOC da Aurora opera em horário comercial (8h às 18h, dias úteis) com plantão de sobreaviso para incidentes críticos.
- Eventos de segurança suspeitos devem ser comunicados ao SOC em até 1 hora após a detecção pelo canal sec-ops@aurora.example.

## 8. Backup e Continuidade

- Backups diários dos dados críticos, com retenção de 30 dias online e 12 meses em cópia offline.
- Testes de restauração trimestrais obrigatórios.
- O RPO (ponto objetivo de recuperação) é de 24 horas e o RTO (tempo objetivo de recuperação) é de 8 horas para sistemas críticos.

## 9. Sanções

O descumprimento desta política está sujeito a medidas disciplinares conforme o regime interno de trabalho, podendo incluir advertência, suspensão ou desligamento, sem prejuízo das responsabilidades civis e penais cabíveis.
