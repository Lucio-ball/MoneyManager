#!/bin/zsh
set -euo pipefail

# Usage:
#   ./scripts/health-check.sh [service_label] [port] [url]
#
# Parameters:
#   service_label  launchd service label, default: com.xigma.moneymanager
#   port           listen port to probe, default: 5000
#   url            http probe url, default: http://127.0.0.1:<port>/
#
# Examples:
#   ./scripts/health-check.sh
#   ./scripts/health-check.sh com.xigma.moneymanager 5000 http://127.0.0.1:5000/

SERVICE_LABEL="${1:-com.xigma.moneymanager}"
PORT="${2:-5000}"
URL="${3:-http://127.0.0.1:${PORT}/}"

DOMAIN="gui/$(id -u)"
SERVICE="${DOMAIN}/${SERVICE_LABEL}"

echo "[1/5] Service: ${SERVICE_LABEL}"
echo "[2/5] launchctl state"
launchctl print "${SERVICE}" | rg "state =|pid =|last exit code =|program =|MONEY_MANAGER_DB_PATH" || true

echo "\n[3/5] listener on :${PORT}"
lsof -nP -iTCP:"${PORT}" -sTCP:LISTEN || true

echo "\n[4/5] HTTP probe ${URL}"
HTTP_CODE="$(curl -s -o /dev/null -w '%{http_code}' "${URL}" || true)"
echo "HTTP ${HTTP_CODE}"

echo "\n[5/5] recent errors"
tail -n 120 "$HOME/Library/Logs/MoneyManager/stderr.log" | rg "ERROR|Traceback|OperationalError|Too many open files|subscription auto-sync failed" || echo "No recent matched errors"

if [[ "${HTTP_CODE}" == "200" ]]; then
  echo "\nResult: HEALTHY"
  exit 0
fi

echo "\nResult: UNHEALTHY"
exit 1
