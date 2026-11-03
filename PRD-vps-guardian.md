# PRD --- VPS Guardian

**Versão:** 1.1\
**Data:** 03/11/2026\
**Status:** Aprovado como especificação-base; execução controlada pelo
ROADMAP.md\
**Nome provisório:** VPS Guardian

------------------------------------------------------------------------

## 1. Visão geral

O VPS Guardian será uma plataforma própria, centralizada e
auto-hospedada para monitorar nove servidores VPS Linux, consolidando
métricas, disponibilidade, serviços e alertas em um único painel web.

A plataforma deverá utilizar componentes open source e infraestrutura já
disponível, evitando dependência de painéis comerciais ou serviços pagos
de monitoramento.

A central será hospedada inicialmente em uma das nove VPS existentes. Os
demais servidores executarão um agente leve, responsável por coletar
métricas locais e enviá-las à central por conexão de saída HTTPS.

Os alertas serão enviados ao WhatsApp por meio da infraestrutura já
existente: **EvoGo/Evolution API + n8n**. O backend do VPS Guardian será
responsável por detectar eventos, aplicar regras, controlar duplicidade
e registrar notificações. O n8n fará a integração/orquestração do envio.

O banco de dados será **MySQL**, utilizando a instância/serviço MySQL
disponível no Easypanel. PostgreSQL (não utilizado neste projeto) não
faz parte da arquitetura desta versão.

### 1.1 Objetivos principais

-   Monitorar nove VPS em um painel único.
-   Detectar indisponibilidade de servidores e serviços.
-   Coletar CPU, memória RAM, disco, rede e uptime.
-   Monitorar Docker e containers, inclusive nos ambientes com Easypanel
    e Portainer.
-   Monitorar portas, domínios e endpoints HTTP/HTTPS configurados.
-   Criar regras de alerta personalizadas.
-   Enviar alertas e recuperações ao WhatsApp.
-   Manter histórico de métricas, incidentes e notificações.
-   Permitir expansão para mais servidores sem reformular a arquitetura.

### 1.2 Fora do escopo da primeira versão

-   Executar comandos administrativos recebidos pelo WhatsApp.
-   Reiniciar servidores, containers ou serviços automaticamente.
-   Acesso remoto interativo por SSH.
-   Análise avançada de logs ou SIEM.
-   Correção automática de incidentes.
-   Dependência de serviços comerciais de observabilidade.

Essas funções poderão ser avaliadas em uma segunda etapa, com o Hermes
Agent como camada de interpretação e execução controlada, conforme a
seção 14.

------------------------------------------------------------------------

## 2. Contexto da infraestrutura

### 2.1 Ambiente atual

  ---------------------------------------------------------------------
  Item                               Quantidade / tecnologia
  ---------------------------------- ----------------------------------
  Total de VPS                       9

  Sistema operacional                Ubuntu 22.04/24.04 (inventariar a
                                     versão exata de cada host antes da
                                     instalação)

  Easypanel                          7 VPS

  Portainer                          1 VPS

  Painel ICP da Integrator           1 VPS

  WhatsApp                           EvoGo / Evolution API

  Automação de mensagens             n8n

  Banco de dados do projeto          MySQL no Easypanel

  Hospedagem inicial da central      Uma das nove VPS existentes
  ---------------------------------------------------------------------

O agente deverá ser independente do painel de hospedagem. A coleta
básica deve funcionar em Ubuntu mesmo quando não houver Easypanel ou
Portainer.

### 2.2 Premissa de conectividade

A comunicação será iniciada pelo agente em cada VPS em direção à
central. Não será necessário expor uma porta de entrada em cada servidor
para receber conexões do monitor.

Fluxo:

1.  Agente coleta dados localmente.
2.  Agente envia payload autenticado por HTTPS à central.
3.  Backend valida identidade e registra a telemetria.
4.  Motor de regras avalia limites e condições.
5.  Incidentes são persistidos no MySQL.
6.  Backend aciona webhook do n8n.
7.  n8n envia a mensagem pelo EvoGo/Evolution API.
8.  Retorno de envio é registrado para auditoria.

A central também deverá executar verificações externas de
disponibilidade para os alvos configurados, como HTTP/HTTPS e portas
TCP. A ausência de heartbeat do agente será um sinal independente de
indisponibilidade.

------------------------------------------------------------------------

## 3. Perfis e permissões

### 3.1 Administrador

