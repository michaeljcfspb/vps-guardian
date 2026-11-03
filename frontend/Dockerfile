# syntax=docker/dockerfile:1
#
# IMPORTANTE: o contexto de build é a RAIZ do repositório (igual ao Dockerfile da API).
#   docker build -t vps-guardian/frontend:0.1.0 -f frontend/Dockerfile .
# No Easypanel: Build Path = frontend (localiza este arquivo) e contexto = raiz.
FROM node:22-alpine AS build
WORKDIR /app

# Mesma versão usada para gerar o pnpm-lock.yaml (lockfile 9.0).
RUN npm i -g pnpm@11.28.5

COPY frontend/package.json frontend/pnpm-lock.yaml frontend/pnpm-workspace.yaml ./
RUN pnpm install --frozen-lockfile

COPY frontend/ ./

# Vazio = mesma origem (o nginx faz proxy de /api para API_UPSTREAM).
ARG VITE_API_BASE_URL=""
ENV VITE_API_BASE_URL=$VITE_API_BASE_URL
RUN pnpm build

FROM nginx:1.29-alpine AS runtime

# Destino interno de /api. Pode ser definido como build-arg (Easypanel) ou como
# variável de ambiente em runtime; o template é processado por envsubst no start.
ARG API_UPSTREAM=http://api:8000
ENV API_UPSTREAM=${API_UPSTREAM}

COPY frontend/nginx.conf.template /etc/nginx/templates/default.conf.template
COPY --from=build /app/dist /usr/share/nginx/html

EXPOSE 80
HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
    CMD wget -q -O /dev/null http://127.0.0.1/ || exit 1
