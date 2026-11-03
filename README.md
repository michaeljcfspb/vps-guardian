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
backend/     API FastAPI, modelos, migrations, testes
agent/       agente Linux (fases 4+)
frontend/    painel React (fase 7+)
deploy/      compose, bootstrap MySQL, seeds de teste
docs/        arquitetura, decisões (ADRs), relatórios de fase
```

## Desenvolvimento local (opcional, sem serviços)

```bash
cd backend
python -m venv .venv && . .venv/bin/activate
pip install -e ".[dev]"
pytest -m unit            # apenas unidade, não precisa de banco
```

## Instalação na VPS (resumo)

Detalhes em [`deploy/README.md`](deploy/README.md). O fluxo previsto é:

1. Criar banco `vps_guardian` e usuário de privilégio mínimo no MySQL do Easypanel.
2. Configurar variáveis de ambiente (`GUARDIAN_*`) no serviço do Easypanel — nunca no repositório.
3. Publicar `guardian-api` (e, nas fases seguintes, `guardian-worker` e `guardian-frontend`).
4. Executar o job `guardian-migrations` (`alembic upgrade head`).
5. Criar o administrador inicial via CLI (senha fornecida na hora, nunca versionada).
6. Instalar o agente nas VPS monitoradas, uma por vez.

## Segurança (resumo)

- Sem portas de entrada nas VPS monitoradas: o agente inicia a conexão de saída por HTTPS.
- Credencial individual por servidor, armazenada apenas como hash; exibida uma única vez.
- Token de provisionamento temporário (TTL curto, uso único) trocado por credencial permanente.
- Senhas com Argon2id; sessão em cookie `HttpOnly`/`Secure` com CSRF double-submit.
- MySQL nunca exposto publicamente; segredos apenas por variável de ambiente.
- Nenhum endpoint de execução de shell/comando remoto existe ou existirá na v1.0.

## Licença

Projeto privado. Todos os direitos reservados.