-   Acessar todas as VPS.
-   Cadastrar, editar, pausar e remover servidores.
-   Gerar, revogar e rotacionar tokens de agentes.
-   Configurar limites e regras de alerta.
-   Configurar integrações com n8n.
-   Consultar histórico, incidentes e notificações.
-   Gerenciar usuários e permissões, caso múltiplos usuários sejam
    habilitados.

### 3.2 Operador (opcional na primeira versão)

-   Visualizar dashboard e detalhes dos servidores.
-   Consultar incidentes e histórico.
-   Reconhecer incidentes.
-   Não pode alterar integrações, credenciais ou configurações críticas.

A primeira entrega poderá iniciar com um único usuário administrador,
mas a estrutura de autorização deve permitir expansão.

------------------------------------------------------------------------

## 4. Escopo funcional

### 4.1 Cadastro e gestão de servidores

Cada servidor deverá possuir:

-   Nome amigável.
-   Identificador único (UUID).
-   Endereço IP ou hostname.
-   Ambiente (produção, homologação, desenvolvimento ou outro).
-   Provedor (campo informativo).
-   Sistema operacional e versão.
-   Tipo de painel: Easypanel, Portainer, ICP Integrator ou
    nenhum/outro.
-   Localização/região (campo opcional).
-   Tags.
-   Intervalo de heartbeat.
-   Estado: ativo, pausado ou desativado.
-   Data do cadastro e última comunicação.
-   Token individual do agente, armazenado de forma segura ou em formato
    não recuperável após emissão.

A interface deverá permitir gerar o comando de instalação do agente com
token de provisionamento de uso único ou validade curta. Não colocar
tokens permanentes em URLs públicas ou logs.

### 4.2 Métricas do host

O agente deverá coletar, no mínimo:

  ---------------------------------------------------------------------
  Métrica                            Dados
  ---------------------------------- ----------------------------------
  CPU                                Percentual de utilização,
                                     quantidade de núcleos e load
                                     average

  RAM                                Total, utilizada, disponível e
                                     percentual

  Swap                               Total, utilizada e percentual

  Disco                              Total, utilizado, disponível e
                                     percentual por ponto de montagem

  Rede                               Bytes recebidos/enviados e taxas
                                     por intervalo

  Uptime                             Tempo desde a inicialização

  Sistema                            Distribuição, versão, kernel e
                                     arquitetura

  Agente                             Versão, estado e horário da última
                                     coleta
  ---------------------------------------------------------------------

As métricas devem conter timestamp UTC e identificação do servidor. O
frontend deverá exibir horário no fuso configurado pelo usuário,
inicialmente America/Sao_Paulo.

### 4.3 Monitoramento de Docker

Quando Docker estiver instalado, o agente deverá detectar
automaticamente sua disponibilidade e coletar:

-   Estado do daemon Docker.
-   Quantidade de containers em execução, parados e em estado de
    reinicialização, quando disponível.
-   Nome, ID abreviado, imagem e estado de cada container.
-   Política de reinicialização, quando disponível.
-   CPU e memória por container, quando suportado pela API do Docker.
-   Mudanças de estado observadas entre coletas.

Requisitos de compatibilidade:

-   Easypanel: monitorar o Docker subjacente, sem depender de APIs
    privadas do painel.
-   Portainer: monitorar o Docker subjacente; integração específica com
    Portainer fica opcional.
-   ICP Integrator: monitoramento básico do host e Docker, caso
    instalado e acessível ao agente.
-   VPS sem Docker: exibir Docker como "não instalado" ou "não
    detectado", sem gerar alerta indevido.

O agente deverá ter acesso somente de leitura às informações do Docker.
Não conceder acesso de controle na primeira versão.

### 4.4 Monitoramento de portas, domínios e endpoints

A central permitirá cadastrar verificações:

-   HTTP e HTTPS por URL.
-   Código HTTP esperado ou conjunto de códigos aceitos.
-   Tempo máximo de resposta.
-   Porta TCP e host de destino.
-   Intervalo e timeout de verificação.
-   Quantidade de falhas consecutivas antes de abrir incidente.
-   Quantidade de sucessos consecutivos para considerar recuperação.

Exemplos: painel administrativo, API, site, webhook, banco de dados
(somente teste de conectividade de porta, sem autenticação), SSH e
serviços web.

As verificações devem ser executadas a partir da central. O painel
deverá deixar claro que um teste de porta confirma conectividade, não a
saúde interna completa da aplicação.

### 4.5 Heartbeat e estado do servidor

O agente enviará heartbeat em intervalo configurável, inicialmente a
cada 30 segundos.

Estados propostos:

