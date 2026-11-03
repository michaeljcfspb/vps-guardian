# Deploy da central — Easypanel + MySQL

Guia operacional da **fase 2/3** (fundação + cadastro de servidores). Cobre o que já
existe no repositório; itens de fases futuras estão marcados como tal.

> **Regra de ouro:** nenhum segredo em arquivo versionado. Senhas, `GUARDIAN_SECRET_KEY`
> e tokens vivem no gerenciador de segredos do Easypanel ou em `.env` local não versionado.

## 1. Pré-requisitos

| Item | Requisito |
|---|---|
| MySQL | **8.0+** (JSON nativo, colunas geradas, `SKIP LOCKED` futuro) |
| Acesso ao MySQL | rede privada interna; **porta 3306 nunca publicada** |
| Domínio | apontando para o proxy do Easypanel, com TLS (Let's Encrypt) |
| Docker | host da central com Docker/Compose (o Easypanel já fornece) |

## 2. Banco de dados

Execute como administrador do MySQL (não como usuário da aplicação):

```bash
mysql -h <host-interno> -u root -p < deploy/mysql/bootstrap.sql
```

Antes de executar, troque `TROCAR_POR_SENHA_FORTE` no arquivo por uma senha forte.
Guarde a senha no gerenciador de segredos do Easypanel — ela será usada apenas em
`GUARDIAN_DATABASE_URL`.

Verificações que devem aparecer na saída:

- `mysql_version` ≥ 8.0;
- `charset = utf8mb4`;
- `SHOW GRANTS` sem privilégios globais (sem `SUPER`, `FILE`, `GRANT OPTION`).

### Banco de testes (opcional, recomendado)

Crie também `vps_guardian_test` com o mesmo usuário e defina
`GUARDIAN_TEST_DATABASE_URL` no ambiente de CI/VPS. Sem essa variável, os testes de
integração são *skipped* (nunca aprovados por omissão — ADR-0001).

## 3. Variáveis de ambiente

Copie `.env.example` (raiz do repositório) para `deploy/.env` **no servidor** e ajuste:

| Variável | Obrigatória | Observação |
|---|---|---|
| `GUARDIAN_SECRET_KEY` | sim | gere com `python -c "import secrets;print(secrets.token_urlsafe(48))"` |
| `GUARDIAN_DATABASE_URL` | sim | `mysql+pymysql://guardian:SENHA@host-interno:3306/vps_guardian` |
| `GUARDIAN_APP_ENV` | sim | `production` |
| `GUARDIAN_PUBLIC_BASE_URL` | recomendado | `https://guardian.seudominio.com` |
| `GUARDIAN_TRUSTED_PROXY_IPS` | recomendado | IP do proxy/Traefik (para auditoria de IP real) |
| `GUARDIAN_CORS_ORIGINS` | se SPA em outro domínio | sem barra final |

`GUARDIAN_SECRET_KEY` trocada invalida todas as sessões ativas.

## 4. Publicar a aplicação

```bash
cd deploy
docker compose build
docker compose run --rm migrations      # aplica o schema (alembic upgrade head)
docker compose up -d api
```

Verificações:

```bash
curl -fsS https://guardian.seudominio.com/health
curl -fsS https://guardian.seudominio.com/health/ready
```

`/health/ready` deve retornar `status=ready` e `schema_revision=0001_initial`.
Se retornar 503, o MySQL não está acessível pela rede privada.

### Criar o administrador inicial

```bash
docker compose run --rm api python -m app.cli create-admin \
  --email admin@seudominio.com --name "Administrador"
```

A senha é solicitada interativamente (mínimo 12 caracteres) ou lida de
`GUARDIAN_ADMIN_PASSWORD` em automação. Ela nunca é passada por argumento de linha de
comando.

## 5. Primeiros passos pela API

```bash
# 1) login (guarda cookies de sessão e CSRF)
curl -c cookies.txt -X POST https://guardian.seudominio.com/api/v1/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"email":"admin@seudominio.com","password":"SUA_SENHA"}'

CSRF=$(grep guardian_csrf cookies.txt | awk '{print $7}')

# 2) cadastrar um servidor
curl -b cookies.txt -X POST https://guardian.seudominio.com/api/v1/servers \
  -H "X-CSRF-Token: $CSRF" -H 'Content-Type: application/json' \
  -d '{"name":"VPS-01","ip_address":"203.0.113.10","panel":"easypanel","environment":"production"}'

# 3) emitir token de provisionamento (exibido uma única vez)
curl -b cookies.txt -X POST \
  https://guardian.seudominio.com/api/v1/servers/<SERVER_ID>/provisioning-token \
  -H "X-CSRF-Token: $CSRF"
```

O token de provisionamento expira em 15 minutos e é de uso único. A troca por credencial
individual é feita por `POST /api/v1/agent/register` (implementado e testado).

## 6. Backup e restauração

Ainda **não automatizado** (fase 11). Procedimento mínimo esperado:

```bash
# backup cifrado (exemplo; ajuste credenciais por variável de ambiente)
mysqldump --single-transaction --routines --triggers \
  -h <host> -u guardian -p vps_guardian | gzip | \
  openssl enc -aes-256-cbc -salt -pbkdf2 -out backup-$(date +%F).sql.gz.enc

# restauração (testar em banco separado, nunca em produção)
openssl enc -d -aes-256-cbc -pbkdf2 -in backup.sql.gz.enc | gunzip | mysql -h <host> -u root -p vps_guardian_restore
```

O teste real de restauração é critério de aceite da fase 11 e será registrado no
relatório daquela fase.

## 7. Rollback

- **Código:** `docker compose up -d api` com a tag de imagem anterior
  (`vps-guardian/api:<versão>`).
- **Schema:** `alembic downgrade -1` dentro do serviço `migrations`. Use apenas se a
  versão anterior do código for compatível — migrations destrutivas exigem backup
  prévio.

## 8. Solução de problemas

| Sintoma | Causa provável | Ação |
|---|---|---|
| `/health/ready` = 503 | MySQL inacessível/rede privada | testar `mysql -h <host>` do container da API |
| `schema_revision` nulo | migrations não aplicadas | `docker compose run --rm migrations` |
| 403 em rotas de escrita | header `X-CSRF-Token` ausente | reenviar valor do cookie `guardian_csrf` |
| 429 no login | rate limit (5 tentativas / 5 min) | aguardar a janela ou reiniciar a API |
| container reinicia em loop | variável obrigatória ausente | `docker compose logs api` |

Logs são JSON estruturado com `request_id`; segredos são redigidos automaticamente.
