# VPS Guardian — Diagnóstico Técnico e Plano de Execução

**Versão do relatório:** 1.0
**Data:** 03/11/2026
**Fase ROADMAP:** 0 — Descoberta e inventário (diagnóstico concluído; inventário pendente de dados do usuário)
**Status:** Aguardando autorização para iniciar implementação
**Autor:** Agente de desenvolvimento (responsável técnico)

---

## 1. Sumário executivo

O repositório contém **apenas os dois documentos de requisitos**. Não há código, migrations, testes, Docker Compose, `README.md`, `CHANGELOG.md` nem repositório Git inicializado. Portanto o projeto está em estado **greenfield**, e nada precisa ser preservado ou migrado.

Os documentos são coerentes entre si quanto a arquitetura (FastAPI + React + MySQL + agente Python + n8n/EvoGo), mas divergem em **dois pontos estruturais** que precisam de decisão registrada antes do primeiro commit:

1. **Modelo de fases divergente** — o PRD §13 define 6 fases; o ROADMAP §3 define 12 fases (0–11). Ambos os documentos afirmam que o ROADMAP é a fonte de verdade da sequência (PRD §17.1 e ROADMAP §1/§2). **Recomendação: ROADMAP prevalece**, com tabela de mapeamento formal.
2. **Nomes de arquivo divergentes** — os documentos se chamam `PRD-vps-guardian.md` e `ROADMAP-vps-guardian.md`, mas se referenciam internamente (e no prompt mestre) como `PRD.md` e `ROADMAP.md`. **Recomendação: renomear para os nomes canônicos** e atualizar referências cruzadas.

O ambiente de desenvolvimento atual **não possui Docker, Docker Compose, MySQL nem WSL**. Isso é um bloqueio material para os critérios de aceite da Fase 2 ("migrations aplicam em banco vazio", "teste de persistência grava e recupera dados"), porque o PRD §17.2.4 **proíbe substituir MySQL por SQLite** — inclusive em testes. Unit tests com banco mockado são permitidos, mas não substituem a evidência exigida.

**Conclusão:** as Fases 0 e 1 do ROADMAP estão bloqueadas por dados de infraestrutura que só o usuário possui. A primeira frente que pode ser iniciada com segurança é uma **fatia local da Fase 2 (fundação do backend)**, explicitamente autorizada pelo PRD §17.3 ("validar localmente a configuração Docker, migrations, autenticação, backups e variáveis de ambiente" antes de qualquer implantação na VPS central) — e mesmo essa depende de um MySQL 8.x local ou de um container.

---

## 2. Estado atual do repositório

### 2.1 Inventário verificado

| Item | Estado | Evidência |
|---|---|---|
| `PRD-vps-guardian.md` | Presente, 1037 linhas, lido integralmente | Seções 1–18 |
| `ROADMAP-vps-guardian.md` | Presente, 678 linhas, lido integralmente | Seções 1–18 |
| Código-fonte (backend/frontend/agent) | **Ausente** | `Get-ChildItem -Force` retorna 2 arquivos |
| `README.md` / `CHANGELOG.md` | **Ausentes** (exigidos pelo PRD §17.1) | idem |
| `.gitignore` / repositório Git | **Ausente** | `git rev-parse` → `not a git repository` |
| Docker Compose | **Ausente** | idem |
| Migrations / modelos | **Ausentes** | idem |
| Testes | **Ausentes** | idem |
| `.env` / segredos versionados | Nenhum (bom) | varredura do diretório |

### 2.2 Ambiente de desenvolvimento (host Windows)

| Ferramenta | Situação | Impacto |
|---|---|---|
| Git 2.51.0 | Instalado, identidade global configurada (`suporte01`) | OK |
| Python 3.12.10 / 3.13 | Instalados, com `pip` (26.2.1 / 25.2) | OK para backend e agente |
| Node.js 22.14.0 + pnpm 10.18.1 | Instalados | OK para frontend |
| Acesso HTTPS a PyPI e npm | **Funcional via Python/Node**; `curl.exe` falha por `SEC_E_NO_CREDENTIALS` (schannel do sandbox) | Instalação de dependências OK usando `pip`/`pnpm`, não `curl` |
| Docker / Docker Compose | **Não instalados** | **Bloqueia** validação de Compose, MySQL e backup/restore |
| MySQL local | **Não instalado**, porta 3306 livre | **Bloqueia** critérios de aceite da Fase 2 |
| WSL2 | **Não instalado** | Impede teste real do agente Linux |
| Espaço livre em disco | 43,17 GB | Suficiente para imagens e volumes |

---

## 3. Resumo da arquitetura

### 3.1 Topologia

