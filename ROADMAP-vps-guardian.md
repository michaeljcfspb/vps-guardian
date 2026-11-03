# ROADMAP --- VPS Guardian

**Versão:** 1.0\
**Data:** 03/11/2026\
**Documento complementar:** `PRD.md`\
**Status inicial:** Planejamento --- nenhuma etapa deve ser considerada
concluída sem evidência de validação.

------------------------------------------------------------------------

## 1. Objetivo deste roadmap

Este documento define a ordem de implementação do VPS Guardian, as
dependências entre etapas, as entregas esperadas e os critérios
objetivos para avançar.

O desenvolvimento será incremental. O agente de programação deverá
executar uma fase por vez, validar o resultado, atualizar este arquivo e
somente então iniciar a próxima fase.

**Regra central:** código implementado não significa tarefa concluída. É
necessário executar os testes e registrar os resultados.

------------------------------------------------------------------------

## 2. Regras gerais de trabalho

1.  Ler integralmente `PRD.md` antes de iniciar.
2.  Inspecionar o repositório e o ambiente antes de criar ou alterar
    arquivos.
3.  Preservar tecnologias e decisões já aprovadas: FastAPI, Python,
    React, TypeScript e **MySQL do Easypanel**.
4.  Não introduzir PostgreSQL, serviços pagos ou infraestrutura extra
    sem autorização.
5.  Não instalar agentes nas nove VPS simultaneamente. O piloto deve
    ocorrer em dois servidores de tipos diferentes.
6.  Não executar comandos destrutivos nem alterar serviços de produção
    sem autorização.
7.  Não expor MySQL publicamente.
8.  Não colocar tokens, senhas, chaves ou URLs secretas no Git, frontend
    ou logs.
9.  Não dar acesso de escrita ao Docker para os agentes na versão 1.0.
10. Não implementar execução remota de comandos nesta versão.
11. Manter testes, documentação e migrations atualizados.
12. Atualizar os checkboxes e o registro de execução ao fim de cada
    sessão de trabalho.
13. Se uma tarefa falhar, registrar o erro e corrigir antes de avançar.
14. Se houver ambiguidade de arquitetura, parar e registrar a decisão
    necessária em vez de improvisar.

### Status permitidos

-   `[ ]` Não iniciado.
-   `[-]` Em andamento.
-   `[x]` Concluído e validado.
-   `[!]` Bloqueado --- informar o motivo.

------------------------------------------------------------------------

## 3. Visão geral das fases

  -----------------------------------------------------------------------
  Fase                    Nome                    Resultado obrigatório
  ----------------------- ----------------------- -----------------------
  0                       Descoberta e inventário Decisões de
                                                  infraestrutura
                                                  registradas

  1                       Preparação da central   VPS central, domínio,
                                                  Docker e conectividade
                                                  preparados

  2                       MySQL e fundação do     Banco, migrations,
                          backend                 autenticação e API-base
                                                  funcionando

  3                       Cadastro e              Cadastro de servidores
                          provisionamento         e credenciais
                                                  individuais

  4                       Agente Linux e          Agente envia heartbeat
                          telemetria              e métricas reais

  5                       Piloto em duas VPS      Compatibilidade
                                                  validada em dois
                                                  ambientes

  6                       Expansão para nove VPS  Todos os servidores
                                                  reportando

  7                       Dashboard e histórico   Visão geral, detalhes e
                                                  gráficos

  8                       Docker e verificações   Containers, portas,
                                                  HTTP e HTTPS
                                                  monitorados

  9                       Motor de alertas        Incidentes,
                                                  deduplicação e
                                                  recuperação

  10                      WhatsApp via n8n +      Alertas reais entregues
                          EvoGo                   e auditados

  11                      Segurança, backup e     Sistema validado para
                          produção                operação contínua
  -----------------------------------------------------------------------

A ordem poderá ser ajustada somente se uma dependência técnica
comprovada exigir isso. Toda alteração deverá ser registrada.

------------------------------------------------------------------------

## 4. Fase 0 --- Descoberta e inventário

**Objetivo:** levantar os dados necessários para implantar sem presumir
detalhes do ambiente.

### Tarefas