-   **Online:** heartbeat recebido dentro da janela esperada.
-   **Atenção:** comunicação atrasada ou agente reportando degradação.
-   **Offline:** heartbeat ausente após limite de tolerância e
    verificações consecutivas.
-   **Pausado:** monitoramento desabilitado manualmente.
-   **Não provisionado:** servidor cadastrado, mas agente ainda não
    conectado.

A central deverá diferenciar "agente sem comunicação" de "host
comprovadamente desligado". A ausência de heartbeat não prova,
isoladamente, que o servidor está desligado.

------------------------------------------------------------------------

## 5. Motor de alertas

### 5.1 Regras iniciais sugeridas

Os limites deverão ser configuráveis globalmente e individualmente por
servidor.

  ---------------------------------------------------------------------
  Evento                            Padrão inicial Persistência /
                                                   confirmação
  -------------------- --------------------------- --------------------
  CPU alta                                  \> 85% 3 minutos

  RAM alta                                  \> 90% 2 minutos

  Disco alto                                \> 85% 1 verificação;
                                                   crítico em \> 90%

  Swap alta                                 \> 80% 3 minutos

  Host sem heartbeat         3 intervalos perdidos Confirmar com
                                                   tolerância
                                                   configurada

  Container parado               Estado inesperado 2 verificações,
                                                   configurável

  Endpoint                          Falha HTTP/TCP 3 falhas
  indisponível                                     consecutivas

  Latência elevada      Acima do limite cadastrado 3 verificações
                                                   consecutivas

  SSL próximo do                           15 dias Alertas em marcos
  vencimento                                       configuráveis
  ---------------------------------------------------------------------

Os valores são padrões iniciais, não limites universais. Devem ser
ajustados conforme a capacidade e o perfil de cada VPS.

### 5.2 Severidade

-   **Informativo:** mudança relevante sem impacto imediato.
-   **Atenção:** condição que merece acompanhamento.
-   **Crítico:** indisponibilidade ou risco elevado.

### 5.3 Antirruído e deduplicação

O sistema deverá:

-   Abrir um incidente quando a condição ultrapassar os critérios.
-   Enviar uma notificação inicial por incidente.
-   Não repetir a mesma mensagem a cada coleta.
-   Permitir lembrete periódico configurável enquanto o incidente
    permanecer aberto.
-   Agrupar eventos equivalentes por servidor, métrica e regra.
-   Enviar notificação de recuperação quando a condição normalizar.
-   Permitir silenciar uma regra ou servidor por período definido.
-   Registrar falhas no envio de notificações e permitir nova tentativa
    com backoff.

### 5.4 Reconhecimento de incidentes

O administrador poderá marcar um incidente como reconhecido, registrando
usuário e horário. Reconhecer não significa resolver: o incidente
permanece aberto até a condição normalizar ou ser encerrado manualmente
com justificativa.

------------------------------------------------------------------------

## 6. Integração WhatsApp: n8n + EvoGo

### 6.1 Arquitetura escolhida

O VPS Guardian não deverá depender diretamente de uma biblioteca não
oficial de WhatsApp. A integração será feita por webhook com o n8n, que
utilizará a instalação EvoGo/Evolution API já existente.

Fluxo:

`VPS Guardian → Webhook n8n → EvoGo/Evolution API → WhatsApp`

### 6.2 Configurações no painel

-   URL do webhook do n8n.
-   Segredo de autenticação do webhook.
-   Número ou grupo destinatário, conforme suporte da instalação.
-   Habilitar/desabilitar notificações.
-   Testar integração.
-   Definir quais severidades serão enviadas.
-   Definir janela de silêncio (opcional).
-   Configurar mensagens de teste.

Credenciais e segredos deverão ser armazenados fora do código-fonte e
nunca exibidos integralmente após salvos.

### 6.3 Modelo de mensagem

Exemplo de alerta:

``` text
🚨 VPS GUARDIAN | CRÍTICO

Servidor: VPS-03
Evento: CPU elevada

CPU atual: 94%
Limite: 85%
Duração: 3 minutos

Horário: 12:35
Incidente: INC-000123

Acesse o painel para consultar os detalhes.
```

Exemplo de recuperação:

``` text
🟢 VPS GUARDIAN | RECUPERADO

Servidor: VPS-03
Evento: CPU elevada

CPU atual: 42%
Condição normalizada.

Duração do incidente: 8 minutos
Incidente: INC-000123
```

O conteúdo deve ser configurável por template, sem permitir que campos
dinâmicos insiram conteúdo executável.

### 6.4 Resiliência de envio

