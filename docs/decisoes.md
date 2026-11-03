# Decisões de arquitetura (ADRs)

Registro curto das decisões técnicas tomadas durante a implementação. Cada decisão
indica contexto, escolha e consequências. Divergências entre `PRD.md` e `ROADMAP.md`
são resolvidas aqui, nunca em silêncio.

---

## ADR-0001 — Desenvolvimento code-first; validação funcional na VPS

**Data:** 03/11/2026
**Status:** Aceita (decisão do responsável do projeto)

### Contexto
O PRD §17.3 sugere validar Docker, migrations, autenticação e backups localmente antes
da implantação. O responsável pelo projeto determinou que não haverá execução local
obrigatória: o sistema é desenvolvido no repositório e instalado na VPS Easypanel +
MySQL, onde é testado de ponta a ponta.

### Decisão
1. O desenvolvimento é **code-first**: código, migrations, testes e documentação são
   produzidos e versionados; nenhum serviço é executado localmente por obrigação.
2. A validação funcional (migrations, autenticação, telemetria, alertas, n8n) ocorre no
   ambiente Easypanel + MySQL, após a instalação.
3. Testes de integração exigem MySQL real via `GUARDIAN_TEST_DATABASE_URL`. Sem essa
   variável, são **skipped** com motivo explícito — nunca aprovados por omissão.
4. SQLite continua proibido como substituto do MySQL (PRD §17.2.4).
5. Testes de unidade (hash, tokens, rate limit, redação de log, validação de esquema)
   não precisam de banco e podem rodar em qualquer ambiente.

### Consequências
- (+) Nenhuma infraestrutura local necessária; foco no que será executado em produção.
- (+) O repositório permanece a única fonte de verdade.
- (−) O ciclo de feedback é mais lento: erros de integração aparecem na VPS.
- Mitigação: migrations escritas à mão e revisadas, validação estática no CI, health
  checks e logs estruturados que tornam a primeira instalação diagnosticável.
- O critério de aceite "migrations aplicam em banco vazio" passa a ser comprovado na
  VPS, com saída registrada no relatório da fase.

---

## ADR-0002 — ROADMAP prevalece sobre o PRD na ordem de execução

**Data:** 03/11/2026
**Status:** Aceita

### Contexto
O PRD §13 define 6 fases; o ROADMAP §3 define 12 (0–11). Posições divergem (por
exemplo, o dashboard aparece na fase 3 do PRD e na fase 7 do ROADMAP).

### Decisão
O `ROADMAP.md` é a fonte de verdade da **sequência**; o `PRD.md` é a fonte de verdade do
**escopo e dos requisitos**. O mapeamento está em `docs/arquitetura.md` §4.

### Consequências
- O dashboard só é entregue após existir telemetria real (evita UI sobre dados falsos).
- Toda fase é reportada com evidência antes de avançar.

---

## ADR-0003 — Sessão opaca em banco com CSRF double-submit

**Data:** 03/11/2026
**Status:** Aceita

### Contexto
O PRD §11 exige autenticação forte, proteção CSRF "quando aplicável" e não define a
estratégia de sessão.

### Decisão
- Login por e-mail e senha com **Argon2id** (`argon2-cffi`), parâmetros OWASP.
- Sessão representada por token opaco de 256 bits; no banco fica apenas `sha256(token)`
  em `user_sessions`, com expiração absoluta e ociosa, revogação e auditoria.
- Cookie `HttpOnly`, `Secure` (em produção), `SameSite=Strict`.
- CSRF por **double-submit**: token aleatório em cookie legível + header
  `X-CSRF-Token`; o hash confere contra `user_sessions.csrf_token_hash`.
- Nenhum token em `localStorage` e nenhum JWT auto-contido: sessão precisa ser revogável.

### Consequências
- (+) Revogação imediata, rotação simples, sem estado no cliente.
- (+) Testável sem criptografia de chave assimétrica.
- (−) Uma consulta ao banco por requisição autenticada (aceitável nesta escala).
- Se a API escalar horizontalmente, sessões continuam válidas (estado compartilhado no
  MySQL), mas o rate limiting em memória não — ver ADR-0006.

---

## ADR-0004 — Credenciais de agente e de provisionamento somente como hash

**Data:** 03/11/2026
**Status:** Aceita

### Contexto
O PRD exige token individual por VPS, armazenamento não recuperável após a emissão,
rotação e revogação (PRD §4.1, §9.4, §11).

### Decisão
- Token de agente: 32 bytes aleatórios (`secrets.token_urlsafe(32)`), exibido **uma
  única vez** na resposta que o cria.
- Persistência: `sha256(token)` (hex de 64 caracteres) em coluna `UNIQUE`, mais um
  prefixo de 12 caracteres para identificação visual/auditoria sem revelar o segredo.
- Hash SHA-256 (e não Argon2) é adequado porque o token tem 256 bits de entropia real:
  não há ataque de dicionário viável e o lookup precisa ser por índice.
- Token de provisionamento: mesma construção, TTL de 15 minutos, uso único, vinculado a
  um `server_id`; ao emitir um novo, os anteriores não usados são revogados.
- Rotação invalida a credencial anterior no mesmo commit (sem janela de sobreposição).

### Consequências
- (+) Vazamento do banco não permite autenticar como agente.
- (+) Revogação e rotação auditáveis.
- (−) Perda do token exige reemissão; não há recuperação — comportamento intencional.

---

## ADR-0005 — MySQL 8.0+ como requisito, sem fallback

**Data:** 03/11/2026
**Status:** Aceita (sujeita à confirmação da versão no Easypanel)

### Contexto
O PRD fixa MySQL e proíbe PostgreSQL/SQLite. A fila de notificações da fase 9 usará
`SELECT ... FOR UPDATE SKIP LOCKED`, disponível a partir do MySQL 8.0.1.

### Decisão
Requisito mínimo **MySQL 8.0**. JSON nativo, colunas geradas (deduplicação de
incidentes) e CTEs são usados sem alternativa para versões antigas.

### Consequências
- Se o MySQL disponível no Easypanel for 5.7 ou MariaDB, a decisão precisa ser revisada
  antes da fase 9 (registrado como risco R-02 no diagnóstico).

---

## ADR-0006 — Rate limiting em memória na v1

**Data:** 03/11/2026
**Status:** Aceita

### Contexto
O PRD exige rate limiting (PRD §11, §17.2), mas proíbe adicionar infraestrutura sem
autorização — o Redis não faz parte da lista de serviços aprovada (PRD §8.2).

### Decisão
Limitador de janela deslizante em memória do processo, aplicado a `POST /auth/login`
(por IP e por e-mail) e às rotas de agente (por credencial), com auditoria de bloqueios.

### Consequências
- (+) Nenhuma dependência extra; funciona com uma réplica da API.
- (−) Não é compartilhado entre réplicas/processos. A API deve rodar com **1 worker**
  até que exista store compartilhado. Restrição documentada e verificável na configuração
  de deploy (`--workers 1`).
- A interface `RateLimiter` permite trocar o backend sem alterar as rotas.