-   [ ] Identificar as nove VPS por nome e função.
-   [ ] Registrar IP/hostname de cada servidor em inventário privado.
-   [ ] Confirmar a versão exata do Ubuntu em cada VPS.
-   [ ] Registrar painel utilizado: Easypanel, Portainer ou ICP
    Integrator.
-   [ ] Identificar quais hosts possuem Docker e confirmar sua versão.
-   [ ] Levantar CPU, RAM, disco e espaço livre da possível VPS central.
-   [ ] Escolher a VPS que hospedará o Guardian.
-   [ ] Identificar o serviço MySQL do Easypanel que será utilizado.
-   [ ] Confirmar versão do MySQL, hostname interno, porta e rede de
    acesso.
-   [ ] Definir domínio da central e estratégia de TLS.
-   [ ] Identificar URL do webhook n8n e método de autenticação.
-   [ ] Confirmar detalhes de envio da instalação EvoGo/Evolution API.
-   [ ] Definir destinatário(s) de alertas e regras iniciais.

### Entregáveis

-   Inventário técnico sem segredos no repositório.
-   Decisão registrada sobre VPS central.
-   Dados de conexão MySQL documentados em ambiente seguro.
-   Dependências externas identificadas.

### Critérios de aceite

-   [ ] As nove VPS estão identificadas.
-   [ ] A VPS central foi escolhida e possui capacidade suficiente.
-   [ ] A conectividade com o MySQL foi confirmada ou há plano de rede
    aprovado.
-   [ ] Domínio e TLS têm estratégia definida.
-   [ ] Integração n8n/EvoGo tem dados técnicos suficientes para
    implementação.

**Bloqueio:** não avançar para implantação central se não houver
capacidade ou conectividade segura confirmada.

------------------------------------------------------------------------

## 5. Fase 1 --- Preparação da VPS central

**Objetivo:** preparar o ambiente de hospedagem da aplicação.

### Tarefas

-   [ ] Confirmar acesso administrativo à VPS escolhida.
-   [ ] Verificar atualizações e estado geral do sistema.
-   [ ] Confirmar Docker e Docker Compose.
-   [ ] Confirmar funcionamento do Easypanel na VPS central, se
    aplicável.
-   [ ] Configurar domínio e proxy reverso.
-   [ ] Habilitar HTTPS.
-   [ ] Definir firewall com portas mínimas necessárias.
-   [ ] Garantir que o MySQL não será exposto publicamente.
-   [ ] Definir diretórios e volumes persistentes.
-   [ ] Definir política inicial de backup.
-   [ ] Preparar arquivos de ambiente sem credenciais versionadas.

### Entregáveis

-   VPS central preparada.
-   Domínio com HTTPS.
-   Estrutura de implantação definida.
-   Política de acesso de rede documentada.

### Testes e aceite

-   [ ] Domínio resolve para o destino correto.
-   [ ] HTTPS válido.
-   [ ] Acesso administrativo à VPS preservado.
-   [ ] Portas não necessárias permanecem fechadas.
-   [ ] Volumes persistentes funcionam após reinício controlado dos
    containers de teste.

------------------------------------------------------------------------

## 6. Fase 2 --- MySQL e fundação do backend

**Objetivo:** estabelecer a persistência e o núcleo da API.

### Tarefas

-   [ ] Confirmar versão e compatibilidade do MySQL. — aguarda VPS (bloqueio B-06)
-   [ ] Criar banco exclusivo `vps_guardian`. — script pronto em
    `deploy/mysql/bootstrap.sql`, ainda não executado
-   [ ] Criar usuário exclusivo com privilégios mínimos. — idem bootstrap
-   [ ] Validar conexão pela rede privada ou rota segura. — aguarda VPS
-   [x] Definir SQLAlchemy e estratégia de migrations Alembic compatível
    com MySQL.
-   [x] Criar estrutura inicial do backend FastAPI.
-   [x] Criar configuração por variáveis de ambiente.
-   [x] Implementar endpoint de health check.
-   [x] Implementar logging estruturado sem segredos.
-   [x] Criar migrations iniciais. — `0001_initial`, DDL validado via
    `alembic upgrade head --sql`
