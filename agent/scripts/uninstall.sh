#!/usr/bin/env bash
#
# VPS Guardian — remoção do agente.
#
#   sudo bash agent/scripts/uninstall.sh          # remove serviço e código, preserva config/logs
#   sudo bash agent/scripts/uninstall.sh --purge  # remove também config, logs, spool e usuário
#
set -euo pipefail

APP_USER="vps-guardian"
APP_DIR="/opt/vps-guardian"
CONF_DIR="/etc/vps-guardian"
STATE_DIR="/var/lib/vps-guardian"
LOG_DIR="/var/log/vps-guardian"
UNIT_FILE="/etc/systemd/system/guardian-agent.service"

PURGE=0
[[ "${1:-}" == "--purge" ]] && PURGE=1

[[ "$EUID" -eq 0 ]] || { echo "erro: execute como root" >&2; exit 1; }

if systemctl list-unit-files | grep -q '^guardian-agent.service'; then
    echo "[guardian] parando e desabilitando o serviço"
    systemctl disable --now guardian-agent.service || true
fi

rm -f "$UNIT_FILE"
systemctl daemon-reload
systemctl reset-failed guardian-agent.service 2>/dev/null || true

echo "[guardian] removendo código em $APP_DIR"
rm -rf "$APP_DIR"

if [[ "$PURGE" -eq 1 ]]; then
    echo "[guardian] removendo configuração, estado, logs e usuário"
    rm -rf "$CONF_DIR" "$STATE_DIR" "$LOG_DIR"
    if id -u "$APP_USER" >/dev/null 2>&1; then
        userdel "$APP_USER" 2>/dev/null || true
    fi
else
    echo "[guardian] config/logs preservados (use --purge para remover)"
fi

echo "[guardian] agente removido. Lembre-se de revogar a credencial no painel."