-   Guardar cada notificação em uma fila persistida no MySQL.
-   Registrar estado: pendente, enviada, falha ou cancelada.
-   Implementar tentativas com backoff e limite máximo.
-   Não bloquear a coleta de métricas quando n8n ou WhatsApp estiver
    indisponível.
-   Disponibilizar botão de reenvio manual para administradores.
-   Registrar resposta técnica sem armazenar segredos.

------------------------------------------------------------------------

## 7. Dashboard e interface

### 7.1 Direção visual

Interface web responsiva, profissional e minimalista, inspirada em
plataformas modernas de observabilidade. Priorizar leitura rápida,
hierarquia visual e acessibilidade.

### 7.2 Dashboard principal

Indicadores:

-   Total de servidores.
-   Online, atenção e offline.
-   CPU média.
-   RAM média.
-   Armazenamento médio ou maior utilização.
-   Incidentes abertos por severidade.
-   Última comunicação.
-   Estado da integração WhatsApp.

Lista de servidores:

-   Nome.
-   Estado.
-   CPU.
-   RAM.
-   Disco.
-   Quantidade de containers ativos/parados.
-   Última comunicação.
-   Alertas ativos.

### 7.3 Detalhe do servidor

-   Informações gerais e tags.
-   Gráficos históricos de CPU, RAM, swap, disco e rede.
-   Estado e inventário de containers.
-   Verificações de portas e endpoints associados.
-   Linha do tempo de incidentes.
-   Histórico de heartbeat.
-   Versão do agente.
-   Ações administrativas de cadastro, pausa e rotação de token (sem
    execução remota de comandos na primeira versão).

### 7.4 Outras telas

1.  Dashboard.
2.  Servidores.
3.  Detalhes do servidor.
4.  Containers.
5.  Verificações de disponibilidade.
6.  Incidentes.
7.  Histórico de notificações.
8.  Regras e limites.
9.  Integrações.
10. Usuários e configurações.

------------------------------------------------------------------------

## 8. Arquitetura técnica

### 8.1 Stack proposta

  ---------------------------------------------------------------------
  Camada                             Tecnologia
  ---------------------------------- ----------------------------------
  Frontend                           React + TypeScript

  Backend/API                        Python + FastAPI

  Agente Linux                       Python

  Banco de dados                     MySQL (serviço no Easypanel)

  ORM/migrations                     SQLAlchemy + Alembic ou
                                     alternativa compatível com MySQL

  Comunicação                        HTTPS/JSON

  Integração de alertas              Webhook n8n

  WhatsApp                           EvoGo / Evolution API via n8n

  Empacotamento                      Docker

  Proxy/TLS                          Traefik/Easypanel ou proxy já
                                     utilizado no ambiente

  Serviço do agente                  systemd
  ---------------------------------------------------------------------

A escolha final de bibliotecas deverá priorizar manutenção ativa,
compatibilidade com Python e suporte estável ao MySQL.

### 8.2 Serviços da central

-   `guardian-frontend`: interface web.
-   `guardian-api`: API e regras de negócio.
-   `guardian-worker`: avaliação de regras, verificações agendadas e
    fila de notificações.
-   `mysql`: serviço MySQL gerenciado pelo Easypanel ou conectado por
    rede privada.
-   `guardian-migrations`: execução controlada de migrations durante
    implantação.

O MySQL pode ser um serviço já existente no Easypanel. Não é obrigatório
subir uma segunda instância, desde que haja banco e usuário exclusivos
para o VPS Guardian, backup e conectividade privada segura.

### 8.3 Banco de dados MySQL

Criar banco exclusivo, por exemplo `vps_guardian`, e usuário com
privilégios mínimos sobre esse banco.

Entidades/tabelas iniciais:

-   `users`
-   `servers`
-   `agent_credentials`
-   `agent_heartbeats`
-   `host_metrics`
-   `disk_metrics`
-   `network_metrics`
-   `docker_daemons`
-   `containers`
-   `container_states`
-   `checks`
-   `check_results`
-   `alert_rules`
-   `incidents`
-   `incident_events`
-   `notification_channels`
-   `notification_queue`
-   `notification_attempts`
-   `audit_logs`
-   `system_settings`

Requisitos do banco:

-   Usar InnoDB e `utf8mb4`.
-   Chaves primárias consistentes.
-   Índices por servidor e timestamp para consultas históricas.
-   Datas armazenadas em UTC.
-   Migrations versionadas.
-   Usuário de aplicação sem privilégios administrativos.
-   Backup automático e teste periódico de restauração.
-   Política de retenção configurável para métricas detalhadas e
    eventos.

