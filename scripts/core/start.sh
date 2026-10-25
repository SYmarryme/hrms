#!/usr/bin/env bash
# Foreground only; never kill existing unrelated processes or initialize an admin.
set -euo pipefail
umask 077
ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"
: "${HRMS_PUBLIC_ORIGIN:?Set the real HTTPS page origin, or loopback origin for local Ubuntu development}"
[[ -x var/core/venv/bin/python && -f frontend/node_modules/vite/bin/vite.js ]]
var/core/venv/bin/python - <<'PY'
import socket
from backend.database import Database
from backend.settings import Settings
Database(Settings.from_env().database_path).check_revision()
for port in (3000,8000):
    with socket.socket() as sock:
        sock.bind(('0.0.0.0', port))
PY
mkdir -p var/core
run_dir="$(mktemp -d "$ROOT/var/core/server.XXXXXXXX")"
backend_pid=''
frontend_pid=''
cleanup() {
  local rc=$?
  trap - EXIT INT TERM
  for pid in "$backend_pid" "$frontend_pid"; do
    if [[ -n "$pid" ]]; then kill "$pid" 2>/dev/null || true; fi
  done
  wait 2>/dev/null || true
  printf '%s\n' "$rc" > "$run_dir/exit-code.txt"
}
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM
unset PYTHONPATH PYTHONHOME __VITE_ADDITIONAL_SERVER_ALLOWED_HOSTS
var/core/venv/bin/python -m uvicorn backend.app:create_app --factory --host 127.0.0.1 --port 8000 \
  --workers 1 --no-proxy-headers --no-access-log > "$run_dir/backend.log" 2>&1 &
backend_pid=$!
node frontend/node_modules/vite/bin/vite.js --config frontend/vite.config.mjs > "$run_dir/frontend.log" 2>&1 &
frontend_pid=$!
printf 'HRMS services starting; private logs=%s. Ctrl+C stops this launch.\n' "$run_dir"
wait -n "$backend_pid" "$frontend_pid"
echo 'A service exited. Both services are being stopped; inspect private logs.' >&2
exit 1
