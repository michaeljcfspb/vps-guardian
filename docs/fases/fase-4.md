# Relatório de fase — Agente Linux e telemetria (Fase 4)

**Data:** 03/11/2026
**Fase:** ROADMAP §8 (Fase 4)
**Status:** Implementação concluída; **aceite em Ubuntu pendente** (depende de host real)
**Decisão de processo:** [ADR-0001](../decisoes.md#adr-0001--desenvolvimento-code-first-validação-funcional-na-vps)

---

## 1. O que foi implementado

### 1.1 Central — ingestão de telemetria

- Migration `0002_telemetry` com 4 tabelas: `agent_heartbeats`, `host_metrics`,
  `disk_metrics`, `network_metrics` (InnoDB, `utf8mb4`, índices compostos
  `(server_id, collected_at)`).
- **Idempotência**: `host_metrics` tem `UNIQUE (server_id, collected_at)`. Reenvio
  após timeout não duplica a série — o endpoint responde `recorded=false, duplicate=true`.
- `POST /api/v1/agent/metrics` com validação estrita:
  - `collected_at` obrigatoriamente com fuso; aceito entre −24 h e +5 min;
  - CPU/RAM/swap/percentuais limitados a 0–100;
  - `used ≤ total`, `available ≤ total`, `swap_used ≤ swap_total`;
  - discos: máximo 64 pontos, sem caracteres de controle, `used/free ≤ total`;
  - rede: máximo 32 interfaces, nome restrito a `[A-Za-z0-9_.:@-]{1,32}`;
  - campos desconhecidos rejeitados (`extra=forbid`).
- Heartbeat passa a gravar histórico em `agent_heartbeats` (PRD §4.5, §7.3).
- `GET /agent/config` agora anuncia `features.metrics = true`.
- `last_metrics_at` e `agent_version` atualizados a cada coleta aceita.

### 1.2 Agente Linux (`agent/`)

- Pacote Python independente (`vps-guardian-agent` 0.2.0), **Python 3.10+**
  (Ubuntu 22.04), dependência externa única: `psutil`.
- Coleta: CPU + load average, RAM, swap, disco por ponto de montagem (com filtro de
  pseudo-filesystems), rede por interface com **taxa em bits/s** calculada entre
  coletas, uptime, contagem de processos.
- **Buffer local limitado** (spool): limite por quantidade (120) e idade (6 h);
  escrita atômica; descarte do mais antigo; payload inválido (4xx) é descartado para
  não travar a fila.
- **Transporte HTTPS** com timeout, backoff exponencial e jitter; 5xx/429/rede são
  transitórios; 4xx é permanente (sem retry inútil).
- **Registro único**: o primeiro start troca o token de provisionamento pela credencial
  permanente e reescreve o config sem o token.
- Config JSON em `/etc/vps-guardian/agent.json`, permissão `0600`, escrita atômica,
  leitura tolerante a BOM.
- Logs JSON com rotação (5 MB × 3) e filtro que mascara segredos registrados.
- `systemd` endurecido: usuário `vps-guardian` sem shell, `CapabilityBoundingSet=`,
  `ProtectSystem=strict`, `ProtectHome`, `PrivateTmp`, `RestrictAddressFamilies`,
  `SystemCallFilter`, escrita liberada apenas em `/var/lib` e `/var/log` do agente.
- Instalador e desinstalador auditáveis (`scripts/install.sh`, `uninstall.sh`) — sem
  download remoto e sem `curl | bash`.
- Nenhuma chamada a `subprocess`, `os.system`, shell ou socket de Docker no pacote.

## 2. Arquivos criados

| Arquivo | Finalidade |
|---|---|
| `backend/alembic/versions/0002_telemetry.py` | 4 tabelas de série temporal |
| `backend/app/models/telemetry.py` | Modelos ORM correspondentes |
| `backend/app/services/telemetry.py` | Ingestão idempotente, janelas de tempo, heartbeat |
| `backend/app/api/v1/agent.py` (alterado) | Rota `/agent/metrics`, heartbeat histórico |
| `backend/app/schemas/agent.py` (alterado) | Contrato de telemetria com validação estrita |
| `backend/tests/unit/test_metrics_schema.py` | 11 testes do contrato |
| `backend/tests/integration/test_metrics.py` | 9 testes de ingestão (MySQL real) |
| `agent/pyproject.toml` | Pacote, entrypoint e marcadores de teste |
| `agent/guardian_agent/config.py` | Config 0600 com validação de URL/intervalo |
| `agent/guardian_agent/spool.py` | Buffer local limitado |
| `agent/guardian_agent/state.py` | Contadores de rede entre coletas |
| `agent/guardian_agent/transport.py` | Cliente HTTPS com retry classificado |
| `agent/guardian_agent/runner.py` | Ciclo: coleta → envio → buffer → heartbeat |
| `agent/guardian_agent/main.py` | CLI (`--once`, `--dry-run`, `--version`), sinais |
| `agent/guardian_agent/logging_setup.py` | Log JSON rotativo com máscara de segredos |
| `agent/guardian_agent/collectors/*` | CPU, memória, disco, rede, sistema |
| `agent/packaging/systemd/guardian-agent.service` | Unidade endurecida |
| `agent/scripts/install.sh`, `uninstall.sh` | Instalação/remoção auditáveis |
| `agent/README.md` | Guia de instalação, configuração e segurança |
| `agent/tests/*` | 55 testes de unidade |

## 3. Arquivos modificados

- `backend/app/models/__init__.py` — registro dos modelos de telemetria.
- `ROADMAP-vps-guardian.md` — checkboxes da Fase 4 e bloco "Estado atual".
- `CHANGELOG.md`, `README.md` — documentação da entrega.
- `docs/arquitetura.md` — tabelas da migration `0002_telemetry` (já previstas).

## 4. Testes realizados

Ambiente: venv descartável em `%TEMP%`, sem banco e sem serviços.

| Verificação | Resultado |
|---|---|
| `pytest -m unit` (backend) | **66 passed** |
| `pytest -m unit` (agente) | **55 passed** |
| `ruff check` (backend e agente) | **All checks passed** |
| `alembic upgrade head --sql` | 11 tabelas, 19 índices, 5 FKs — SQL MySQL válido |
| OpenAPI | 20 rotas |
| `guardian-agent --dry-run` (coleta real) | payload válido: CPU 15,5 %, 8 núcleos, RAM 8,4 GB (81,8 %), swap, 1 disco, uptime 785 060 s, 266 processos |
| `pytest -m integration` | **46 skipped** — sem `GUARDIAN_TEST_DATABASE_URL` |

### Não executados (e por quê)

| Item | Motivo |
|---|---|
| Instalação em Ubuntu 22.04/24.04 | exige host Linux real |
| Serviço após reboot e recuperação de falha | idem |
| Métricas recebidas × locais (tolerância) | exige central + agente reais |
| Consumo de CPU/RAM do agente | medido no piloto (Fase 5) |

## 5. Pendências

1. Instalar em um host Ubuntu e validar que o servidor fica `online` no painel.
2. Executar `pytest -m integration` na VPS (9 novos testes de telemetria).
3. Medir e registrar o consumo real do agente.
4. Job de retenção/agregação (7 d bruto / 30 d 5 min / 180 d 1 h) — previsto para a
   Fase 11; hoje as tabelas crescem sem expurgo.
5. Coleta Docker (socket-proxy somente leitura) — Fase 8.

## 6. Bloqueios

| Bloqueio | Impacto |
|---|---|
| VPS com Ubuntu + token de provisionamento | impede o aceite da fase |
| MySQL do Easypanel | impede testar a ingestão de ponta a ponta |
| Domínio/TLS | o agente exige HTTPS (por desenho) |

## 7. Próxima fase

Recomendação: **Fase 7 — dashboard e histórico**. Com telemetria já persistida, o
dashboard é o que permite validar visualmente o piloto (Fase 5) de 24 h. Alternativa
com valor imediato: **Fase 9 — motor de alertas**, que não depende de UI.

Ordem sugerida para quando a VPS estiver disponível:

1. subir a central (`docker compose up -d --build`);
2. criar servidor + token;
3. `install.sh` no host piloto;
4. observar 24 h;
5. só então aprovar a expansão para as nove VPS.

## 8. Status do ROADMAP

- Fase 4: tarefas de implementação `[x]`; critérios que dependem de Ubuntu `[ ]`.
- Fases 2 e 3: seguem com aceite pendente na VPS.
- Versão 1.0: **não liberada**.