### 8.4 Retenção inicial sugerida

-   Métricas em intervalo de 30 segundos: 7 dias em alta resolução.
-   Métricas agregadas por 5 minutos: 30 dias.
-   Métricas agregadas por 1 hora: 180 dias.
-   Incidentes e auditoria: 12 meses ou mais, conforme capacidade.
-   Resultados de verificações: 90 dias.

A agregação e limpeza deverão ocorrer por tarefas agendadas. Os prazos
devem ser configuráveis. Antes de produção, validar volume e índices com
carga simulada.

------------------------------------------------------------------------

## 9. Agente Linux

### 9.1 Requisitos

-   Compatível com Ubuntu 22.04 e 24.04.
-   Baixo consumo de CPU e memória.
-   Execução como serviço `systemd`.
-   Reinício automático em falha.
-   Comunicação de saída HTTPS.
-   Configuração local protegida, com permissões restritas.
-   Atualização versionada e verificável.
-   Logs locais com rotação.
-   Identidade exclusiva por servidor.
-   Não executar comandos recebidos da central na primeira versão.

### 9.2 Coleta

Intervalo padrão: 30 segundos, configurável.

O agente deverá coletar métricas do sistema por interfaces locais e APIs
documentadas. Para Docker, usar API somente de leitura ou mecanismos
equivalentes. Não executar comandos construídos a partir de dados
recebidos remotamente.

### 9.3 Instalação e provisionamento

O painel deverá gerar instruções de instalação específicas para cada
servidor.

O processo deverá:

1.  Baixar pacote/script de instalação por HTTPS.
2.  Validar integridade e versão.
3.  Receber token de provisionamento temporário.
4.  Registrar o agente na central.
5.  Trocar o token temporário por credencial individual.
6.  Criar configuração local com permissões restritas.
7.  Instalar e iniciar serviço `systemd`.
8.  Enviar primeiro heartbeat.
9.  Exibir servidor como online no painel.

Evitar recomendar execução cega de script remoto. A documentação deverá
permitir inspecionar o instalador antes da execução e validar
checksum/assinatura quando implementado.

### 9.4 Segurança do agente

-   Token individual e revogável por VPS.
-   Rotação de credenciais.
-   TLS obrigatório.
-   Validação de timestamp e proteção contra replay.
-   Limite de tamanho de payload.
-   Allowlist de endpoints da central quando aplicável.
-   Permissões mínimas no sistema.
-   Sem acesso de escrita ao Docker na primeira versão.
-   Sem coleta de variáveis de ambiente, arquivos `.env`, chaves
    privadas, senhas ou conteúdo de volumes.
-   Sem envio de logs completos por padrão.

------------------------------------------------------------------------

## 10. API inicial

Rotas ilustrativas, sujeitas à convenção final do backend:

### Agentes

-   `POST /api/v1/agent/register`
-   `POST /api/v1/agent/heartbeat`
-   `POST /api/v1/agent/metrics`
-   `POST /api/v1/agent/docker`
-   `GET /api/v1/agent/config`

As rotas do agente deverão exigir autenticação própria, diferente da
sessão do painel.

### Painel

-   `GET /api/v1/servers`
-   `POST /api/v1/servers`
-   `GET /api/v1/servers/{id}`
-   `PATCH /api/v1/servers/{id}`
-   `POST /api/v1/servers/{id}/rotate-token`
-   `GET /api/v1/servers/{id}/metrics`
-   `GET /api/v1/incidents`
-   `POST /api/v1/incidents/{id}/acknowledge`
-   `GET /api/v1/notifications`
-   `POST /api/v1/integrations/n8n/test`
-   `GET /api/v1/alert-rules`
-   `POST /api/v1/alert-rules`

Documentar API com OpenAPI/Swagger gerado pelo FastAPI, protegendo
documentação administrativa em produção quando necessário.

------------------------------------------------------------------------

## 11. Segurança e auditoria

-   HTTPS obrigatório em produção.
-   Autenticação forte no painel.
-   Senhas armazenadas com hash moderno e salt.
-   Proteção contra brute force e rate limiting.
-   Tokens individuais para agentes.
-   Segredos fora do repositório e das imagens Docker.
-   CORS restrito aos domínios do painel.
-   Validação rigorosa de payloads.
-   Proteção contra CSRF quando aplicável à estratégia de sessão.
-   Logs de auditoria para alterações de regras, credenciais e
    configurações.
