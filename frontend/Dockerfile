# syntax=docker/dockerfile:1
FROM node:22-alpine AS build
WORKDIR /app

# Mesma versão usada para gerar o pnpm-lock.yaml (lockfile 9.0).
RUN npm i -g pnpm@11.28.5

COPY package.json pnpm-lock.yaml pnpm-workspace.yaml ./
RUN pnpm install --frozen-lockfile

COPY . .
# Vazio = mesma origem (o nginx faz proxy de /api para a API).
ARG VITE_API_BASE_URL=""
ENV VITE_API_BASE_URL=$VITE_API_BASE_URL
RUN pnpm build

FROM nginx:1.29-alpine AS runtime

# Template processado por envsubst no start: API_UPSTREAM define o destino de /api.
ENV API_UPSTREAM=http://api:8000
COPY nginx.conf.template /etc/nginx/templates/default.conf.template
COPY --from=build /app/dist /usr/share/nginx/html

EXPOSE 80
HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
    CMD wget -q -O /dev/null http://127.0.0.1/ || exit 1
