# Arquitetura — VPS Guardian

Este documento consolida a arquitetura aprovada no `PRD.md` e a ordem de execução do
`ROADMAP.md`. Em caso de divergência, ver [ADR-0002](decisoes.md#adr-0002--roadmap-prevalece-sobre-o-prd-na-ordem-de-execução).

## 1. Topologia

```
┌──────────────────────── VPS central (Easypanel) ─────────────────────────┐
│  Traefik (TLS/Let's Encrypt)                                             │
│     ├── guardian-frontend   React/TS estático (nginx)                    │
│     ├── guardian-api        FastAPI — ingestão, CRUD, auth, auditoria    │
│     ├── guardian-worker     regras, checks, fila, retenção               │
│     └── guardian-migrations job único: alembic upgrade head              │
└──────────────────────────────────┬───────────────────────────────────────┘
                                   │ rede privada (MySQL não exposto)
                         ┌─────────▼──────────┐
                         │ MySQL 8.x Easypanel │  vps_guardian (InnoDB/utf8mb4)
                         └────────────────────┘

  VPS monitoradas 1..9 (7 Easypanel, 1 Portainer, 1 ICP Integrator)
  guardian-agent (systemd, Python 3.10+)
      ├── coleta local: CPU, RAM, swap, disco, rede, uptime
      ├── Docker: API somente leitura via socket-proxy local (127.0.0.1)
      └── HTTPS de saída ──► guardian-api /api/v1/agent/*
```

**Nenhuma porta de entrada é aberta nas VPS monitoradas.** O agente sempre inicia a
conexão (PRD §2.2, §9.1).

## 2. Fluxo de telemetria e alerta

1. Agente coleta dados locais e envia payload autenticado por HTTPS.
2. `guardian-api` valida identidade, tamanho e esquema; persiste a telemetria.
3. `guardian-worker` avalia regras (duração mínima, falhas consecutivas).
4. Incidente é aberto/atualizado/resolvido no MySQL, com deduplicação por chave.
5. Notificação entra na fila persistida (`notification_queue`).
6. Worker envia webhook assinado ao n8n; n8n aciona EvoGo/Evolution → WhatsApp.
7. Resultado de cada tentativa é registrado (`notification_attempts`).

A ingestão **nunca** bloqueia no envio de notificação (PRD §6.4, §12.1).

## 3. Planos de autenticação (isolados)

| Plano | Quem | Credencial | Transporte |
|---|---|---|---|
| Painel | administrador/operador | sessão opaca em `user_sessions` | cookie `HttpOnly` + CSRF token |
| Agente | servidor VPS | credencial individual (hash em `agent_credentials`) | `Authorization: Bearer` |
| Provisionamento | instalador | token temporário (hash em `provisioning_tokens`) | corpo de `POST /agent/register`, uso único |

Um token de agente **nunca** é aceito em rotas do painel e vice-versa.

## 4. Mapeamento PRD §13 ↔ ROADMAP §3

| PRD §13 | ROADMAP §3 | Observação |
|---|---|---|
| Fase 1 — Fundação | Fases 0, 1, 2, 3 | O ROADMAP separa descoberta, preparação da VPS, fundação e cadastro |
| Fase 2 — Agente e telemetria | Fases 4, 5, 6 | Inclui piloto e expansão gradual |
| Fase 3 — Dashboard | Fase 7 | Movido para depois de existir dado real |
| Fase 4 — Serviços e disponibilidade | Fase 8 | Docker + checks HTTP/TCP |
| Fase 5 — Alertas e WhatsApp | Fases 9, 10 | Motor de alertas separado da integração |
| Fase 6 — Hardening | Fase 11 | Segurança, backup, produção |

## 5. Serviços e portas

| Serviço | Porta interna | Exposição |
|---|---|---|
| `guardian-api` | 8000 | via Traefik, HTTPS |
| `guardian-frontend` | 80 | via Traefik, HTTPS |
| `guardian-mysql` (opcional) | 3306 | **somente rede interna do compose** |
| `guardian-worker` | — | sem porta |

Dois modos de implantação, ambos com migrations automáticas no boot:

1. **Stack completo** (`docker-compose.yml`) — MySQL 8 no próprio compose, volume
   `mysql_data`, sem porta publicada. É o modo padrão e o mais rápido de subir.
2. **MySQL do Easypanel** (`docker-compose.external-db.yml`) — apenas API e job de
   migrations, apontando para o banco gerenciado via rede privada.

O entrypoint da API executa `wait-db` e `alembic upgrade head` antes de iniciar o
Uvicorn, garantindo que o schema exista antes da primeira requisição.

## 6. Modelo de dados (evolução)

O PRD §8.3 lista as entidades iniciais. A ordem de criação segue as fases:

| Migration | Tabelas |
|---|---|
| `0001_initial` | `users`, `user_sessions`, `servers`, `agent_credentials`, `provisioning_tokens`, `audit_logs`, `system_settings` |
| `0002_telemetry` (fase 4) | `agent_heartbeats`, `host_metrics`, `disk_metrics`, `network_metrics` |
| `0003_docker_checks` (fase 8) | `docker_daemons`, `containers`, `container_states`, `checks`, `check_results` |
| `0004_alerts` (fase 9) | `alert_rules`, `incidents`, `incident_events` |
| `0005_notifications` (fase 10) | `notification_channels`, `notification_queue`, `notification_attempts` |

Convenções: PKs `BIGINT UNSIGNED` auto-incrementais para séries temporais e `CHAR(36)`
(UUIDv4) para entidades de negócio; datas **sempre UTC**; índices compostos
`(server_id, collected_at)` nas séries; JSON nativo do MySQL 8 para payloads flexíveis.

## 7. Observabilidade da própria central

`GET /health` (liveness, sem dependências) e `GET /health/ready` (MySQL + versão de
schema). Nas fases seguintes: saúde do worker, profundidade da fila, espaço em disco e
último processamento bem-sucedido (PRD §17.6).

Como a central roda em uma das VPS monitoradas, uma falha dela interrompe detecção e
envio. Isso está registrado como risco R-05 no diagnóstico técnico.