-   Backups criptografados e acesso restrito.
-   Atualizações de dependências e imagens controladas.
-   Não expor MySQL publicamente; preferir rede privada.
-   Firewall permitindo somente portas necessárias.
-   Não disponibilizar endpoint de execução de shell ou comandos remotos
    na versão inicial.

------------------------------------------------------------------------

## 12. Requisitos não funcionais e critérios de aceite

### 12.1 Desempenho e confiabilidade

-   Suportar inicialmente nove servidores e permitir expansão sem
    mudança estrutural.
-   Receber heartbeat de todos os agentes em intervalo de 30 segundos.
-   O processamento de notificações não pode bloquear a ingestão de
    métricas.
-   A central deve continuar registrando incidentes mesmo se o n8n
    estiver indisponível.
-   O painel deve indicar a idade dos dados e não apresentar métricas
    antigas como atuais.
-   Falhas de um agente não devem afetar os demais.
-   Workers devem evitar processamento duplicado de um mesmo evento.

### 12.2 Critérios de aceite da primeira versão

1.  Cadastrar nove servidores no painel.
2.  Instalar agente em Ubuntu 22.04/24.04.
3.  Receber heartbeat e identificar perda de comunicação.
4.  Exibir CPU, RAM, swap, disco, rede e uptime.
5.  Detectar Docker e listar containers nos hosts compatíveis.
6.  Criar verificações HTTP/HTTPS e TCP.
7.  Configurar regras e limites pelo painel.
8.  Abrir incidente após os critérios de persistência.
9.  Enviar alerta via webhook n8n e EvoGo.
10. Enviar recuperação quando a condição normalizar.
11. Deduplicar alertas e registrar tentativas de envio.
12. Consultar gráficos e histórico.
13. Persistir tudo no MySQL.
14. Revogar e rotacionar credenciais de agentes.
15. Executar backup e comprovar restauração do banco.

------------------------------------------------------------------------

## 13. Plano de desenvolvimento

### Fase 1 --- Fundação

-   Repositório e estrutura do projeto.
-   Docker Compose da central.
-   Configuração de conexão MySQL no Easypanel.
-   Migrations e modelos iniciais.
-   Login administrativo.
-   Cadastro de servidores e credenciais de agente.

**Entrega:** painel acessível e cadastro funcional, ainda sem telemetria
completa.

### Fase 2 --- Agente e telemetria

-   Agente Python para Ubuntu.
-   Serviço systemd.
-   Provisionamento seguro.
-   Heartbeat.
-   CPU, RAM, swap, disco, rede e uptime.
-   Detecção básica de Docker.

**Entrega:** nove VPS reportando dados à central.

### Fase 3 --- Dashboard

-   Indicadores gerais.
-   Lista de servidores.
-   Detalhe por VPS.
-   Gráficos históricos.
-   Estado de comunicação e idade dos dados.

**Entrega:** visão centralizada da infraestrutura.

### Fase 4 --- Serviços e disponibilidade

-   Inventário de containers.
-   Monitoramento de estado dos containers.
-   Verificações HTTP/HTTPS.
-   Verificações TCP.
-   Histórico de resultados.

**Entrega:** monitoramento intermediário conforme escopo.

### Fase 5 --- Alertas e WhatsApp

-   Motor de regras.
-   Incidentes e recuperação.
-   Deduplicação e silenciamento.
-   Fila persistida.
-   Webhook n8n.
-   Envio via EvoGo.
-   Teste de integração e histórico de notificações.

**Entrega:** alertas personalizados no WhatsApp.

### Fase 6 --- Hardening e produção

-   Rate limiting.
-   Auditoria.
-   Rotação de tokens.
-   Backup e restauração.
-   Testes de carga e falhas.
-   Documentação de instalação e operação.
-   Teste de recuperação da central.

**Entrega:** primeira versão pronta para uso contínuo.

------------------------------------------------------------------------

## 14. Segunda etapa: Hermes Agent como assistente operacional

### 14.1 Diretriz

A possibilidade de enviar comandos autorizados pelo WhatsApp será
tratada como uma segunda etapa. A proposta é utilizar o **Hermes Agent**
como interface conversacional e agente de operação, sem transformar o
VPS Guardian em um executor irrestrito de comandos.

O VPS Guardian continuará sendo a fonte estruturada de verdade para
métricas, incidentes e estado dos servidores. O Hermes consultará essas
informações por uma API controlada e, quando habilitado, poderá
solicitar ações operacionais aprovadas.

### 14.2 Arquitetura futura proposta