```
┌─────────────────────────── VPS central (1 das 9) ───────────────────────────┐
│  Traefik/Easypanel  ──TLS──►  guardian-frontend (React/TS, estático)        │
│                              guardian-api (FastAPI, 2 workers)              │
│                              guardian-worker (regras, checks, fila)         │
│                              guardian-migrations (job de deploy)            │
└───────────────────────────────────┬─────────────────────────────────────────┘
                                    │ rede privada (MySQL não exposto)
                          ┌─────────▼──────────┐
                          │ MySQL 8.x (Easypanel)│  banco `vps_guardian`
                          └────────────────────┘

   VPS 1..9 (7 Easypanel, 1 Portainer, 1 ICP)
   guardian-agent (Python 3.10+, systemd)  ──HTTPS de saída──►  guardian-api
        │ coleta local (psutil, /proc, /sys)
        └ Docker: API somente leitura via socket-proxy local

   guardian-worker ──webhook assinado (HMAC)──► n8n ──► EvoGo/Evolution ──► WhatsApp
```

### 3.2 Princípios que governam o design

- **Pull invertido:** nenhuma porta de entrada é aberta nas VPS monitoradas. O agente inicia a conexão (PRD §2.2, §9.1).
- **Dois planos de autenticação separados:** sessão de painel (humano) e credencial de agente (servidor). O agente nunca recebe sessão de administrador.
- **Sem execução remota:** nenhum endpoint de comando/shell/SSH na v1.0 (PRD §1.2, §11; ROADMAP §2.10). O agente **nunca** interpreta instruções vindas da central.
- **Assíncrono por padrão:** ingestão de métricas nunca bloqueia no envio de notificação. Fila persistida em MySQL (PRD §6.4, §12.1).
- **Idempotência e deduplicação:** um incidente aberto não gera nova notificação a cada coleta (PRD §5.3).
- **Segredos fora do código:** toda configuração sensível por variável de ambiente; segredos de integração cifrados em repouso.

### 3.3 Componentes e responsabilidades

| Componente | Responsabilidade | Não faz |
|---|---|---|
| `guardian-api` | Ingestão, CRUD, autenticação, autorização, auditoria, health | Não executa regras periódicas nem envia webhook |
| `guardian-worker` | Avaliação de regras, checks HTTP/TCP agendados, expiração de heartbeat, fila de notificação, retenção/agregação | Não expõe API pública |
| `guardian-frontend` | Dashboard, detalhes, incidentes, configurações | Nunca recebe segredo de integração em claro |
| `guardian-agent` | Coleta local + envio HTTPS com buffer local | Não aceita comandos, não escreve no Docker |
| MySQL | Fonte de verdade transacional | Não é exposto publicamente |
| n8n + EvoGo | Transporte da mensagem | Não decide o que é incidente |

---

## 4. Divergências entre PRD e ROADMAP (com decisão recomendada)

