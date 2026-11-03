# syntax=docker/dockerfile:1
# Imagem única para API e (futuramente) worker e job de migrations.
# Versão do Python fixada para corresponder ao pyproject.toml (>=3.12).
FROM python:3.12-slim-bookworm AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Usuário sem privilégios: a aplicação nunca roda como root (PRD §9.4).
RUN groupadd --system --gid 10001 guardian \
    && useradd --system --uid 10001 --gid guardian --no-create-home --shell /usr/sbin/nologin guardian

WORKDIR /app

COPY pyproject.toml ./
COPY app ./app
RUN pip install --no-cache-dir .

# Necessário apenas pelo serviço de migrations (mesma imagem, outro comando).
COPY alembic.ini ./
COPY alembic ./alembic

# Entrypoint: espera o MySQL e roda `alembic upgrade head` antes de iniciar.
# Permite subir a stack inteira com `docker compose up -d` e já ter o schema pronto.
COPY docker-entrypoint.sh /usr/local/bin/docker-entrypoint.sh
RUN chmod 0755 /usr/local/bin/docker-entrypoint.sh

USER guardian
EXPOSE 8000
ENTRYPOINT ["/usr/local/bin/docker-entrypoint.sh"]

# --workers 1: o rate limiting em memória exige instância única (ADR-0006).
# --proxy-headers: o TLS termina no Traefik do Easypanel.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1", "--proxy-headers", "--forwarded-allow-ips", "*", "--no-server-header"]