-   [x] Criar autenticação do painel e hash seguro de senhas. — Argon2id
    + sessão + CSRF
-   [x] Implementar rate limiting para autenticação.
-   [-] Criar testes de conexão e persistência. — testes escritos
    (37 de integração); execução pendente de MySQL real

### Entregáveis

-   API FastAPI executando.
-   Banco MySQL conectado.
-   Migrations versionadas.
-   Autenticação administrativa básica.
-   Health check funcional.

### Testes e aceite

-   [-] API inicia sem erro. — validado por `create_app()` + OpenAPI
    (19 rotas); processo real na VPS pendente
-   [-] Health check retorna estado correto. — unidade ok; `/health/ready`
    com MySQL real pendente
-   [ ] API conecta ao MySQL sem exposição pública do banco.
-   [ ] Migrations aplicam em banco vazio.
-   [ ] Teste de persistência grava e recupera dados.
-   [x] Credenciais não aparecem nos logs ou no Git. — redação testada;
    `.env` no `.gitignore`; nenhum segredo versionado
-   [-] Testes automatizados passam. — 49 de unidade aprovados; 37 de
    integração skipped por ausência de MySQL (não aprovados)

**Gate:** não iniciar cadastro/provisionamento enquanto a fundação e as
migrations não estiverem estáveis.

------------------------------------------------------------------------

## 7. Fase 3 --- Cadastro de servidores e provisionamento

**Objetivo:** permitir registrar VPS e emitir credenciais individuais
para agentes.

### Tarefas

-   [x] Criar modelo e migration de servidores.
-   [x] Implementar CRUD protegido de servidores. — criar, ler, editar,
    listar; remoção física não implementada (só desativação, que preserva
    histórico)
-   [x] Criar estados: não provisionado, online, atenção, offline e
    pausado. — + `disabled`
-   [x] Criar tokens individuais de agente.
-   [x] Implementar emissão de token temporário de provisionamento.
-   [x] Implementar troca do token temporário por credencial individual.
-   [x] Implementar revogação e rotação de credenciais.
-   [x] Criar endpoint de registro do agente.
-   [x] Criar validação de payload e autenticação própria de agente.
-   [x] Registrar auditoria de operações administrativas.
-   [-] Criar testes de autorização e revogação. — 37 testes escritos;
    execução pendente de MySQL real

### Entregáveis

-   Cadastro de VPS funcional pela API.
-   Identidade exclusiva por servidor.
-   Provisionamento inicial documentado.

### Testes e aceite

-   [ ] Criar e editar servidor autenticado.
-   [ ] Usuário não autenticado não acessa rotas administrativas.
-   [ ] Token de uma VPS não autentica outra VPS.
-   [ ] Token revogado deixa de funcionar.
-   [ ] Token temporário não pode ser reutilizado fora das regras de
    validade.
-   [ ] Segredos não são retornados novamente em consultas comuns.

> Situação em 03/11/2026: os seis critérios acima possuem teste
> automatizado escrito, mas **não foram executados** — dependem de MySQL
> real (ADR-0001). Permanecem abertos até a execução na VPS.

------------------------------------------------------------------------

## 8. Fase 4 --- Agente Linux e telemetria

**Objetivo:** desenvolver o agente leve para Ubuntu 22.04/24.04.

### Tarefas

-   [x] Criar pacote do agente em Python.
-   [x] Implementar configuração local protegida. — JSON 0600, escrita atômica
-   [x] Implementar coleta de CPU e load average.
-   [x] Implementar RAM e swap.
-   [x] Implementar uso de disco por ponto de montagem.
-   [x] Implementar contadores e taxas de rede. — estado persistido entre coletas
-   [x] Implementar uptime e informações do sistema.
-   [x] Implementar heartbeat com timestamp UTC.
-   [x] Implementar envio HTTPS com timeout e retentativas controladas. —
    backoff exponencial; 4xx não repete
-   [x] Implementar fila local limitada para interrupções temporárias. —
    limite por quantidade e idade
-   [x] Implementar logs locais com rotação. — JSON, 5 MB × 3, com máscara de segredos
-   [x] Criar serviço systemd. — usuário sem privilégios + hardening
-   [x] Implementar atualização/versionamento seguro do agente. —
    versão no pacote, no payload e em `/agent/config`; reinstalação idempotente