| ID | Divergência | Evidência | Decisão recomendada | Precisa de você? |
|---|---|---|---|---|
| **D-01** | Modelo de fases: PRD §13 tem 6 fases; ROADMAP §3 tem 12 (0–11), com dashboard em posições diferentes | PRD §13 vs ROADMAP §3/§11 | ROADMAP prevalece (ambos os documentos declaram isso). Registrar tabela de mapeamento em `docs/arquitetura.md` | Não (recomendação explícita dos próprios documentos) |
| **D-02** | Nomes: arquivos são `*-vps-guardian.md`, mas se referenciam como `PRD.md`/`ROADMAP.md` | PRD §17.1, ROADMAP cabeçalho | Renomear para `PRD.md` e `ROADMAP.md`; manter conteúdo; atualizar referências | Sim (renomeação) |
| **D-03** | PRD Fase 1 inclui "cadastro de servidores"; ROADMAP separa fundação (F2) de cadastro (F3) | PRD §13 vs ROADMAP §6/§7 | Seguir ROADMAP: cadastro só depois da fundação estável (gate explícito no ROADMAP §6) | Não |
| **D-04** | `mysql` aparece como serviço do Compose (PRD §8.2), mas também pode ser instância existente do Easypanel, e §17.2.8 exige rede privada | PRD §8.2 | Compose com MySQL **apenas em desenvolvimento local**; produção conecta ao MySQL do Easypanel por rede privada. Mapear diferenças em `docker-compose.yml` vs `docker-compose.prod.yml` | Não |
| **D-05** | Intervalo de coleta: PRD §4.5 fixa heartbeat em 30 s; PRD §4.1 fala em "intervalo de heartbeat" por servidor; §8.4 assume retenção de métricas de 30 s | PRD §4.1/§4.5/§8.4 | Um único `collection_interval_seconds` por servidor (padrão 30 s) governa heartbeat **e** métricas, evitando duas cadências concorrentes | Não |
| **D-06** | Estado "Atenção" do host inclui "agente reportando degradação", mas não há campo de degradação definido | PRD §4.5 | v1: "Atenção" derivado apenas de atraso de heartbeat (1 intervalo perdido) e de flags determinísticas do agente (ex.: falha de coleta Docker). Sem heurística oculta | Não |
| **D-07** | Estratégia de sessão do painel não definida (cookie vs JWT); CSRF citado como "quando aplicável" | PRD §11 | Cookie `HttpOnly; Secure; SameSite=Strict` com token opaco de sessão em tabela `user_sessions` (revogável) + CSRF double-submit. Sem JWT em `localStorage` | Não |
| **D-08** | "Docker socket com acesso irrestrito" é proibido, mas o socket do Docker não oferece modo somente-leitura nativo (entrar no grupo `docker` equivale a root) | PRD §4.3, §9.4; ROADMAP §12 | Agente **não** entra no grupo `docker`. Coleta via `docker-socket-proxy` (GET apenas: `/containers/json`, `/info`, `/containers/{id}/stats`, `/version`) ligado a `127.0.0.1`. Custo: 1 container leve por host com Docker | Sim (aceitar o container extra) |
| **D-09** | Verificações da central podem atingir IPs privados legítimos (as próprias VPS), mas isso é vetor de SSRF | ROADMAP §12 ("evitar SSRF: bloquear endereços proibidos") | Bloqueio por padrão de loopback, link-local, metadados (169.254.169.254) e faixas privadas; liberação explícita por check com `allow_private_target`, restrita a admin e auditada; resolução DNS fixada (anti-rebinding); redirects desabilitados; limite de bytes | Não |
| **D-10** | PRD §8.3 lista "entidades/tabelas iniciais" sem tabela de sessão nem de agregação | PRD §8.3 | Lista é declaradamente inicial. Adicionar `user_sessions`, `metric_aggregates` e `schema_version` (Alembic) com justificativa registrada | Informar |
| **D-11** | Usuário "Operador" é opcional, mas a estrutura de autorização deve permitir expansão | PRD §3 | v1: um administrador; tabela `users` já com `role` (`admin`/`operator`) e RBAC verificado em dependência, sem tela de gestão de usuários | Não |
| **D-12** | PRD §18 exige manter "API de consulta segura" para o Hermes futuro, mas Hermes está fora de escopo | PRD §14, §18 | Nenhum endpoint extra agora. A API administrativa já é versionada e autenticada; a futura camada de ferramentas consumirá esses endpoints com escopo de leitura | Não |

**Nenhuma dessas divergências altera a arquitetura aprovada.** As D-02 e D-08 exigem sua confirmação porque uma renomeia arquivos canônicos e a outra adiciona um container por host.

---

## 5. Estrutura de diretórios recomendada

```
vps-guardian/
├── PRD.md                              # renomeado de PRD-vps-guardian.md
├── ROADMAP.md                          # renomeado de ROADMAP-vps-guardian.md
├── README.md                           # setup local, env vars, comandos
├── CHANGELOG.md                        # histórico por versão (PRD §17.1)
├── .gitignore  .editorconfig  .dockerignore
├── .env.example                        # sem valores reais
├── docker-compose.yml                  # dev: api, worker, frontend, mysql
├── docker-compose.prod.yml             # central/Easypanel (MySQL externo)
├── Makefile                            # atalhos: up, test, lint, migrate
│
├── docs/
│   ├── arquitetura.md                  # topologia, mapeamento PRD↔ROADMAP
│   ├── seguranca.md                    # modelo de ameaças, decisões de auth
│   ├── api.md                          # contrato e convenções
│   ├── instalacao.md                   # central + agente (Ubuntu 22.04/24.04)
│   ├── operacao.md                     # runbook, backup/restore, rollback
│   ├── decisoes/                       # ADRs curtos (ADR-0001-fases.md, ...)
│   └── fases/                          # relatório de conclusão por fase
│
├── backend/
│   ├── pyproject.toml  alembic.ini  Dockerfile  .env.example
│   ├── alembic/
│   │   ├── env.py
│   │   └── versions/
│   ├── app/
│   │   ├── main.py                     # factory FastAPI, middlewares
│   │   ├── core/                       # config, security, logging, rate_limit, errors, clock
│   │   ├── db/                         # engine, session, base, types
│   │   ├── models/                     # SQLAlchemy 2.x (tipado)
│   │   ├── schemas/                    # Pydantic v2 (request/response separados)
│   │   ├── api/
│   │   │   ├── deps.py                 # sessão, usuário atual, agente atual, RBAC
│   │   │   └── v1/                     # auth, servers, agent, metrics, checks,
│   │   │                               # incidents, rules, notifications, integrations, admin
│   │   ├── services/                   # regras de negócio puras e testáveis
│   │   └── workers/                    # scheduler, evaluator, checker, notifier, retention
│   └── tests/
│       ├── conftest.py                 # MySQL de teste (nunca SQLite)
│       ├── unit/  integration/  security/
│
├── frontend/
│   ├── package.json  vite.config.ts  tsconfig.json  Dockerfile  nginx.conf
│   └── src/
│       ├── main.tsx  App.tsx  router.tsx
│       ├── api/                        # cliente tipado + tipos gerados do OpenAPI
│       ├── components/  pages/  hooks/  lib/  styles/
│       └── test/
│
└── agent/
    ├── pyproject.toml  README.md
    ├── guardian_agent/
    │   ├── main.py                     # loop de coleta, sinais, backoff
    │   ├── config.py                   # /etc/vps-guardian/agent.toml (0600)
    │   ├── collectors/                 # cpu, memory, disk, network, uptime, docker, system
    │   ├── transport/                  # HTTPS com timeout, retry, fila local limitada
    │   └── spool.py                    # buffer em disco com teto e descarte auditado
    ├── packaging/
    │   ├── systemd/guardian-agent.service
    │   └── docker-socket-proxy.compose.yml
    ├── scripts/install.sh  uninstall.sh
    └── tests/
```

