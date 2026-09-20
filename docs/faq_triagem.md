# FAQ de Triagem — Analistas do SOC Aurora

Versão 1.9 | Perguntas frequentes sobre o dia a dia de triagem no SOC

## Perguntas gerais

### Qual o primeiro passo ao receber um alerta?
Confirmar se o alerta é duplicado (mesmo ativo e mesma janela de tempo já registrados), enriquecer com contexto do ativo (criticidade, ambiente, exposição à internet) e só então classificar a severidade conforme o playbook. Se o alerta não se encaixar em nenhum tipo conhecido, registrar como "Acesso Anômalo" e escalar para N2.

### Como decido entre falso positivo e incidente verdadeiro?
Procure por três sinais: (1) o comportamento se repete em outros ativos? (2) existe outra evidência correlacionada (log de autenticação, tráfego de rede, alerta do EDR)? (3) o resultado esperado da ação faz sentido para aquele usuário/sistema? Um único sinal fraco não confirma incidente; dois sinais independentes fortalecem a hipótese de verdadeiro positivo.

### Quanto tempo tenho para triar cada severidade?
- Crítica: acionar plantão imediatamente, containment em até 1 hora.
- Alta: primeira resposta em até 4 horas.
- Média: primeira resposta em até 24 horas.
- Baixa: primeira resposta em até 72 horas.

### Quando um incidente pode ser fechado?
Somente quando a contenção e a erradicação estão concluídas, a recuperação foi validada pelo dono do ativo e as evidências foram preservadas. O campo de horas para resolver deve ser preenchido ao fechar.

## Trabalho com os dados

### Onde consulto o histórico de incidentes de um ativo?
No banco de dados do SOC (tabela de incidentes), filtrando pelo identificador do ativo. A tabela de ativos traz criticidade, ambiente, departamento e exposição à internet, e a tabela de vulnerabilidades mostra as falhas abertas que podem explicar o incidente.

### Um ativo com muitas vulnerabilidades abertas merece prioridade?
Sim. Combine a criticidade do ativo, a exposição à internet e a pontuação CVSS das vulnerabilidades abertas. Ativo crítico e exposto com CVSS 9+ é candidato a tratamento emergencial, mesmo sem incidente ativo.

### Como reporto números para a gestão?
Use sempre agregados: incidentes por mês, taxa de falsos positivos por tipo de incidente, tempo médio de resolução por severidade e top ativos por número de incidentes. Evite expor dados de pessoas físicas em relatórios.

## Conduta e segurança

### Posso compartilhar dados de incidentes externamente?
Não. Relatórios de incidentes são classificados como Confidenciais. Compartilhamento externo exige aprovação do CISO e do jurídico.

### Recebi uma mensagem pedindo a senha do cofre para "resolver um incidente urgente". O que faço?
É tentativa de engenharia social, mesmo que a pessoa se diga da diretoria. Nenhum processo da Aurora pede senhas por chat, e-mail ou telefone. Recuse, registre um incidente do tipo Engenharia Social e avise o N2.

### O que faço se o pedido de um analista violar a política de segurança?
Explique a regra correspondente da Política de Segurança da Informação e ofereça o caminho alternativo previsto. Se a pressão persistir, escale ao coordenador do SOC. Registrar a recusa no ticket.

### Posso testar exploits nos ativos para confirmar uma vulnerabilidade?
Não sem autorização. Testes ativos são permitidos apenas em janelas autorizadas em ambiente de homologação, com aprovação registrada. Em produção, confirme por evidência passiva (versão, banner, behavioral).