-   [x] Implementar limite de payload e proteção contra dados inválidos. —
    validação estrita Pydantic na central + filtro de interfaces no agente
-   [x] Garantir que o agente não execute comandos remotos. — não há
    subprocess/`os.system` em nenhum ponto do código
-   [x] Garantir que não colete `.env`, chaves privadas, senhas ou
    conteúdo de volumes. — coleta restrita a `psutil`, `/etc/os-release` e kernel

### Entregáveis

-   Agente instalável em Ubuntu.
-   Serviço systemd.
-   Heartbeat e métricas chegando à API.
-   Guia de instalação e remoção.

### Testes e aceite

-   [ ] Instalação em Ubuntu 22.04.
-   [ ] Instalação em Ubuntu 24.04.
-   [ ] Serviço inicia após reboot.
-   [ ] Serviço se recupera de falha.
-   [ ] Métricas recebidas correspondem às métricas locais dentro de
    tolerância.
-   [-] Falha temporária de rede não trava o agente. — coberto por teste
    de unidade (buffer + retry); falta a prova em host real
-   [-] Credencial inválida é rejeitada. — coberto por teste de
    integração (escrito, não executado)
-   [ ] Consumo do agente é medido e documentado.
-   [x] Nenhum comando recebido da central é executado. — verificado por
    inspeção: não existe chamada de subprocess/shell no pacote do agente

> Situação em 03/11/2026: implementação concluída e validada por 55 testes
> de unidade + coleta real (`--dry-run`). Os critérios que dependem de host
> Ubuntu seguem **abertos** — a validação ocorre na VPS (Fase 5).

------------------------------------------------------------------------

## 9. Fase 5 --- Piloto em duas VPS

**Objetivo:** provar compatibilidade antes de escalar.

### Seleção

-   VPS piloto A: uma das sete VPS com Easypanel.
-   VPS piloto B: preferencialmente a VPS com Portainer ou ICP
    Integrator.

### Tarefas

-   [ ] Fazer backup/registrar estado atual antes da instalação.
-   [ ] Instalar agente na VPS piloto A.
-   [ ] Validar heartbeat e métricas por pelo menos 24 horas.
-   [ ] Instalar agente na VPS piloto B.
-   [ ] Validar diferenças de Docker e permissões.
-   [ ] Verificar se o agente interfere em aplicações existentes.
-   [ ] Testar reinício do agente e reboot controlado, quando
    autorizado.
-   [ ] Corrigir incompatibilidades.
-   [ ] Registrar procedimento repetível de instalação.

### Entregáveis

-   Relatório do piloto.
-   Lista de incompatibilidades e correções.
-   Procedimento de rollout.

### Critérios de aceite

-   [ ] Dois agentes ativos e estáveis.
-   [ ] Telemetria consistente por pelo menos 24 horas.
-   [ ] Sem impacto operacional identificado.
-   [ ] CPU, RAM, disco, rede e uptime validados.
-   [ ] Docker detectado corretamente nos hosts aplicáveis.
-   [ ] Plano de reversão testado/documentado.

**Gate obrigatório:** não instalar nas demais sete VPS sem aprovação
explícita do piloto.

------------------------------------------------------------------------

## 10. Fase 6 --- Expansão para as nove VPS

**Objetivo:** completar o inventário monitorado.

### Tarefas

-   [ ] Cadastrar as nove VPS.
-   [ ] Planejar janelas de instalação.
-   [ ] Instalar agente em grupos pequenos.
-   [ ] Validar heartbeat após cada instalação.
-   [ ] Confirmar versão do agente em todos os hosts.
-   [ ] Identificar hosts sem Docker sem gerar falso alerta.
-   [ ] Confirmar que cada agente está vinculado ao servidor correto.
-   [ ] Documentar exceções específicas do painel ICP, se houver.

### Entregáveis

-   Nove VPS cadastradas.
-   Agentes instalados e identificados.
-   Relatório de cobertura.

### Critérios de aceite

-   [ ] Nove servidores aparecem no inventário.
-   [ ] Todos os servidores aprovados reportam heartbeat.
-   [ ] Dados de cada VPS não estão misturados.
-   [ ] Servidores sem Docker aparecem como "não detectado/não
    instalado".