**Justificativa das escolhas:** separação `api`/`worker` no mesmo código-base (imagem única, comandos distintos) evita divergência de modelos e simplifica o Easypanel; `services/` isola regra de negócio de HTTP, permitindo testar o motor de alertas sem subir a API; `agent/` é um pacote Python independente, sem FastAPI, para manter a superfície mínima no host monitorado.

---

## 6. Tecnologias e versões recomendadas

Versões consultadas hoje nos registries (não são chutes). Critério: manutenção ativa, suporte a MySQL e compatibilidade com o runtime escolhido.

### 6.1 Backend (roda em container, Python 3.12)

| Pacote | Versão | Observação |
|---|---|---|
| Python | 3.12 (imagem `python:3.12-slim-bookworm`) | 3.11+ é exigido por `sqlalchemy 2.1` e `pydantic-settings 2.16` |
| FastAPI | 0.162.0 | OpenAPI automático |
| Uvicorn | 0.54.0 | 2 workers na API |
| SQLAlchemy | 2.1.6 | ORM 2.x tipado |
| Alembic | 1.20.1 | Migrations versionadas |
| Pydantic | 2.14.2 | Validação estrita |
| pydantic-settings | 2.16.2 | Config por env |
| PyMySQL | 1.2.3 | Driver síncrono; requer `cryptography` para `caching_sha2_password` |
| cryptography | 50.0.2 | TLS do driver + Fernet para segredos em repouso |
| argon2-cffi | 25.1.0 | Hash de senha (Argon2id). **Não** usar `passlib` (sem manutenção ativa) |
| structlog | 26.1.0 | Logs JSON estruturados com redação de campos sensíveis |
| slowapi | 0.1.10 | Rate limiting em processo (v1 single-instance) |
| APScheduler | 3.11.3 | Agendamento no worker |
| httpx | 0.28.1 | Webhook n8n + checks HTTP |
| tenacity | 9.2.1 | Backoff de retry |
| pytest | 9.2.0 | Testes |
| pytest-cov / hypothesis | — | Cobertura e testes de propriedade |

### 6.2 Banco de dados

| Item | Recomendação | Observação |
|---|---|---|
| Engine | **MySQL 8.0.x (preferencial) ou 8.4 LTS** | `SELECT ... FOR UPDATE SKIP LOCKED` (fila do worker) exige **MySQL ≥ 8.0.1**. Se o Easypanel oferecer 5.7 ou MariaDB, o design da fila muda — **precisa confirmação** |
| Charset/Collation | `utf8mb4` / `utf8mb4_0900_ai_ci` | PRD §8.3 |
| Engine de tabela | InnoDB | idem |
| Timezone | UTC em todas as colunas de data | idem |

### 6.3 Frontend

| Pacote | Versão | Observação |
|---|---|---|
| React / React DOM | 19.3.1 | |
| TypeScript | 7.0.2 | `strict: true` |
| Vite | 8.3.5 | Build |
| React Router | 7.18.5 | Rotas |
| TanStack Query | 5.105.3 | Cache/refetch e estados de erro |
| Tailwind CSS | 4.3.4 | Design system utilitário |
| Recharts | 3.10.1 | Gráficos (volume baixo; se degradar, migrar para uPlot) |
| Zod | 4.6.7 | Validação de formulários |
| Vitest / Testing Library | 5.1.0 / 16.3.3 | Testes |
| ESLint / Prettier | 10.14.0 / 3.9.10 | Qualidade |

