#!/bin/sh
# Entrypoint da central: espera o MySQL e aplica as migrations antes de subir a API.
#
# Controlado por GUARDIAN_AUTO_MIGRATE (padrão: true). Defina "false" quando as
# migrations forem executadas por um job separado ou por outro serviço.
set -eu

if [ "${GUARDIAN_AUTO_MIGRATE:-true}" = "true" ]; then
    WAIT_TIMEOUT="${GUARDIAN_DB_WAIT_TIMEOUT:-180}"
    echo "guardian: aguardando MySQL (timeout ${WAIT_TIMEOUT}s)..."
    python -m app.cli wait-db --timeout "${WAIT_TIMEOUT}"
    echo "guardian: aplicando migrations (alembic upgrade head)..."
    alembic upgrade head
    echo "guardian: schema atualizado; iniciando aplicação."
fi

exec "$@"