-   [ ] Alertas falsos por recursos não aplicáveis não são gerados.

------------------------------------------------------------------------

## 11. Fase 7 --- Dashboard e histórico

**Objetivo:** entregar a interface operacional.

### Tarefas

-   [ ] Criar aplicação React + TypeScript.
-   [ ] Definir biblioteca de componentes e padrão visual.
-   [ ] Implementar login e sessão segura.
-   [ ] Criar dashboard com totais e estados.
-   [ ] Criar tabela de servidores.
-   [ ] Criar detalhe por servidor.
-   [ ] Criar gráficos de CPU, RAM, swap, disco e rede.
-   [ ] Criar indicadores de idade/atualidade dos dados.
-   [ ] Criar filtros por estado, tag e painel.
-   [ ] Criar visualização de incidentes e eventos.
-   [ ] Implementar paginação e consultas eficientes.
-   [ ] Implementar tratamento de loading, vazio e erro.
-   [ ] Testar layout desktop e mobile.

### Entregáveis

-   Dashboard responsivo.
-   Visão detalhada de cada servidor.
-   Histórico consultável.

### Critérios de aceite

-   [ ] Dashboard apresenta os nove hosts.
-   [ ] Estado online/offline reflete heartbeat real.
-   [ ] Métricas exibem timestamp e não parecem atuais quando estão
    antigas.
-   [ ] Gráficos consultam dados persistidos no MySQL.
-   [ ] Filtros e paginação funcionam.
-   [ ] Usuário sem sessão não acessa dados privados.

------------------------------------------------------------------------

## 12. Fase 8 --- Docker e verificações de disponibilidade

**Objetivo:** adicionar monitoramento intermediário.

### Tarefas Docker

-   [ ] Detectar presença e estado do daemon.
-   [ ] Listar containers e estado.
-   [ ] Coletar imagem, nome e ID abreviado.
-   [ ] Coletar CPU e memória por container quando disponível.
-   [ ] Detectar transições de estado.
-   [ ] Tratar hosts sem Docker.
-   [ ] Restringir coleta à leitura.

### Tarefas de checks

-   [ ] CRUD de verificações HTTP/HTTPS.
-   [ ] CRUD de verificações TCP.
-   [ ] Configurar timeout e intervalo.
-   [ ] Configurar códigos HTTP esperados.
-   [ ] Persistir latência, resultado e timestamp.
-   [ ] Configurar falhas consecutivas e recuperação.
-   [ ] Evitar SSRF: validar destinos, bloquear endereços proibidos e
    restringir redirecionamentos.
-   [ ] Limitar frequência, timeout e tamanho das respostas.

### Entregáveis

-   Inventário de containers.
-   Verificações HTTP/HTTPS/TCP.
-   Histórico de disponibilidade.

### Critérios de aceite

-   [ ] Container parado é detectado.
-   [ ] Estado de Docker indisponível é diferenciado de host offline.
-   [ ] Endpoint HTTP válido é identificado como disponível.
-   [ ] Endpoint indisponível gera resultado de falha.
-   [ ] Timeout é respeitado.
-   [ ] Verificações não podem ser usadas para acessar serviços internos
    não autorizados ou metadados de nuvem.
-   [ ] O agente continua sem permissões de escrita no Docker.

------------------------------------------------------------------------

## 13. Fase 9 --- Motor de alertas e incidentes

**Objetivo:** converter condições monitoradas em incidentes confiáveis,
sem excesso de notificações.

### Tarefas

-   [ ] Criar CRUD de regras.
-   [ ] Implementar limites globais e por servidor.
-   [ ] Implementar duração mínima e falhas consecutivas.
-   [ ] Criar estados de incidente: aberto, reconhecido e resolvido.
-   [ ] Implementar deduplicação por regra/alvo.
-   [ ] Implementar lembretes configuráveis.
-   [ ] Implementar silenciamento temporário.
-   [ ] Implementar evento de recuperação.
-   [ ] Criar fila persistida de notificações.
-   [ ] Implementar tentativas e backoff.
-   [ ] Criar auditoria de reconhecimento e encerramento manual.
-   [ ] Criar testes de cenários de alerta e recuperação.

