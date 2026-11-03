# Deploy da central — Easypanel + MySQL

Dois modos de instalação. Escolha **um**:

| Modo | Quando usar | Arquivo |
|---|---|---|
| **A. Stack completo** (recomendado para começar) | a VPS não tem MySQL, ou você quer o banco no mesmo compose | `docker-compose.yml` |
| **B. MySQL do Easypanel** | já existe um serviço MySQL gerenciado, com backup próprio | `docker-compose.external-db.yml` |

Em ambos, os segredos vivem apenas no `.env` do servidor — nunca no Git.

---

## 0. Antes de tudo: qual tipo de serviço no Easypanel?

O Easypanel oferece dois jeitos de publicar a aplicação. A escolha muda **onde** o
Dockerfile e o banco ficam:

### 0.1 Serviço do tipo "Compose" (recomendado para o modo A)

1. No Easypanel: **Create Service → Compose**.
2. Cole o conteúdo de `docker-compose.yml` (raiz do repositório).
3. Em **Environment**, cole as variáveis do `.env` (seção 2 abaixo). O Easypanel
   injeta essas variáveis no processo do compose, então `${MYSQL_ROOT_PASSWORD}` e
   `env_file: .env` funcionam.
4. Deploy. O Easypanel constrói `api` e `mysql` e sobe a stack inteira.

Se o seu Easypanel **não** cria o arquivo `.env`, use o modo B (0.2) — ele não depende
de arquivo de ambiente, só de variáveis no painel.

### 0.2 Serviço do tipo "App" (Dockerfile) — modo B

1. No Easypanel: **Create Service → App**.
2. **Source:** repositório `michaeljcfspb/vps-guardian`, branch `main`.
3. **Build:**
   - **Build Path / Root Directory:** deixe **vazio** (raiz do repositório) — o
     `Dockerfile` agora está na raiz.
   - **Dockerfile:** `Dockerfile`.
4. **Port:** `8000` (porta interna da API).
5. **Environment:** variáveis da seção 2, com `GUARDIAN_DATABASE_URL` ou
   `GUARDIAN_DB_*` apontando para o MySQL do Easypanel (serviço **MySQL** criado
   separadamente, na mesma rede privada).
6. **Deploy**.

> **Erro `failed to read dockerfile: open Dockerfile: no such file or directory`**
> O EasyPanel usa por padrão o `Dockerfile` na raiz do repositório. Até o commit
> anterior, o arquivo ficava em `backend/Dockerfile`. Agora ele está na **raiz**:
> configure Build Path vazio e Dockerfile `Dockerfile`. Se você já criou o serviço
> apontando para `backend`, mude o Build Path para vazio (ou recrie o serviço).

---

## 1. Pré-requisitos

| Item | Requisito |
|---|---|
| Docker | 24+ com Compose v2 |
| MySQL | 8.0+ (o modo A já sobe a versão 8.0) |
| Domínio | apontando para o proxy do Easypanel (para TLS) |
| Portas | apenas 80/443 públicas; **3306 nunca exposta** |

---

## 2. Modo A — stack completo (sobe o MySQL junto)

### 2.1 Preparar o ambiente

```bash
git clone https://github.com/michaeljcfspb/vps-guardian.git
cd vps-guardian
cp .env.example .env
```

Gere os segredos:

```bash
python3 -c "import secrets; print(secrets.token_urlsafe(48))"   # GUARDIAN_SECRET_KEY
python3 -c "import secrets; print(secrets.token_urlsafe(24))"   # GUARDIAN_DB_PASSWORD
python3 -c "import secrets; print(secrets.token_urlsafe(24))"   # MYSQL_ROOT_PASSWORD
```

Edite o `.env` e preencha os quatro valores obrigatórios:

| Variável | O que é |
|---|---|
| `GUARDIAN_SECRET_KEY` | chave de sessão/criptografia (≥ 32 caracteres) |
| `MYSQL_ROOT_PASSWORD` | senha do root do MySQL (interna ao container) |
| `GUARDIAN_DB_PASSWORD` | senha do usuário da aplicação (diferente da root) |
| `GUARDIAN_PUBLIC_BASE_URL` | `https://guardian.seudominio.com` (opcional, mas recomendado) |

`GUARDIAN_DB_NAME` e `GUARDIAN_DB_USER` já vêm prontos (`vps_guardian` / `guardian`).

### 2.2 Subir tudo

```bash
docker compose up -d --build
```

A sequência é automática:

1. `mysql` inicia (InnoDB, `utf8mb4`) e passa no healthcheck;
2. `api` espera o banco responder (`app.cli wait-db`);
3. `api` executa `alembic upgrade head` (cria as 7 tabelas);
4. só então o Uvicorn começa a aceitar conexões.

Acompanhe:

```bash
docker compose ps
docker compose logs -f api
```

Procure por `guardian: schema atualizado; iniciando aplicação.`

### 2.3 Verificar

```bash
curl -fsS http://127.0.0.1:8000/health          # via túnel local ou pelo proxy
curl -fsS https://guardian.seudominio.com/health/ready
```

`/health/ready` deve retornar `"status":"ready"` e `"schema_revision":"0001_initial"`.

### 2.4 Criar o administrador

```bash
docker compose exec api python -m app.cli create-admin \
  --email admin@seudominio.com --name "Administrador"
```

A senha é digitada no terminal (mínimo 12 caracteres). Em automação, defina
`GUARDIAN_ADMIN_PASSWORD` antes do comando — nunca passe a senha como argumento.

### 2.5 Onde ficam os dados

