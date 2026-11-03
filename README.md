# VPS Guardian

Plataforma própria, centralizada e auto-hospedada para monitorar servidores VPS Linux,
consolidando métricas, disponibilidade, containers e incidentes em um único painel, com
alertas entregues ao WhatsApp via **n8n + EvoGo/Evolution API**.

- **Requisitos (fonte de verdade):** [`PRD.md`](PRD.md) e [`ROADMAP.md`](ROADMAP.md)
- **Arquitetura e decisões:** [`docs/arquitetura.md`](docs/arquitetura.md) e [`docs/decisoes.md`](docs/decisoes.md)
- **Diagnóstico inicial:** [`docs/fase-0/diagnostico-tecnico.md`](docs/fase-0/diagnostico-tecnico.md)

## Stack

| Camada | Tecnologia |
|---|---|
| Backend/API | Python 3.12 + FastAPI + SQLAlchemy 2 + Alembic + Pydantic v2 |
| Banco | MySQL 8.0+ (InnoDB, `utf8mb4`) no Easypanel, via rede privada |
| Frontend | React + TypeScript + Vite (fase 7) |
| Agente | Python 3.10+ (compatível com Ubuntu 22.04/24.04), serviço `systemd` |
| Integrações | Webhook n8n → EvoGo/Evolution API |
| Deploy | Docker + Docker Compose no Easypanel |

## Estratégia de desenvolvimento e testes

Este projeto é **desenvolvido code-first e validado na VPS**. Não há ambiente de execução
local obrigatório: a validação funcional (migrations, autenticação, telemetria, alertas)
ocorre no ambiente Easypanel + MySQL, conforme a decisão [ADR-0001](docs/decisoes.md).

Testes automatizados vivem no repositório e são executados:

- **na VPS/CI**, contra um MySQL real (`GUARDIAN_TEST_DATABASE_URL`);
- **localmente, opcionalmente**, apenas como suíte de unidade sem banco.

> Testes de integração **nunca** usam SQLite como substituto do MySQL (PRD §17.2.4).
> Sem MySQL disponível, eles são marcados como *skipped* com motivo explícito, e não
> como aprovados.

## Estrutura

```
docker-compose.yml              stack completo: MySQL 8 + API + migrations automáticas
docker-compose.external-db.yml  API usando o MySQL já existente do Easypanel
.env.example                    modelo de variáveis (copiar para .env na VPS)
backend/                        API FastAPI, modelos, migrations, testes
deploy/                         bootstrap/seed MySQL e guia de instalação
docs/                           arquitetura, decisões (ADRs), relatórios de fase
agent/                          agente Linux (fase 4+)
frontend/                       painel React (fase 7+)
```

## Desenvolvimento local (opcional, sem serviços)

```bash
cd backend
python -m venv .venv && . .venv/bin/activate
pip install -e ".[dev]"
pytest -m unit            # apenas unidade, não precisa de banco
```

## Instalação na VPS (resumo)

Detalhes em [`deploy/README.md`](deploy/README.md). O fluxo é:

1. `cp .env.example .env` e preencher os quatro valores obrigatórios
   (`GUARDIAN_SECRET_KEY`, `MYSQL_ROOT_PASSWORD`, `GUARDIAN_DB_PASSWORD`,
   `GUARDIAN_PUBLIC_BASE_URL`).
2. `docker compose up -d --build` — o MySQL sobe, a API espera o banco e aplica as
   migrations automaticamente.
3. Conferir `GET /health/ready` → `ready` com `schema_revision=0002_telemetry`.
4. Criar o administrador: `docker compose exec api python -m app.cli create-admin ...`.
5. Cadastrar a VPS, emitir o token e instalar o agente no host monitorado:

```bash
sudo bash agent/scripts/install.sh \
  --server-id <UUID> \
  --token <token-de-provisionamento> \
  --api-url https://guardian.seudominio.com
```

Guia do agente: [`agent/README.md`](agent/README.md).

## Segurança (resumo)

- Sem portas de entrada nas VPS monitoradas: o agente inicia a conexão de saída por HTTPS.
- Credencial individual por servidor, armazenada apenas como hash; exibida uma única vez.
- Token de provisionamento temporário (TTL curto, uso único) trocado por credencial permanente.
- Senhas com Argon2id; sessão em cookie `HttpOnly`/`Secure` com CSRF double-submit.
- MySQL nunca exposto publicamente; segredos apenas por variável de ambiente.
- Nenhum endpoint de execução de shell/comando remoto existe ou existirá na v1.0.

## Licença

Projeto privado. Todos os direitos reservados.