### 6.4 Agente (Python 3.10+ — Ubuntu 22.04 traz 3.10.12)

| Pacote | Versão | Observação |
|---|---|---|
| Python | **3.10+** (alvo 22.04 e 24.04) | **Restrição dura**: nada de `tomllib`, `Self`, `ExceptionGroup`, `match` obrigatório. CI precisa testar 3.10 |
| psutil | 7.2.2 | CPU, RAM, swap, disco, rede |
| httpx | 0.28.1 | HTTPS com timeout (ou `urllib` para zero dependências) |
| stdlib | `logging.handlers.RotatingFileHandler` | Rotação local |
| Empacotamento | wheel + `install.sh` verificável | systemd com hardening |

> **Nota de compatibilidade:** `sqlalchemy 2.1` e `pydantic-settings 2.16` exigem Python ≥ 3.11 e **não** podem ser usados no agente. Backend e agente terão `pyproject.toml` independentes justamente por isso.

### 6.5 Infraestrutura

| Item | Recomendação |
|---|---|
| Imagens base | `python:3.12-slim-bookworm`, `node:22-alpine` (build), `nginx:alpine` (estático) |
| Proxy/TLS | Traefik do Easypanel + Let's Encrypt; TLS obrigatório em produção |
| Orquestração local | Docker Compose v2 |
| Deploy central | Compose/Easypanel, MySQL externo por rede privada |

---

## 7. Dependências

### 7.1 Dependências internas (ordem obrigatória)

```
MySQL 8.x  ──►  migrations  ──►  auth  ──►  servidores/credenciais
                                              └─►  agente (coleta)
                                                     └─►  telemetria
                                                            └─►  checks/docker
                                                                   └─►  motor de alertas
                                                                          └─►  fila
                                                                                 └─►  n8n/EvoGo
```

### 7.2 Dependências externas (todas bloqueiam fases específicas)

| Dependência | Necessária para | Estado |
|---|---|---|
| 9 VPS: nome, IP/hostname, função | Fase 0 | **Não fornecida** |
| Versão exata do Ubuntu por VPS | Fase 0, 4, 5 | **Não fornecida** |
| Painel por VPS (Easypanel/Portainer/ICP) | Fase 0, 8 | **Não fornecida** |
| VPS central escolhida + capacidade | Fase 0, 1 | **Não fornecida** |
| Serviço MySQL do Easypanel (host, porta, versão, rede) | Fase 2 | **Não fornecida** |
| Domínio + TLS da central | Fase 1 | **Não fornecido** |
| Webhook n8n (URL + método de auth) | Fase 10 | **Não fornecido** |
| EvoGo/Evolution API (instância, destinatários) | Fase 10 | **Não fornecido** |
| Acesso administrativo à VPS central | Fase 1, 6 | **Não fornecido** |

### 7.3 Dependências de ambiente local (a resolver)

| Item | Ação necessária | Alternativas |
|---|---|---|
| MySQL 8.x local | Instalar Docker Desktop **ou** MySQL Server 8.x nativo | MySQL remoto do Easypanel (exige rede/túnel — não expor publicamente) |
| Docker Compose | Instalar Docker Desktop | — |
| Linux para o agente | WSL2 **ou** uma VPS de teste | Testes unitários multiplataforma com coletores mockados não cobrem aceite da Fase 4 |

---

## 8. Riscos técnicos

