# syntax=docker/dockerfile:1
#
# Imagem da central (API e, no futuro, worker e job de migrations).
#
# IMPORTANTE: o contexto de build é a RAIZ do repositório.
#   docker build -t vps-guardian/api:0.1.0 .
# No Easypanel: Build Path = / (vazio) e Dockerfile = Dockerfile.
#
# Uma única imagem atende API, worker e migrations — o comando é que muda.
FROM python:3.12-slim-bookworm AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Usuário sem privilégios: a aplicação nunca roda como root (PRD §9.4).
RUN groupadd --system --gid 10001 guardian \
    && useradd --system --uid 10001 --gid guardian --no-create-home --shell /usr/sbin/nologin guardian

WORKDIR /app

COPY backend/pyproject.toml ./
COPY backend/app ./app
RUN pip install --no-cache-dir .

# Necessário pelo serviço de migrations e pelo entrypoint (mesma imagem).
COPY backend/alembic.ini ./
COPY backend/alembic ./alembic
COPY backend/docker-entrypoint.sh /usr/local/bin/docker-entrypoint.sh
RUN chmod 0755 /usr/local/bin/docker-entrypoint.sh

USER guardian
EXPOSE 8000

# Entrypoint: espera o MySQL e roda `alembic upgrade head` antes de iniciar.
ENTRYPOINT ["/usr/local/bin/docker-entrypoint.sh"]

# --workers 1: o rate limiting em memória exige instância única (ADR-0006).
# --proxy-headers: o TLS termina no proxy do Easypanel.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1", "--proxy-headers", "--forwarded-allow-ips", "*", "--no-server-header"]
