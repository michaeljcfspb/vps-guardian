#!/bin/sh
# Entrypoint da central: espera o MySQL e aplica as migrations antes de subir a API.
#
# Controlado por GUARDIAN_AUTO_MIGRATE (padrão: true). Defina "false" quando as
# migrations forem executadas por um job separado ou por outro serviço.
set -eu

if [ "${GUARDIAN_AUTO_MIGRATE:-true}" = "true" ]; then
    WAIT_TIMEOUT="${GUARDIAN_DB_WAIT_TIMEOUT:-180}"

    echo "guardian: validando configuração e aguardando MySQL (timeout ${WAIT_TIMEOUT}s)..."
    if ! python -m app.cli wait-db --timeout "${WAIT_TIMEOUT}"; then
        echo "guardian: NÃO foi possível conectar ao MySQL. Verifique GUARDIAN_DB_HOST/PORT/NAME/USER/PASSWORD (ou GUARDIAN_DATABASE_URL) e se o banco está acessível pela rede interna." >&2
        exit 1
    fi

    echo "guardian: aplicando migrations (alembic upgrade head)..."
    if ! alembic upgrade head; then
        echo "guardian: falha ao aplicar migrations. O schema não foi atualizado." >&2
        exit 1
    fi
    echo "guardian: schema atualizado; iniciando aplicação."
fi

exec "$@"
