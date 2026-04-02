#!/bin/zsh
set -euo pipefail

# Usage:
#   ./scripts/restart-service.sh [service_label] [plist_path] [port] [url] [mode]
#
# Parameters:
#   service_label  launchd service label, default: com.xigma.moneymanager
#   plist_path     launch agent plist path, default: ~/Library/LaunchAgents/<service_label>.plist
#   port           listen port to probe, default: 5000
#   url            http probe url, default: http://127.0.0.1:<port>/
#   mode           restart mode: smart | full, default: smart
#                  smart: if service exists, kickstart only; otherwise bootstrap + kickstart
#                  full:  always bootout + bootstrap + kickstart
#
# Examples:
#   ./scripts/restart-service.sh
#   ./scripts/restart-service.sh com.xigma.moneymanager ~/Library/LaunchAgents/com.xigma.moneymanager.plist 5000 http://127.0.0.1:5000/ full

SERVICE_LABEL="${1:-com.xigma.moneymanager}"
PLIST_PATH="${2:-$HOME/Library/LaunchAgents/${SERVICE_LABEL}.plist}"
PORT="${3:-5000}"
URL="${4:-http://127.0.0.1:${PORT}/}"
MODE="${5:-smart}"

DOMAIN="gui/$(id -u)"
SERVICE="${DOMAIN}/${SERVICE_LABEL}"

echo "[1/4] restart service: ${SERVICE_LABEL} (mode=${MODE})"
if [[ "${MODE}" == "full" ]]; then
  launchctl bootout "${SERVICE}" 2>/dev/null || true
  launchctl bootstrap "${DOMAIN}" "${PLIST_PATH}"
  launchctl enable "${SERVICE}"
  launchctl kickstart -k "${SERVICE}"
else
  if launchctl print "${SERVICE}" >/dev/null 2>&1; then
    launchctl kickstart -k "${SERVICE}"
  else
    launchctl bootstrap "${DOMAIN}" "${PLIST_PATH}"
    launchctl enable "${SERVICE}"
    launchctl kickstart -k "${SERVICE}"
  fi
fi

echo "\n[2/4] wait for startup"
sleep 1

echo "\n[3/4] status"
launchctl print "${SERVICE}" | rg "state =|pid =|last exit code =|program =|MONEY_MANAGER_DB_PATH" || true

echo "\n[4/4] HTTP probe ${URL}"
HTTP_CODE="$(curl -s -o /dev/null -w '%{http_code}' "${URL}" || true)"
echo "HTTP ${HTTP_CODE}"

if [[ "${HTTP_CODE}" == "200" ]]; then
  echo "\nResult: RESTART OK"
  exit 0
fi

echo "\nResult: RESTART FAILED"
exit 1
