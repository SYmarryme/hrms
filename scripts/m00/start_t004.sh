#!/usr/bin/env bash
# Foreground only: Ctrl+C stops only this invocation's two child processes.
set -euo pipefail
umask 077
ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"
if [[ -n "$(git status --porcelain --untracked-files=all -- experiments/t004 scripts/m00 requirements/m00-bootstrap.lock)" ]]; then
  echo 'Relevant source has local changes; synchronize the reviewed commit before launch' >&2
  exit 1
fi
env_dir="$(realpath -e -- "${1:?usage: start_t004.sh ENV_DIR HTTPS_ORIGIN}")"
case "$env_dir" in "$ROOT"/var/m00/t004-env.*) ;; *) echo 'Invalid experiment environment' >&2; exit 1;; esac
[[ "$(cat "$env_dir/setup-exit-code.txt")" == 0 ]]
[[ "$(cat "$env_dir/commit.txt")" == "$(git rev-parse HEAD)" ]] || { echo 'Source changed; create a new T-004 environment' >&2; exit 1; }
for source in package.json index.html vite.config.mjs src/main.ts; do
  [[ "$(git hash-object "$env_dir/frontend/$source")" == "$(git rev-parse "HEAD:experiments/t004/frontend/$source")" ]] || { echo 'Copied frontend source changed; create a new environment' >&2; exit 1; }
done
export T004_PUBLIC_ORIGIN="${2:?bare HTTPS origin required}"
export T004_COMMIT="$(git rev-parse HEAD)"
run_dir="$(mktemp -d "$ROOT/var/m00/t004-server.XXXXXXXX")"
exec > >(tee "$run_dir/start.log") 2>&1
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
"$env_dir/venv/bin/python" -I - <<'PY'
import socket
for port in (3000, 8000):
    with socket.socket() as sock:
        sock.bind(('0.0.0.0', port))
print('PORTS_FREE: 3000,8000')
PY
unset PYTHONPATH PYTHONHOME __VITE_ADDITIONAL_SERVER_ALLOWED_HOSTS
"$env_dir/venv/bin/python" -m uvicorn backend:app --app-dir "$ROOT/experiments/t004" \
  --host 127.0.0.1 --port 8000 --no-proxy-headers --no-access-log > "$run_dir/backend.log" 2>&1 &
backend_pid=$!
node "$env_dir/frontend/node_modules/vite/bin/vite.js" --config "$env_dir/frontend/vite.config.mjs" \
  > "$run_dir/frontend.log" 2>&1 &
frontend_pid=$!
printf 'T004_SERVER_LOG_DIR=%s\n' "$run_dir"
sleep 2
kill -0 "$backend_pid" "$frontend_pid"
ss -ltn '( sport = :8000 or sport = :3000 )' | tee "$run_dir/listeners.txt"
printf 'Processes started; readiness must be verified with t004_probe.py. Ctrl+C stops them.\n'
wait -n "$backend_pid" "$frontend_pid"
echo 'A server exited; both are being stopped. Inspect logs.' >&2
exit 1