`WhatsApp → EvoGo/Evolution API → n8n → Hermes Agent → API de ferramentas controladas → VPS Guardian / agentes`

O Hermes não deverá receber acesso irrestrito ao shell, ao Docker socket
ou às credenciais administrativas de todas as VPS.

### 14.3 Consultas permitidas inicialmente

-   Consultar estado de uma VPS.
-   Consultar CPU, RAM e disco.
-   Listar containers e seus estados.
-   Consultar incidentes abertos.
-   Consultar disponibilidade de domínio ou porta.
-   Consultar histórico recente de alertas.

### 14.4 Ações operacionais futuras

Ações como reiniciar container ou serviço somente poderão ser
habilitadas após implantação de uma camada de autorização e aprovação.

Requisitos obrigatórios:

-   Lista explícita de ações permitidas (allowlist).
-   Identificação e autorização do solicitante.
-   Vínculo do usuário/número de WhatsApp a permissões específicas.
-   Confirmação adicional para ações que alterem o estado do servidor.
-   Confirmação com resumo do alvo e da ação exata.
-   Prazo curto para confirmação e proteção contra repetição.
-   Registro de auditoria com solicitante, ação, alvo, horário,
    resultado e identificador da aprovação.
-   Limites de frequência e proteção contra comandos duplicados.
-   Bloqueio de comandos arbitrários, shell livre e parâmetros não
    validados.
-   Credenciais separadas por servidor e com privilégio mínimo.
-   Possibilidade de desabilitar imediatamente todas as ações remotas.
-   Hermes deve operar somente por ferramentas/API explicitamente
    disponibilizadas, nunca por acesso geral ao host.

### 14.5 Separação de responsabilidades

-   **VPS Guardian:** coleta, histórico, incidentes, políticas,
    autenticação e auditoria.
-   **n8n:** roteamento de mensagens e integração com WhatsApp.
-   **Hermes Agent:** interpretação de pedidos e seleção de ferramentas
    autorizadas.
-   **Camada de ferramentas:** validação de identidade, permissões,
    parâmetros e aprovações antes de qualquer ação.

A primeira versão do VPS Guardian não deverá expor endpoints de execução
de comandos. A API futura de ações deverá ser projetada e revisada
separadamente.

------------------------------------------------------------------------

## 15. Riscos e decisões em aberto

### Riscos

-   A central está hospedada em uma das nove VPS monitoradas; se ela
    falhar, o painel e a avaliação central podem parar.
-   A ausência de heartbeat pode indicar falha de rede, agente ou
    central, não necessariamente host desligado.
-   O volume de métricas pode crescer rapidamente; retenção, agregação e
    índices precisam ser testados.
-   O acesso de leitura ao Docker exige cuidado com permissões e
    exposição do socket.
-   O envio via n8n/EvoGo depende da disponibilidade dessas integrações.
-   O painel ICP pode ter particularidades; o monitoramento deverá se
    basear no Linux e Docker disponíveis, sem presumir APIs específicas.

### Decisões pendentes para implementação

-   Escolher qual VPS hospedará a central.
-   Confirmar versão exata do Ubuntu em cada VPS.
-   Definir domínio e TLS da central.
-   Definir qual serviço MySQL do Easypanel será utilizado, sua versão e
    rede de acesso.
-   Definir URL e autenticação do webhook n8n.
-   Confirmar detalhes de envio e destinatários disponíveis na
    instalação EvoGo.
-   Definir limites iniciais por servidor.
-   Definir política final de retenção conforme espaço e capacidade do
    MySQL.

------------------------------------------------------------------------

## 16. Definição de pronto

A versão 1.0 será considerada concluída quando as nove VPS estiverem
cadastradas, os agentes estiverem reportando telemetria, o painel
apresentar dados atuais, Docker e verificações de disponibilidade
estiverem operacionais, regras de alerta gerarem incidentes sem
duplicidade e as notificações de alerta/recuperação chegarem ao WhatsApp
pelo fluxo n8n + EvoGo.

O sistema deverá continuar coletando e registrando eventos mesmo quando
o WhatsApp estiver temporariamente indisponível, entregando notificações
pendentes após a recuperação da integração.

------------------------------------------------------------------------

## 17. Governança de implementação e regras para agentes de desenvolvimento

Esta seção complementa os requisitos funcionais. A ordem operacional
detalhada está no `ROADMAP.md`, que deve ser mantido sincronizado com
este PRD.

### 17.1 Documentos de referência

-   `PRD.md`: fonte de verdade para objetivos, escopo, arquitetura,
    requisitos, segurança e critérios de aceite.
