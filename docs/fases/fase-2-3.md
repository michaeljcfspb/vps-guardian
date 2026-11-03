# Relatório de fase — Fundação (Fase 2) e Cadastro/Provisionamento (Fase 3)

**Data:** 03/11/2026
**Fases:** ROADMAP §6 (Fase 2 — MySQL e fundação do backend) e §7 (Fase 3 — Cadastro de servidores e provisionamento)
**Status:** Implementação concluída; **aceite final pendente de execução na VPS** (sem MySQL acessível)
**Decisão de processo:** [ADR-0001](../decisoes.md#adr-0001--desenvolvimento-code-first-validação-funcional-na-vps) — desenvolvimento code-first, validação funcional na VPS

---

## 1. O que foi implementado

### 1.1 Fundação técnica

- Configuração central por variáveis de ambiente (`GUARDIAN_*`), com *fail-fast*:
  ausência de `GUARDIAN_SECRET_KEY` ou `GUARDIAN_DATABASE_URL` impede a inicialização.
- **MySQL obrigatório por validação de esquema**: URLs `sqlite://`, `postgresql://`
  e derivadas são rejeitadas na carga da configuração (PRD §17.2.4).
- SQLAlchemy 2.x tipado + PyMySQL, pool com `pool_pre_ping`, `pool_recycle` e
  `connect_timeout`; sessão transacional por requisição.
- Alembic configurado para MySQL, lendo a URL do ambiente (nunca do `alembic.ini`).
- Logging estruturado JSON com `request_id`, redação recursiva de campos sensíveis
  (`password`, `token`, `secret`, `authorization`, `cookie`, `csrf`, `database_url`).
- Erros HTTP padronizados (`{"error": {"code", "message", "details"}}`) sem stack trace
  nem SQL na resposta; validação retorna apenas metadados dos campos inválidos.
- Health checks: `/health` (liveness, sem dependências) e `/health/ready`
  (conectividade MySQL + revisão aplicada do Alembic, 503 quando indisponível).
- Middleware de `X-Request-Id` e limite de payload de 1 MiB (413).

### 1.2 Autenticação e autorização

- Senhas com **Argon2id** (`argon2-cffi`), verificação com equalização de tempo para
  e-mails inexistentes (evita oráculo de existência de conta).
- Sessão opaca de 256 bits: apenas `sha256(token)` em `user_sessions`, com expiração
  absoluta **e** ociosa, revogação e `revoked_reason` (ADR-0003).
- Cookie `guardian_session` `HttpOnly`/`SameSite=Strict`/`Secure` em produção;
  cookie `guardian_csrf` legível para *double-submit* + header `X-CSRF-Token`.
- CSRF obrigatório em todos os métodos não seguros das rotas do painel.
- RBAC mínimo com `admin` e `operator` já modelados: operador lê, administrador escreve.
- Rate limiting de login (5 tentativas / 5 min) por IP **e** por e-mail, com auditoria
  de bloqueio e header `Retry-After` (ADR-0006).
- Rate limiting de registro de agente (10/min por IP) e de heartbeat (20/min por
  credencial).

### 1.3 Servidores e provisionamento

- CRUD de servidores com filtros (estado, painel, ambiente, busca) e paginação.
- Estados do PRD §4.5 implementados: `unprovisioned`, `online`, `attention`, `offline`,
  `paused`, `disabled`.
- Token de provisionamento: 256 bits, **uso único**, TTL 15 min, vinculado ao servidor;
  emitir um novo invalida o anterior não utilizado.
- Troca do token temporário por credencial permanente em `POST /agent/register`,
  com `SELECT ... FOR UPDATE` (sem corrida entre dois registros simultâneos).
- **Rotação atômica**: revoga credenciais ativas e emite a nova no mesmo commit.
- **Revogação** de todas as credenciais ativas de um servidor.
- Credenciais armazenadas apenas como SHA-256 + prefixo de 12 caracteres; o valor em
  claro aparece **uma única vez** na resposta que o emite (ADR-0004).
- Heartbeat autenticado atualiza `last_heartbeat_at`, versão do agente e estado
  (→ `online`), com rejeição de desvio de relógio absurdo (> 24 h).
- Rotas do agente usam `Authorization: Bearer`; cookie de sessão jamais é aceito nelas.
- Auditoria de: login (sucesso/falha/bloqueio), logout, criação/edição/pausa/
  desativação de servidor, emissão de token, registro de agente, rotação e revogação.

---

## 2. Arquivos criados

### Backend

| Arquivo | Finalidade |
|---|---|
| `backend/pyproject.toml` | Dependências fixadas, marcadores de teste, configuração do ruff |
| `Dockerfile` (raiz) | Imagem única (API/migrations) com usuário sem privilégios |
| `backend/alembic.ini`, `alembic/env.py`, `alembic/script.py.mako` | Migrations lendo URL do ambiente |
| `backend/alembic/versions/0001_initial.py` | 7 tabelas, 14 índices, 5 FKs, JSON nativo |
| `app/core/config.py` | Configuração tipada com validações de segurança |
| `app/core/security.py` | Argon2id, tokens opacos, hash/prefixo, relógio UTC |
| `app/core/logging.py` | structlog JSON + redação de segredos |
| `app/core/rate_limit.py` | Janela deslizante em memória com registro nomeado |
| `app/core/enums.py` | Estados, severidades, ações auditáveis |
| `app/core/errors.py` | Hierarquia de erros e handlers |
| `app/db/base.py`, `app/db/session.py` | Metadata com convenção de nomes, engine/sessão |
| `app/models/*` | `users`, `user_sessions`, `servers`, `agent_credentials`, `provisioning_tokens`, `audit_logs`, `system_settings` |
| `app/schemas/*` | Validação estrita (extra=forbid), timestamps UTC com sufixo `Z` |
| `app/services/auth.py` | Autenticação, sessão, CSRF, revogação |
| `app/services/servers.py` | Regras de servidor e heartbeat |
| `app/services/provisioning.py` | Tokens, registro, rotação, revogação |
| `app/services/audit.py` | Trilha de auditoria |
| `app/services/schema.py` | Revisão aplicada do Alembic |
| `app/api/deps.py` | Sessão, CSRF, agente, RBAC, rate limit, IP real |
| `app/api/v1/{auth,servers,agent,system,health}.py` | Rotas versionadas |
| `app/main.py` | Factory da aplicação, middlewares, handlers |
| `app/cli.py` | `check` e `create-admin` (senha nunca por argumento) |

### Testes

| Arquivo | Cobertura |
|---|---|
| `tests/conftest.py` | Ambiente isolado; *skip* explícito sem MySQL |
| `tests/unit/test_security.py` | Hash Argon2id, tokens, prefixo, UTC naive |
| `tests/unit/test_config.py` | Rejeição de SQLite/PostgreSQL, CORS, cookie seguro, `repr` sem segredo |
| `tests/unit/test_rate_limit.py` | Janela, bloqueio, isolamento por chave, prune |
| `tests/unit/test_logging.py` | Redação de chaves sensíveis aninhadas |
| `tests/unit/test_schemas.py` | IP, hostname, tags, invariante de timeout, timestamp com TZ |
| `tests/integration/test_auth.py` | Login, cookies, CSRF, rate limit, logout, auditoria |
| `tests/integration/test_servers.py` | CRUD, conflito, 401/403, filtros, paginação, auditoria |
| `tests/integration/test_provisioning.py` | Uso único, expiração, vínculo ao servidor, rotação, revogação |

### Deploy e documentação

| Arquivo | Finalidade |
|---|---|
| `docker-compose.yml` (raiz) | Stack completo: MySQL 8 + API, com migrations automáticas |
| `docker-compose.external-db.yml` (raiz) | API usando o MySQL existente do Easypanel |
| `backend/docker-entrypoint.sh` | Espera o MySQL e aplica `alembic upgrade head` no boot |
| `.env.example` (raiz) | Modelo único de variáveis, com obrigatórias marcadas |
| `deploy/mysql/bootstrap.sql` | Banco e usuário com privilégio mínimo (modo externo) |
| `deploy/mysql/seed-test.sql` | **Dados fictícios** de homologação (sem credenciais) |
| `deploy/README.md` | Passo a passo de instalação, verificação e rollback |
| `docs/arquitetura.md`, `docs/decisoes.md`, `docs/fase-0/diagnostico-tecnico.md` | Arquitetura, ADRs e diagnóstico |
| `README.md`, `CHANGELOG.md`, `.gitignore` | Documentação e higiene do repositório |

## 3. Arquivos modificados

- `ROADMAP-vps-guardian.md` — checkboxes das Fases 2 e 3 e bloco "Estado atual".
- Nenhum arquivo pré-existente de código foi alterado (o repositório não tinha código).

---

## 4. Testes realizados

Ambiente: venv **descartável e temporário** (`%TEMP%`), sem banco e sem serviços.
Nenhum MySQL, Docker ou servidor foi iniciado; nenhum acesso à VPS.

| Verificação | Comando | Resultado |
|---|---|---|
| Suíte de unidade | `pytest -m unit -q` | **49 passed**, 0 failed |
| Lint estático | `ruff check app tests alembic` | **All checks passed** |
| Compilação | `python -m compileall app alembic tests` | exit 0 |
| Geração do OpenAPI | `create_app(...).openapi()` | **19 rotas** carregadas sem erro |
| Migration (DDL offline) | `alembic upgrade head --sql` | 7 tabelas, 14 índices, 5 FKs, JSON nativo — SQL MySQL válido |
| Histórico do Alembic | `alembic history` | `<base> -> 0001_initial (head)` |
| Integração (`-m integration`) | `pytest -m integration -q` | **37 skipped** — `GUARDIAN_TEST_DATABASE_URL` ausente |

### Testes que NÃO foram executados (e por quê)

| Teste | Motivo | Onde será executado |
|---|---|---|
| Migrations em banco vazio | não há MySQL acessível | VPS, `docker compose run --rm migrations` |
| Persistência grava/recupera | idem | VPS, `pytest -m integration` |
| Fluxo completo de login/cookies/CSRF | idem | VPS |
| Provisionamento → heartbeat | idem | VPS |
| `create-admin` + login real | idem | VPS |

> **Nenhum desses itens foi declarado aprovado.** O resultado "skipped" é explícito no
> relatório do pytest e consta como pendência abaixo.

---

## 5. Pendências

1. Executar `deploy/mysql/bootstrap.sql` no MySQL do Easypanel (confirmar versão ≥ 8.0).
2. Executar `alembic upgrade head` e comprovar que aplica em banco vazio.
3. Executar `pytest -m integration` na VPS com `GUARDIAN_TEST_DATABASE_URL`.
4. Comprovar login real, cookies e CSRF com `curl` conforme `deploy/README.md` §5.
5. Decidir sobre remoção definitiva de servidores (hoje existe apenas "desativar",
   que preserva histórico). Exclusão física exigiria política de retenção.
6. Programar job de limpeza de sessões expiradas (hoje há limpeza oportunista no login).

## 6. Bloqueios

| Bloqueio | Impacto | Necessário |
|---|---|---|
| MySQL do Easypanel indisponível | impede aceite das Fases 2 e 3 | host interno, porta, versão e credenciais |
| Domínio/TLS da central | impede exposição pública da API | definição do domínio |
| VPS central não escolhida | impede instalação | decisão da Fase 0 |

Nenhum bloqueio impede o **código** de avançar; todos impedem o **aceite**.

## 7. Próxima fase

Recomendação: **Fase 4 — Agente Linux e telemetria**, com a ressalva de que o aceite
(instalação em Ubuntu 22.04/24.04) depende de host real.

Ordem sugerida:

1. Agente Python (coleta CPU/RAM/swap/disco/rede/uptime) + `systemd` + instalador.
2. Migration `0002_telemetry` (`agent_heartbeats`, `host_metrics`, `disk_metrics`,
   `network_metrics`).
3. Endpoints `/agent/metrics` e `/agent/docker` com validação de tamanho e esquema.
4. Detecção de agente offline (worker ou job de heartbeat expirado).

## 8. Status do ROADMAP

- Fase 2: tarefas de implementação marcadas `[x]`; **critérios de aceite permanecem
  `[-]`** até execução na VPS.
- Fase 3: idem.
- Fase 0/1: `[!]` bloqueadas por dados de infraestrutura.
- Versão 1.0: **não liberada**.