- Banco: volume Docker `vps-guardian_mysql_data`;
- Nada sensível no repositório.

```bash
docker compose exec mysql \
  mysql -u root -p"$MYSQL_ROOT_PASSWORD" -e "SHOW TABLES FROM vps_guardian;"
```

### 2.6 Expor a API com TLS

No Easypanel, crie o domínio apontando para a porta interna **8000** do serviço `api`
(o container publica apenas em `expose`, não em portas do host). O TLS é terminado pelo
proxy do Easypanel (Let's Encrypt).

Depois de definir o domínio, preencha no `.env`:

```
GUARDIAN_PUBLIC_BASE_URL=https://guardian.seudominio.com
GUARDIAN_TRUSTED_PROXY_IPS=<IP interno do proxy>
GUARDIAN_CORS_ORIGINS=https://guardian.seudominio.com   # só se o painel for outro host
```

`GUARDIAN_TRUSTED_PROXY_IPS` é o que faz a auditoria registrar o IP real do cliente em
vez do IP do proxy.

---

## 3. Modo B — MySQL já existente no Easypanel

### 3.1 Criar banco e usuário

```bash
mysql -h <host-interno> -u root -p < deploy/mysql/bootstrap.sql
```

Antes, troque `TROCAR_POR_SENHA_FORTE` no arquivo. A saída deve mostrar MySQL ≥ 8.0 e
`SHOW GRANTS` sem privilégios globais.

### 3.2 Apontar a aplicação

No `.env`, ajuste o bloco de conexão:

```
GUARDIAN_DB_HOST=<host-interno-do-mysql>
GUARDIAN_DB_PORT=3306
GUARDIAN_DB_NAME=vps_guardian
GUARDIAN_DB_USER=guardian
GUARDIAN_DB_PASSWORD=<senha-definida-no-bootstrap>
```

### 3.3 Subir

```bash
docker compose -f docker-compose.external-db.yml up -d --build
```

Migrations continuam automáticas no boot da API.

---

## 4. Primeiros passos pela API

```bash
# login (guarda cookie de sessão e cookie CSRF)
curl -c cookies.txt -X POST https://guardian.seudominio.com/api/v1/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"email":"admin@seudominio.com","password":"SUA_SENHA"}'

CSRF=$(grep guardian_csrf cookies.txt | awk '{print $7}')

# cadastrar servidor
curl -b cookies.txt -X POST https://guardian.seudominio.com/api/v1/servers \
  -H "X-CSRF-Token: $CSRF" -H 'Content-Type: application/json' \
  -d '{"name":"VPS-01","ip_address":"203.0.113.10","panel":"easypanel","environment":"production"}'

# emitir token de provisionamento (exibido uma única vez, vale 15 min)
curl -b cookies.txt -X POST \
  https://guardian.seudominio.com/api/v1/servers/<SERVER_ID>/provisioning-token \
  -H "X-CSRF-Token: $CSRF"
```

---

## 5. Backup e restauração

Ainda **não automatizado** (fase 11). Procedimento mínimo:

```bash
# modo A: dump de dentro do container (sem expor porta)
docker compose exec mysql sh -c \
  'exec mysqldump --single-transaction --routines --triggers -u root -p"$MYSQL_ROOT_PASSWORD" vps_guardian' \
  | gzip > backup-$(date +%F).sql.gz

# cifrar o arquivo antes de sair do servidor
openssl enc -aes-256-cbc -salt -pbkdf2 -in backup-$(date +%F).sql.gz \
  -out backup-$(date +%F).sql.gz.enc

# teste de restauração (banco separado, nunca em produção)
gunzip -c backup-2026-11-03.sql.gz | docker compose exec -T mysql \
  sh -c 'exec mysql -u root -p"$MYSQL_ROOT_PASSWORD" vps_guardian_restore'
```

---

## 6. Operação e rollback

| Ação | Comando |
|---|---|
| Ver estado | `docker compose ps` |
| Logs da API | `docker compose logs -f api` |
| Reiniciar API | `docker compose restart api` |
| Aplicar migrations manualmente | `docker compose run --rm migrations` |
| Parar tudo (mantém dados) | `docker compose down` |
| Recriar schema do zero | `docker compose down -v` (⚠ apaga o banco) |

**Rollback de código:** `docker compose up -d` com a tag de imagem anterior
(`vps-guardian/api:<versão>`).
**Rollback de schema:** `docker compose run --rm migrations alembic downgrade -1`
(somente com backup e compatibilidade de código garantida).

---

## 7. Solução de problemas

| Sintoma | Causa provável | Ação |
|---|---|---|
| `GUARDIAN_SECRET_KEY: obrigatório e não definido` | variável não configurada no painel | adicionar em Environment, mínimo 32 caracteres |
| `defina MYSQL_ROOT_PASSWORD no .env` | `.env` ausente/incompleto | `cp .env.example .env` e preencher |
| `api` reinicia em loop | MySQL não subiu | `docker compose logs mysql` |
| `/health/ready` = 503 | banco inacessível | conferir `GUARDIAN_DB_*` e a rede |
| `schema_revision` nulo | migration não aplicada | `docker compose run --rm migrations` |
| 403 em rotas de escrita | header `X-CSRF-Token` ausente | reenviar o valor do cookie `guardian_csrf` |
| 429 no login | rate limit (5 tentativas / 5 min) | aguardar a janela |
| `Cannot connect to Docker daemon` | Docker parado | iniciar Docker/Easypanel |

Logs da aplicação são JSON com `request_id`; segredos são redigidos automaticamente.
