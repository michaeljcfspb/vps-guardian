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

### Decisões

- ADR-0001: desenvolvimento code-first; validação funcional na VPS.
- ADR-0002: ROADMAP prevalece sobre o PRD na ordem de execução.
- ADR-0003: sessão opaca em banco com cookie `HttpOnly` e CSRF double-submit.
- ADR-0004: credenciais de agente e de provisionamento armazenadas apenas como hash.