| ID | Risco | Prob. | Impacto | Mitigação proposta |
|---|---|---|---|---|
| R-01 | **Sem MySQL/Docker local não há evidência válida** para "migrations aplicam em banco vazio" e "persistência grava/recupera". SQLite é proibido pelo PRD §17.2.4 | Alta | Alto | Bloquear conclusão da Fase 2 até existir MySQL 8.x acessível; testes de integração falham explicitamente se `TEST_DATABASE_URL` não for MySQL |
| R-02 | **Fila de notificação depende de `SKIP LOCKED`** (MySQL ≥ 8.0.1). Versão do Easypanel é desconhecida | Média | Alto | Confirmar versão na Fase 0; se < 8.0, adotar lock otimista com `version` + `SELECT ... FOR UPDATE` por lote |
| R-03 | **Socket Docker não tem modo read-only nativo**; grupo `docker` ≈ root | Alta | Alto | `docker-socket-proxy` com allowlist de GET; agente sem grupo `docker`; PRD §9.4 atendido sem root |
| R-04 | **Volume de métricas**: 9 hosts × 30 s ≈ 25.920 coletas/dia; com disco e rede por linha, milhões de linhas/mês no MySQL compartilhado do Easypanel | Alta | Médio | Índices compostos `(server_id, collected_at)`, retenção em 3 camadas (7 d bruto, 30 d 5 min, 180 d 1 h), agregação em job idempotente, teste de carga na Fase 11 |
| R-05 | **Central dentro de um dos hosts monitorados** — falha da central cega o monitoramento | Média | Alto | Documentar (PRD §15/§17.6); health checks próprios; arquitetura pronta para verificação externa futura |
| R-06 | **relógio do agente dessincronizado** corrompe séries temporais e detecção de offline | Média | Médio | Armazenar `collected_at` (agente) **e** `received_at` (servidor); rejeitar skew > 300 s; alarme de skew |
| R-07 | **Agente precisa rodar em Python 3.10**; bibliotecas modernas exigem 3.11+ | Média | Médio | `pyproject.toml` separado, `requires-python = ">=3.10"`, CI com matriz 3.10/3.12 |
| R-08 | **SSRF** nas verificações HTTP/TCP da central | Média | Alto | Ver D-09: bloqueio de faixas privadas/metadados por padrão, DNS pinning, sem redirects, limite de bytes |
| R-09 | **Rate limiting em processo** não sobrevive a múltiplas réplicas | Média | Baixo | v1 com 1 réplica de API documentada; abstração de storage permite trocar por store compartilhado sem alterar rotas |
| R-10 | **Segredo do webhook n8n em repouso** no MySQL | Média | Alto | Cifrar com Fernet (`GUARDIAN_SECRET_KEY` fora do banco); nunca retornar em claro após salvo; redigir em logs |
| R-11 | **Deploy no Easypanel** (build de imagem vs Compose) indefinido | Média | Médio | Manter `docker-compose.prod.yml` e Dockerfiles prontos para ambos; decidir na Fase 1 |
| R-12 | **Ambiente dev Windows vs alvo Linux** — diferenças de paths, permissões e systemd | Alta | Médio | Código do agente testável por injeção de dependência; aceite real exige host Linux (Fase 4/5) |
| R-13 | **Backup/restore não testável** sem MySQL acessível | Alta | Alto | Adiado para Fase 11, mas depende de R-01 resolvido antes |

---

## 9. Decisões pendentes

### 9.1 Decisões que eu recomendo e aplico por padrão (diga "discordo" para mudar)

| ID | Decisão | Padrão proposto |
|---|---|---|
| A-01 | Modelo de fases | ROADMAP §3 prevalece; mapeamento PRD↔ROADMAP documentado (D-01) |
| A-02 | Sessão do painel | Cookie `HttpOnly/Secure/SameSite=Strict` + token opaco em `user_sessions` + CSRF double-submit (D-07) |
| A-03 | Hash de senha | Argon2id (`argon2-cffi`), parâmetros OWASP |
| A-04 | Token de agente | 32 bytes aleatórios, armazenado apenas como SHA-256 + prefixo indexado para lookup; exibido **uma vez** na emissão |
| A-05 | Token de provisionamento | 32 bytes, TTL 15 min, uso único, vinculado ao `server_id` |
| A-06 | Autenticação do agente | Header `Authorization: Bearer <token>` sobre TLS; sem cookies; rate limit por credencial |
| A-07 | Webhook n8n | HMAC-SHA256 do corpo + timestamp + `X-Guardian-Event-Id` (idempotência) |
| A-08 | Migrations | Alembic com `alembic upgrade head` em job dedicado `guardian-migrations`; nunca `create_all()` |
| A-09 | Logs | structlog JSON, `request_id`, redação de `password`, `token`, `secret`, `authorization` |
| A-10 | Horário | UTC no banco; `America/Sao_Paulo` na renderização |
| A-11 | Fila | Tabela `notification_queue` com status + `attempts` + `next_attempt_at`; worker com `SKIP LOCKED` |
| A-12 | Testes | pytest + `TEST_DATABASE_URL` MySQL real; testes unitários puros sem banco; frontend com Vitest |

### 9.2 Decisões que dependem exclusivamente de você (bloqueiam fases)

| ID | Decisão | Bloqueia |
|---|---|---|
| B-01 | Autoriza renomear `PRD-vps-guardian.md` → `PRD.md` e `ROADMAP-vps-guardian.md` → `ROADMAP.md`? | Início (organização do repo) |
| B-02 | Autoriza `git init` + primeiro commit com `.gitignore`? | Rastreabilidade de todas as fases |
| B-03 | Autoriza instalar Docker Desktop (ou MySQL 8.x nativo) nesta máquina? Sem isso a Fase 2 não pode ser validada | Fase 2 |
| B-04 | Autoriza o `docker-socket-proxy` no host do agente (1 container leve por VPS com Docker)? | Fase 4/8 |
| B-05 | Qual VPS será a central, e qual sua capacidade? | Fases 0/1 |
| B-06 | Versão do MySQL no Easypanel e forma de acesso privado | Fase 2 |
| B-07 | Domínio e TLS da central | Fase 1 |
| B-08 | URL e autenticação do webhook n8n; instância EvoGo e destinatários | Fase 10 |
| B-09 | Inventário das 9 VPS (nome, IP, Ubuntu, painel, Docker) | Fases 0/5/6 |

