# Changelog

Todas as mudanças relevantes deste projeto são registradas aqui.
Formato baseado em [Keep a Changelog](https://keepachangelog.com/pt-BR/1.1.0/) e
versionamento semântico.

## [Não publicado]

### Adicionado

- Estrutura inicial do repositório: `backend/`, `deploy/`, `docs/`.
- Fundação do backend FastAPI: configuração por ambiente, logging estruturado com
  redação de segredos, engine SQLAlchemy 2 + PyMySQL, Alembic e health checks.
- Autenticação do painel: Argon2id, sessão em cookie `HttpOnly` com CSRF
  double-submit, rate limiting e auditoria de tentativas.
- Cadastro de servidores, emissão de token de provisionamento de uso único,
  registro de agente e rotação/revogação de credenciais.
- Instalação em um comando: `docker-compose.yml` sobe **MySQL 8 + API**, com
  healthcheck, espera do banco e `alembic upgrade head` automáticos no boot.
- Variante `docker-compose.external-db.yml` para usar o MySQL já existente do Easypanel.
- `.env.example` único na raiz, com os quatro valores obrigatórios marcados.
- Conexão por partes (`GUARDIAN_DB_*`) com URL-encoding automático da senha, evitando
  falha de instalação quando a senha contém `@`, `#`, `/` ou `:`.
- CLI: comandos `check`, `wait-db` e `create-admin`.
- Arquivos de deploy para Easypanel + MySQL e bootstrap de banco.
- Suíte de testes de unidade e integração (integração exige MySQL real).

### Corrigido

- **500 em todas as rotas /api (painel inutilizável).** `Settings` não declarava
  `session_cookie_name`; a dependência de sessão levantava `AttributeError` em
  produção. Nenhum teste cobria esse caminho porque os testes de integração ficavam
  *skipped* sem MySQL. Adicionado o campo, validação do nome do cookie e um smoke test
  que cria a aplicação real e exige 401 (não 500) nas rotas protegidas.

- **Configuração inválida não imprime mais traceback nem valores de ambiente.** O
  `ValidationError` do Pydantic carrega `input_value` na representação e expunha a
  senha do MySQL nos logs. Agora o boot falha com mensagem limpa, listando apenas o
  **nome** da variável e o problema (ex.: `GUARDIAN_SECRET_KEY: obrigatório`), com
  código de saída 2.
- Entrypoint orienta explicitamente quando o MySQL não responde ou a migration falha.

### Adicionado — Fase 7 (painel)

- Frontend React 19 + TypeScript + Vite + Tailwind 4 + TanStack Query + Recharts.
- Login com sessão por cookie HttpOnly e CSRF double-submit; nenhum token em
  localStorage.
- Dashboard com totais por estado, médias de CPU/RAM/disco, idade dos dados e tabela
  de servidores.
- Detalhe por servidor: KPIs, gráficos (CPU/RAM/swap/disco e rede) com janela
  1h/6h/24h/7d, heartbeats recentes e ações administrativas (pausar, desativar,
  token de provisionamento, rotação e revogação de credencial).
- Novos endpoints de leitura: /dashboard/summary, /telemetry/latest,
  /servers/{id}/metrics, /servers/{id}/heartbeats — agregação em SQL por bucket.
- Imagem nginx multi-stage com SPA fallback e proxy /api na mesma origem
  (sem CORS); serviço rontend nos dois composes.

### Adicionado — Fase 4 (agente e telemetria)

- Migration `0002_telemetry`: `agent_heartbeats`, `host_metrics`, `disk_metrics`,
  `network_metrics`, com índices `(server_id, collected_at)`.
- `POST /api/v1/agent/metrics` com contrato estrito e **ingestão idempotente**
  (`UNIQUE (server_id, collected_at)`).
- Histórico de heartbeat em `agent_heartbeats`; `features.metrics = true` no
  `/agent/config`.
- Agente Linux em Python 3.10+ com coleta de CPU, load, RAM, swap, disco por ponto de
  montagem, rede com taxa calculada, uptime e processos.
- Buffer local limitado (quantidade e idade), retry com backoff e descarte de payload
  inválido; transporte HTTPS com TLS obrigatório.
- Serviço `systemd` endurecido (usuário sem privilégios, `ProtectSystem=strict`,
  sem capabilities) e instalador/desinstalador auditáveis.
- Config local `0600` com escrita atômica; registro único troca o token de
  provisionamento pela credencial permanente.
- 66 testes de unidade no backend e 53 no agente.

### Decisões

- ADR-0001: desenvolvimento code-first; validação funcional na VPS.
- ADR-0002: ROADMAP prevalece sobre o PRD na ordem de execução.
- ADR-0003: sessão opaca em banco com cookie `HttpOnly` e CSRF double-submit.
- ADR-0004: credenciais de agente e de provisionamento armazenadas apenas como hash.