-   `ROADMAP.md`: fonte de verdade para sequência de execução, tarefas,
    dependências, validações e status.
-   `README.md`: instruções para desenvolvedores, instalação local,
    variáveis de ambiente e comandos operacionais.
-   `CHANGELOG.md`: registro das mudanças relevantes por versão.

Em caso de conflito, não escolher silenciosamente. Registrar a
divergência e solicitar decisão antes de implementar algo que altere
arquitetura, segurança, banco de dados ou escopo.

### 17.2 Regras obrigatórias de execução

1.  Implementar uma fase por vez, seguindo o `ROADMAP.md`.
2.  Não iniciar uma fase enquanto os critérios de aceite da fase
    anterior não estiverem aprovados.
3.  Antes de alterar código, inspecionar a estrutura existente e
    preservar decisões já validadas.
4.  Não substituir MySQL por PostgreSQL (não utilizado neste projeto),
    SQLite ou outro banco sem autorização explícita.
5.  Não introduzir serviços pagos ou dependências comerciais sem
    aprovação.
6.  Não instalar agentes em todos os nove servidores antes de validar o
    piloto em dois ambientes distintos.
7.  Não armazenar segredos no repositório, no frontend, em logs ou em
    arquivos versionados.
8.  Não expor MySQL à internet; usar rede privada ou túnel seguro entre
    central e banco.
9.  Não conceder ao agente acesso de escrita ao Docker na versão 1.
10. Não criar execução remota de shell, SSH remoto ou endpoint genérico
    de comandos.
11. Toda funcionalidade deve possuir testes automatizados compatíveis
    com seu risco e critérios de aceite.
12. Atualizar `ROADMAP.md` ao concluir cada tarefa, registrando
    evidências e pendências reais.
13. Não marcar uma tarefa como concluída apenas porque o código foi
    escrito: executar e registrar os testes.
14. Se uma dependência externa estiver indisponível, implementar
    tratamento de falha e documentar a limitação, sem simular sucesso.
15. Não modificar configurações de produção ou reiniciar serviços
    existentes sem autorização explícita.

### 17.3 Estratégia de ambientes

Manter, sempre que possível:

-   Ambiente local de desenvolvimento.
-   Ambiente de homologação/teste.
-   Ambiente de produção na VPS escolhida.

A primeira implantação na VPS central deverá ser feita somente após
validar localmente a configuração Docker, migrations, autenticação,
backups e variáveis de ambiente.

### 17.4 Definição de concluído por tarefa

Uma tarefa somente poderá ser marcada como concluída quando:

-   A implementação estiver no repositório.
-   O teste correspondente tiver sido executado.
-   O resultado do teste estiver documentado.
-   Não houver segredo ou dado sensível exposto.
-   A documentação afetada estiver atualizada.
-   As condições de aceite da tarefa estiverem atendidas.

### 17.5 Decisões técnicas que exigem confirmação antes da produção

-   Qual das nove VPS será a central.
-   Domínio definitivo e estratégia TLS.
-   Versão do MySQL disponibilizada no Easypanel.
-   Rede privada ou rota segura até o MySQL.
-   Versões exatas de Ubuntu nos nove hosts.
-   URL, autenticação e formato do webhook n8n.
-   Versão e particularidades da instalação EvoGo/Evolution API.
-   Limites finais de métricas e retenção.
-   Capacidade de CPU, RAM e disco da VPS central.

### 17.6 Observabilidade da própria central

A central também deverá ter monitoramento mínimo de saúde:

-   Health check da API.
-   Health check do worker.
-   Conectividade com MySQL.
-   Estado da fila de notificações.
-   Espaço em disco.
-   Uso de memória.
-   Último processamento bem-sucedido de métricas e regras.

Como a central estará hospedada inicialmente em uma das VPS monitoradas,
documentar que uma falha da própria central pode interromper a detecção
e o envio de alertas. A arquitetura deverá permitir futuramente uma
verificação externa independente ou uma segunda central.

------------------------------------------------------------------------

## 18. Atualização do escopo da versão 1.0

A versão 1.0 deve ser considerada concluída apenas após cumprir os
critérios de aceite da seção 12 e a definição de pronto da seção 16,
seguindo a sequência do `ROADMAP.md`.

A integração com Hermes Agent permanece explicitamente fora da versão
1.0. A versão inicial deverá apenas manter separação de
responsabilidades e uma API de consulta segura que possa, futuramente,
ser consumida por uma camada de ferramentas autorizadas. Nenhuma ação
remota será habilitada por antecipação.