---

## 10. Plano de implementação

### 10.1 Fases do ROADMAP e situação real

| Fase | Nome | Pode iniciar agora? | Motivo |
|---|---|---|---|
| 0 | Descoberta e inventário | **Não** | Depende integralmente de B-05..B-09. Diagnóstico técnico já concluído |
| 1 | Preparação da VPS central | **Não** | Depende de acesso à VPS, domínio e TLS |
| 2 | MySQL e fundação do backend | **Parcialmente (local)** | Código e testes unitários sim; aceite de migrations/persistência exige B-03/B-06 |
| 3 | Cadastro e provisionamento | **Após 2** | ROADMAP §6 tem gate explícito |
| 4 | Agente Linux e telemetria | **Após 2** (código sim; aceite em Ubuntu não) | Aceite exige host Linux real (R-12) |
| 5 | Piloto em duas VPS | **Não** | Exige VPS reais e aprovação |
| 6 | Expansão para as nove | **Não** | Gate de aprovação do piloto |
| 7 | Dashboard e histórico | **Após 3** (pode adiantar UI com API local) | Precisa de dados reais para validar "estado reflete heartbeat real" |
| 8 | Docker e verificações | **Após 4** | Depende de agente e de D-09 |
| 9 | Motor de alertas | **Após 3/7** | Núcleo de valor; testável com telemetria sintética **identificada como tal** |
| 10 | WhatsApp via n8n + EvoGo | **Não** | Depende de B-08 |
| 11 | Segurança, backup e produção | **Não** | Depende de ambiente real |

### 10.2 Fatia recomendada para autorização imediata — "Fase 2A: fundação local"

Escopo fechado, sem tocar infraestrutura externa:

1. `git init`, `.gitignore`, `.editorconfig`, `.dockerignore`.
2. Renomear os dois documentos para os nomes canônicos (B-01).
3. `README.md` inicial e `CHANGELOG.md`.
4. Estrutura `backend/` com `pyproject.toml`, `app/main.py` (factory), `core/config.py` (pydantic-settings, sem segredos default), `core/logging.py` (structlog JSON com redação), `core/errors.py`.
5. `db/` com engine SQLAlchemy 2.x + PyMySQL, pool configurado, `pool_pre_ping`.
6. Alembic configurado para MySQL (`alembic.ini`, `env.py`), migration inicial vazia válida.
7. Modelos base: `users`, `user_sessions`, `servers`, `agent_credentials`, `audit_logs` (somente os necessários para autenticação e cadastro — o restante vem nas fases seguintes).
8. Autenticação: `POST /api/v1/auth/login`, `POST /api/v1/auth/logout`, `GET /api/v1/auth/me`; Argon2id; sessão em cookie; CSRF.
9. Rate limiting em `/auth/login` (slowapi) com resposta 429 e auditoria de tentativas falhas.
10. `GET /health` (liveness) e `GET /health/ready` (checa MySQL, sem vazar DSN).
11. `GET /api/v1/system/info` autenticado (versão da API, versão do schema).
12. Seed do primeiro administrador **por variável de ambiente em comando CLI**, nunca hardcoded.
13. Testes: unitários (hash, token, config, redação de log) + integração contra MySQL real (login, sessão, 401/403, rate limit, migration em banco vazio).
14. `docker-compose.yml` com `api`, `worker` (placeholder sem lógica), `mysql:8.0` — validado apenas quando B-03 existir.
15. Relatório da fatia + atualização do bloco "Estado atual" do ROADMAP.

**Fora da fatia 2A, deliberadamente:** telemetria, agente, dashboard, alertas, n8n, Docker.

### 10.3 Critérios de aceite da Fase 0 (quando os dados chegarem)

- [ ] As nove VPS identificadas por nome e função.
- [ ] Inventário privado com IP/hostname, Ubuntu exato, painel e Docker por host.
- [ ] VPS central escolhida com CPU/RAM/disco documentados.
- [ ] Serviço MySQL do Easypanel identificado (versão ≥ 8.0, host interno, porta, rede).
- [ ] Domínio e estratégia de TLS definidos.
- [ ] Contrato técnico do webhook n8n e da instância EvoGo definidos.
- [ ] Nenhum segredo no repositório; dados sensíveis apenas em cofre/ambiente.

