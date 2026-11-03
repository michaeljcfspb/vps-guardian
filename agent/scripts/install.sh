#!/usr/bin/env bash
#
# VPS Guardian — instalador do agente (Ubuntu 22.04 / 24.04)
#
# LEIA ESTE ARQUIVO ANTES DE EXECUTAR. Ele foi escrito para ser auditável:
# não baixa nada da internet, não executa código remoto e não usa curl | bash.
#
# Uso:
#   sudo bash agent/scripts/install.sh \
#     --server-id <UUID do painel> \
#     --token <token de provisionamento> \
#     --api-url https://guardian.seudominio.com
#
# Opções:
#   --interval <segundos>   intervalo de coleta (padrão 30)
#   --source <diretório>    código do agente (padrão: pasta agent/ deste repositório)
#
# O que ele faz:
#   1. valida Python >= 3.10 e que está rodando como root;
#   2. cria usuário de sistema sem shell e os diretórios de estado/log;
#   3. instala o agente em /opt/vps-guardian com virtualenv próprio;
#   4. grava /etc/vps-guardian/agent.json com permissão 0600 (contém o token);
#   5. instala e habilita o serviço systemd endurecido;
#   6. o agente troca o token temporário pela credencial permanente no 1º start.
#
set -euo pipefail
IFS=$'\n\t'

APP_USER="vps-guardian"
APP_DIR="/opt/vps-guardian"
CONF_DIR="/etc/vps-guardian"
STATE_DIR="/var/lib/vps-guardian"
LOG_DIR="/var/log/vps-guardian"
UNIT_FILE="/etc/systemd/system/guardian-agent.service"

SERVER_ID=""
TOKEN=""
API_URL=""
INTERVAL="30"
SOURCE=""

die() { echo "erro: $*" >&2; exit 1; }
info() { echo "[guardian] $*"; }

usage() {
    sed -n '3,22p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        --server-id) SERVER_ID="${2:-}"; shift 2 ;;
        --token) TOKEN="${2:-}"; shift 2 ;;
        --api-url) API_URL="${2:-}"; shift 2 ;;
        --interval) INTERVAL="${2:-}"; shift 2 ;;
        --source) SOURCE="${2:-}"; shift 2 ;;
        -h|--help) usage; exit 0 ;;
        *) die "opção desconhecida: $1" ;;
    esac
done

[[ "$EUID" -eq 0 ]] || die "execute como root (sudo)"
[[ -n "$SERVER_ID" ]] || die "--server-id é obrigatório"
[[ -n "$TOKEN" ]] || die "--token é obrigatório"
[[ -n "$API_URL" ]] || die "--api-url é obrigatório"
[[ "$API_URL" == https://* ]] || die "--api-url deve começar com https://"
[[ "$INTERVAL" =~ ^[0-9]+$ ]] || die "--interval deve ser numérico"

if [[ -z "$SOURCE" ]]; then
    SOURCE="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
fi
[[ -f "$SOURCE/pyproject.toml" ]] || die "código do agente não encontrado em: $SOURCE"

command -v python3 >/dev/null 2>&1 || die "python3 não encontrado (apt install python3)"
python3 - <<'PY' || die "é necessário Python >= 3.10"
import sys
raise SystemExit(0 if sys.version_info >= (3, 10) else 1)
PY

info "Python: $(python3 --version)"

# --- usuário e diretórios ----------------------------------------------------
if ! id -u "$APP_USER" >/dev/null 2>&1; then
    info "criando usuário de sistema $APP_USER"
    useradd --system --no-create-home --shell /usr/sbin/nologin "$APP_USER"
fi

install -d -m 0755 "$APP_DIR"
install -d -m 0750 -o "$APP_USER" -g "$APP_USER" "$CONF_DIR" "$STATE_DIR" "$STATE_DIR/spool" "$LOG_DIR"

# --- código e virtualenv -----------------------------------------------------
info "instalando código em $APP_DIR/agent"
rm -rf "$APP_DIR/agent.new"
cp -a "$SOURCE" "$APP_DIR/agent.new"
rm -rf "$APP_DIR/agent"
mv "$APP_DIR/agent.new" "$APP_DIR/agent"

info "criando virtualenv"
python3 -m venv "$APP_DIR/venv"
"$APP_DIR/venv/bin/pip" install --quiet --upgrade pip
"$APP_DIR/venv/bin/pip" install --quiet "$APP_DIR/agent"

# --- configuração (0600, dono do serviço) ------------------------------------
info "gravando $CONF_DIR/agent.json (permissão 0600)"
python3 - "$SERVER_ID" "$TOKEN" "$API_URL" "$INTERVAL" "$CONF_DIR/agent.json" <<'PY'
import json
import os
import sys
import tempfile

server_id, token, api_url, interval, path = sys.argv[1:6]
config = {
    "api_url": api_url.rstrip("/"),
    "server_id": server_id,
    "provisioning_token": token,
    "credential": None,
    "interval_seconds": int(interval),
    "request_timeout_seconds": 10,
    "verify_tls": True,
    "spool_dir": "/var/lib/vps-guardian/spool",
    "state_file": "/var/lib/vps-guardian/state.json",
    "log_file": "/var/log/vps-guardian/agent.log",
    "log_level": "INFO",
}
directory = os.path.dirname(path)
descriptor, temporary = tempfile.mkstemp(dir=directory, prefix=".tmp-")
with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
    json.dump(config, handle, indent=2)
    handle.write("\n")
os.chmod(temporary, 0o600)
os.replace(temporary, path)
PY
chown "$APP_USER:$APP_USER" "$CONF_DIR/agent.json"
chmod 0600 "$CONF_DIR/agent.json"

# --- serviço systemd ---------------------------------------------------------
info "instalando unidade systemd"
install -m 0644 "$APP_DIR/agent/packaging/systemd/guardian-agent.service" "$UNIT_FILE"
systemctl daemon-reload
systemctl enable --now guardian-agent.service

info "aguardando o primeiro ciclo..."
sleep 8

if systemctl is-active --quiet guardian-agent.service; then
    info "agente ativo"
else
    echo "--- últimas linhas do journal ---" >&2
    journalctl -u guardian-agent.service -n 40 --no-pager >&2 || true
    die "o serviço não está ativo; verifique o log acima"
fi

# --- verificação -------------------------------------------------------------
info "teste de coleta local (sem enviar):"
sudo -u "$APP_USER" "$APP_DIR/venv/bin/guardian-agent" \
    --config "$CONF_DIR/agent.json" --dry-run | head -n 25 || true

echo
info "instalação concluída."
cat <<'EOT'

Próximos passos:
  systemctl status guardian-agent
  journalctl -u guardian-agent -f
  tail -f /var/log/vps-guardian/agent.log

Verifique no painel se o servidor mudou para "online" em até 1 minuto.
Para remover: sudo bash agent/scripts/uninstall.sh [--purge]
EOT
