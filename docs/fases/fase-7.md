# Relatório de fase — Dashboard e histórico (Fase 7)

**Data:** 03/11/2026
**Fase:** ROADMAP §11 (Fase 7)
**Status:** Implementação concluída; validação visual depende de dados reais na VPS
**Decisão de processo:** [ADR-0001](../decisoes.md#adr-0001--desenvolvimento-code-first-validação-funcional-na-vps)

---

## 1. O que foi implementado

### 1.1 Backend — leitura para o painel

| Endpoint | Função |
|---|---|
| `GET /api/v1/dashboard/summary` | totais por estado, médias de CPU/RAM/disco da última coleta, idade dos dados, contadores de incidentes (sinalizados como indisponíveis até a fase 9) |
| `GET /api/v1/telemetry/latest` | última coleta de cada servidor (CPU, RAM, swap, pior disco, rede, uptime) para a tabela do dashboard |
| `GET /api/v1/servers/{id}/metrics?window=1h\|6h\|24h\|7d` | série agregada em buckets no MySQL (`AVG`/`MAX`), no máximo ~170 pontos |
| `GET /api/v1/servers/{id}/heartbeats?limit=N` | histórico recente de heartbeat |

Todas exigem sessão do painel; nenhuma aceita credencial de agente. A agregação é feita
em SQL (`GROUP BY` por bucket), evitando trazer dezenas de milhares de linhas para o
processo. O rótulo de cada ponto vem de `MIN(collected_at)`, então o horário exibido é o
real da coleta, independente do fuso da sessão do MySQL.

### 1.2 Frontend (`frontend/`)

React 19 + TypeScript + Vite + Tailwind 4 + TanStack Query + Recharts.

- **Login** com e-mail/senha, sessão por cookie `HttpOnly` e CSRF double-submit lido do
  cookie `guardian_csrf`; nenhum token em `localStorage`.
- **Dashboard**: 6 indicadores (servidores, CPU/RAM/disco médios, incidentes, última
  comunicação), busca, filtro por estado e tabela com métricas por servidor, badge de
  estado e idade da última comunicação.
- **Detalhe do servidor**: KPIs atuais com barras de uso, janela de tempo (1h/6h/24h/7d),
  gráfico CPU/RAM/Swap/Disco, gráfico de rede (recebido/enviado), heartbeats recentes,
  informações do sistema e credenciais ativas.
- **Ações administrativas** (apenas `admin`): cadastrar servidor, pausar/retomar,
  desativar (com confirmação), emitir token de provisionamento, rotacionar credencial e
  revogar — os dois primeiros exibem o segredo **uma única vez** em modal.
- Estados de **loading, vazio e erro** em todas as consultas, com botão "tentar
  novamente"; `401` redireciona para o login.
- Timestamps em UTC na API, exibidos em `America/Sao_Paulo` (PRD §4.2).
- Code splitting: o detalhe (com Recharts) é carregado sob demanda — bundle inicial
  ~98 kB gzip, detalhe ~112 kB gzip.

### 1.3 Empacotamento

- `frontend/Dockerfile` multi-stage (Node 22 → nginx 1.29), imagem final sem toolchain.
- `nginx.conf`: SPA fallback, cabeçalhos de segurança, proxy `/api` e `/health` para o
  serviço `api` — mesma origem, sem CORS e sem expor a API diretamente.
- Serviço `frontend` adicionado aos dois composes, com `read_only`, `no-new-privileges`
  e tmpfs para o nginx.
- Build reproduzível: `pnpm-lock.yaml` versionado e `pnpm install --frozen-lockfile`.

## 2. Arquivos criados

| Arquivo | Finalidade |
|---|---|
| `backend/app/schemas/dashboard.py` | Contratos do resumo, série, heartbeat e latest |
| `backend/app/services/dashboard.py` | Agregação em SQL e montagem das séries |
| `backend/app/api/v1/dashboard.py`, `telemetry.py` | Rotas de leitura |
| `backend/app/api/v1/servers.py` (alterado) | `/metrics` e `/heartbeats` |
| `backend/tests/integration/test_dashboard.py` | 6 testes de integração |
| `backend/tests/unit/test_dashboard_windows.py` | 2 testes das janelas |
| `frontend/package.json`, `tsconfig.json`, `vite.config.ts`, `index.html`, `nginx.conf`, `Dockerfile` | Base do painel |
| `frontend/src/lib/{api,types,format,auth}.ts` | Cliente tipado, tipos, formatação, sessão |
| `frontend/src/components/{ui,charts,Layout,NewServerModal}.tsx` | Componentes e gráficos |
| `frontend/src/pages/{LoginPage,DashboardPage,ServerDetailPage,NotFoundPage}.tsx` | Telas |
| `frontend/src/{App,main}.tsx`, `src/index.css` | Roteamento, bootstrap e tema |

## 3. Testes realizados

| Verificação | Resultado |
|---|---|
| Backend `pytest -m unit` | **72 passed** |
| Agente `pytest -m unit` | **55 passed** |
| Backend `ruff` | All checks passed |
| Frontend `pnpm build` (tsc + vite) | **sucesso** — 656 módulos, sem erro de tipo |
| Rotas na API | 24 |
| Integração | **52 skipped** (sem MySQL) |

O build do frontend falhou duas vezes por tipagem estrita (`data` possivelmente
`undefined` no TanStack Query v5) e foi corrigido com guarda explícita antes do uso.

## 4. Pendências

1. Validar visualmente com 9 servidores reais (dados, gráficos, idade).
2. Testar em dispositivos móveis reais (layout responsivo implementado, não testado).
3. Filtros por **tag** e **painel** (hoje: busca + estado).
4. Paginação de UI na tabela (hoje carrega até 200 servidores).
5. Tela de incidentes e notificações — dependem das fases 9 e 10.
6. Coleta de containers na tabela — fase 8.

## 5. Bloqueios

- Sem MySQL/VPS com dados reais, não há como validar os critérios visuais de aceite.
- O painel assume a API na mesma origem (`/api`); em domínios separados é preciso
  configurar `VITE_API_BASE_URL` e CORS no backend.

## 6. Próxima fase

**Fase 8 — Docker e verificações de disponibilidade** (containers, HTTP/TCP), ou
**Fase 9 — motor de alertas**, que destrava a tela de incidentes.

## 7. Status do ROADMAP

Fase 7: tarefas de implementação `[x]`, com pendências explícitas em filtros por
tag/painel, paginação e teste em mobile. Versão 1.0 continua **não liberada**.