### 10.4 Critérios de aceite da fatia 2A (fundação local)

| # | Critério | Evidência exigida |
|---|---|---|
| 1 | API inicia sem erro | log de startup + `GET /health` = 200 |
| 2 | Health check distingue vivo de pronto | `/health/ready` = 200 com MySQL, 503 sem MySQL |
| 3 | Migration aplica em banco vazio | `alembic upgrade head` em schema limpo + `alembic current` |
| 4 | Persistência grava e recupera | teste de integração cria e lê usuário/servidor |
| 5 | Login válido emite sessão | teste: 200, cookie `HttpOnly`, `Secure` em produção |
| 6 | Login inválido não vaza informação | 401 genérico, sem indicar se o e-mail existe |
| 7 | Senha nunca em claro | Argon2id verificável; coluna com hash; teste de rejeição |
| 8 | Rotas administrativas exigem sessão | 401 sem cookie; 403 para role insuficiente |
| 9 | Rate limit funciona | 429 após N tentativas; tentativa registrada em `audit_logs` |
| 10 | Segredos não aparecem em log | teste que injeta senha/token e afirma ausência na saída |
| 11 | Nenhum segredo no Git | revisão manual + `grep` por padrões |
| 12 | Testes automatizados passam | saída completa do `pytest` anexada ao relatório |

> Os critérios 1–3, 4 e 12 dependem de MySQL real (B-03/B-06). Sem isso, a fatia fica **parcialmente validada** e não será declarada concluída.

---

## 11. Pré-requisitos para começar

**Bloqueantes (sem eles não há implementação válida):**
1. B-01 e B-02 — renomeação dos documentos e `git init` (baixo risco, decisão sua).
2. B-03 — Docker Desktop **ou** MySQL 8.x nesta máquina, para os critérios de aceite 2–4 e 12.

**Bloqueantes de fase (não impedem a fatia 2A):**
3. B-05 a B-09 — inventário, VPS central, MySQL Easypanel, domínio/TLS, n8n/EvoGo.

**Não bloqueante, mas recomendado antes da Fase 4:**
4. WSL2 ou uma VPS de teste para validar o agente em Linux.

---

## 12. Qual fase pode ser iniciada com segurança

**Resposta objetiva:** a **Fase 0 do ROADMAP não pode ser iniciada** — ela é inteiramente composta de coleta de dados de infraestrutura que você ainda não forneceu, e o próprio ROADMAP §4 a declara bloqueante ("não avançar para implantação central se não houver capacidade ou conectividade segura confirmada").

O que pode ser iniciado com segurança, e é o que recomendo, é a **Fase 2A (fundação local do backend)**, condicionada a B-01, B-02 e B-03. Justificativa: o PRD §17.3 determina que a implantação na VPS central só ocorra após validar localmente Docker, migrations, autenticação, backups e variáveis de ambiente — ou seja, o trabalho local é pré-requisito do próprio ROADMAP, não um atalho. Nenhum critério de aceite de fase é contornado, porque a fatia 2A **só será declarada concluída** com MySQL real.

Se você preferir a leitura estrita do ROADMAP (nada antes da Fase 2 completa, e Fase 2 depende da Fase 1), então **nenhuma fase pode ser iniciada** e o projeto permanece bloqueado em B-05..B-09.

---

## 13. O que não farei sem sua autorização

- Renomear/mover os documentos canônicos, inicializar repositório ou commitar.
- Instalar Docker, MySQL, WSL ou qualquer software nesta máquina.
- Criar credenciais, tokens ou segredos de qualquer tipo.
- Acessar, alterar ou instalar qualquer coisa em VPS reais.
- Criar endpoints administrativos, de execução de comandos ou de shell.
- Substituir MySQL por SQLite, inclusive em testes.
- Adiantar qualquer parte do Hermes Agent.

---

## 14. Próximo passo proposto

Aguardo sua resposta a três perguntas objetivas para iniciar:

1. **B-01/B-02:** autoriza renomear para `PRD.md`/`ROADMAP.md` e executar `git init` com `.gitignore` + primeiro commit?
2. **B-03:** prefere instalar **Docker Desktop** (recomendado: valida Compose, MySQL 8.0 e backup/restore como em produção), instalar **MySQL 8.x nativo**, ou apontar para um MySQL de teste remoto por túnel seguro?
3. **Escopo de início:** aprova iniciar pela **Fase 2A (fundação local)**, ou prefere manter a ordem estrita e permanecer bloqueado até responder B-05..B-09?

Com essas três respostas, inicio a implementação e entrego o relatório da fase no formato da seção 12 do prompt mestre.