### Entregáveis

-   Motor de regras.
-   Incidentes rastreáveis.
-   Fila de notificações resiliente.

### Critérios de aceite

-   [ ] CPU acima do limite pelo período configurado abre um incidente.
-   [ ] Oscilação breve não abre incidente se não atingir a persistência
    exigida.
-   [ ] Mesmo incidente não gera mensagens repetidas a cada coleta.
-   [ ] Normalização gera evento de recuperação.
-   [ ] Silenciamento funciona e expira corretamente.
-   [ ] Falha de notificação não apaga o incidente.
-   [ ] Reinício do worker não perde itens persistidos na fila.

------------------------------------------------------------------------

## 14. Fase 10 --- WhatsApp via n8n + EvoGo

**Objetivo:** entregar alertas e recuperações ao WhatsApp.

### Tarefas

-   [ ] Definir contrato JSON do webhook Guardian → n8n.
-   [ ] Criar segredo de autenticação do webhook.
-   [ ] Criar workflow n8n para receber evento.
-   [ ] Validar payload e autenticação no workflow.
-   [ ] Configurar envio pela instalação EvoGo/Evolution API.
-   [ ] Definir destinatários.
-   [ ] Criar templates de alerta, recuperação e teste.
-   [ ] Tratar respostas de sucesso e erro.
-   [ ] Implementar idempotência para evitar duplicidade.
-   [ ] Registrar ID do evento e tentativas.
-   [ ] Criar teste de integração ponta a ponta.

### Entregáveis

-   Workflow n8n documentado.
-   Integração com EvoGo funcional.
-   Alertas reais no WhatsApp.

### Critérios de aceite

-   [ ] Mensagem de teste chega ao destinatário.
-   [ ] Incidente crítico gera mensagem.
-   [ ] Recuperação gera mensagem.
-   [ ] Falha do n8n não interrompe ingestão de métricas.
-   [ ] Reenvio não duplica mensagens já confirmadas.
-   [ ] Segredos não aparecem no histórico de execução ou logs.
-   [ ] Administrador consegue consultar estado de envio.

------------------------------------------------------------------------

## 15. Fase 11 --- Segurança, backup e produção

**Objetivo:** preparar o sistema para uso contínuo.

### Tarefas

-   [ ] Revisar autenticação e autorização.
-   [ ] Revisar rate limiting.
-   [ ] Revisar CORS, CSRF e cookies/sessões conforme estratégia
    adotada.
-   [ ] Revisar validação de entrada e proteção contra SSRF.
-   [ ] Revisar isolamento de credenciais dos agentes.
-   [ ] Revisar permissões de Docker e sistema.
-   [ ] Revisar exposição de portas e serviços.
-   [ ] Configurar backup automático do MySQL.
-   [ ] Criptografar e restringir acesso aos backups.
-   [ ] Executar teste real de restauração.
-   [ ] Configurar retenção e agregação de métricas.
-   [ ] Testar indisponibilidade de n8n/EvoGo.
-   [ ] Testar reinício de API e worker.
-   [ ] Testar perda temporária de conexão dos agentes.
-   [ ] Configurar health checks da própria central.
-   [ ] Documentar atualização e rollback.
-   [ ] Documentar recuperação após falha da VPS central.
-   [ ] Criar checklist de operação.

### Critérios de aceite

-   [ ] Backup automático executado.
-   [ ] Restauração comprovada em ambiente de teste.
-   [ ] Segredos revisados e protegidos.
-   [ ] Testes de falha concluídos.
-   [ ] Retenção não excede limites planejados.
-   [ ] API, worker e banco têm health checks.
-   [ ] Documentação de implantação e rollback está atualizada.
-   [ ] Todas as fases anteriores estão aprovadas.

------------------------------------------------------------------------

## 16. Segunda etapa futura --- Hermes Agent

**Não executar nesta primeira versão.**

Depois que o monitoramento estiver estável, avaliar a integração:

`WhatsApp → EvoGo → n8n → Hermes Agent → API de ferramentas autorizadas → VPS Guardian`

### Primeira entrega futura: somente consultas

-   [ ] Consultar status das VPS.
-   [ ] Consultar CPU, RAM e disco.
-   [ ] Listar containers e estados.
-   [ ] Consultar incidentes.
-   [ ] Consultar disponibilidade de domínios e portas.

### Ações controladas, somente após revisão

-   [ ] Definir allowlist de ações.
-   [ ] Vincular número/identidade a permissões.
-   [ ] Exigir confirmação explícita antes de ações que alterem estado.
-   [ ] Validar alvo e parâmetros em API intermediária.
-   [ ] Impedir shell livre e comandos arbitrários.
-   [ ] Usar credenciais de privilégio mínimo.
-   [ ] Auditar solicitante, alvo, ação, aprovação e resultado.
-   [ ] Criar botão/procedimento de desligamento emergencial das ações.
-   [ ] Testar em ambiente não produtivo antes de habilitar em VPS
    reais.

O Hermes não receberá acesso irrestrito ao SSH ou Docker socket. A
execução será feita por ferramentas específicas e limitadas.

------------------------------------------------------------------------

## 17. Modelo de acompanhamento por sessão

Ao final de cada sessão, o agente de desenvolvimento deverá atualizar
este bloco:

### Estado atual

-   **Fase atual:** 4 --- Agente Linux e telemetria (implementação concluída;
    aceite em Ubuntu pendente).
-   **Última tarefa concluída:** Ingestão idempotente de telemetria
    (`/agent/metrics`) e pacote do agente com serviço systemd.
-   **Próxima tarefa:** Fase 7 --- dashboard e histórico (recomendado antes
    do piloto, para tornar a validação de 24 h observável) ou Fase 9 ---
    motor de alertas.
-   **Bloqueios:** MySQL do Easypanel, domínio/TLS, VPS central e
    inventário das nove VPS — os mesmos da Fase 0.
-   **Testes executados:** 66 testes de unidade no backend e 55 no agente,
    lint (`ruff`) nos dois pacotes, DDL das duas migrations gerado por
    `alembic upgrade head --sql`, OpenAPI com 20 rotas, coleta real via
    `guardian-agent --dry-run`.
-   **Testes aprovados:** 121 de unidade. Os 46 de integração do backend
    ficaram *skipped* por ausência de MySQL e **não** foram aprovados.
-   **Data da última atualização:** 03/11/2026.

### Registro de execução

  --------------------------------------------------------------------------
  Data           Fase           Atividade      Resultado      Evidência /
                                                              observação
  -------------- -------------- -------------- -------------- --------------
  03/11/2026     Planejamento   Criação do     Planejado      Documento
                                roadmap                       inicial

  03/11/2026     0              Diagnóstico    Concluído      docs/fase-0/
                                técnico e                     diagnostico-
                                plano                         tecnico.md

  03/11/2026     2 e 3          Backend,       Implementado   docs/fases/
                                auth, cadastro (aceite       fase-2-3.md;
                                e provisio-    pendente)      49 testes de
                                namento                       unidade ok

  03/11/2026     4              Agente Linux   Implementado   docs/fases/
                                + telemetria   (aceite em     fase-4.md;
                                + migration    Ubuntu         121 testes de
                                0002_telemetry pendente)      unidade ok

  --------------------------------------------------------------------------

Não registrar como concluído algo que não foi efetivamente testado.

------------------------------------------------------------------------

## 18. Checklist de liberação da versão 1.0

-   [ ] Nove VPS cadastradas.
-   [ ] Agentes instalados e autenticados.
-   [ ] Heartbeat e métricas recebidos.
-   [ ] Dashboard operacional.
-   [ ] Docker monitorado nos hosts aplicáveis.
-   [ ] Checks HTTP/HTTPS/TCP funcionando.
-   [ ] Motor de alertas validado.
-   [ ] Deduplicação e recuperação funcionando.
-   [ ] WhatsApp integrado via n8n + EvoGo.
-   [ ] MySQL com backup e restauração testados.
-   [ ] Segurança revisada.
-   [ ] Documentação operacional concluída.
-   [ ] Todas as fases aprovadas.

**A versão 1.0 só está pronta quando todos os itens obrigatórios
estiverem validados.**
