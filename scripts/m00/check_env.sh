#!/usr/bin/env bash
set -uo pipefail
umask 077
ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd)" || exit 1
cd "$ROOT" || exit 1
mkdir -p "$ROOT/var/m00" || exit 1
run_dir="$(mktemp -d "$ROOT/var/m00/env.XXXXXXXX")" || exit 1
exec > >(tee "$run_dir/environment.log") 2>&1
failed=0
check() {
  local label="$1"; shift
  printf '\n[%s]\n' "$label"
  "$@"
  local rc=$?
  printf 'exit_code=%s\n' "$rc"
  if (( rc != 0 )); then failed=1; fi
}
printf 'UTC=%s\n' "$(date -u +%FT%TZ)"
check git_commit git rev-parse HEAD
check os cat /etc/os-release
check architecture uname -m
check ubuntu bash -c '. /etc/os-release; [[ "$ID" == ubuntu ]]'
check python python3 --version
check pip python3 -m pip --version
check python_sqlite_packages python3 scripts/m00/env_probe.py
check node node --version
check npm npm --version
check sqlite_cli sqlite3 --version
check alembic python3 -m alembic --version
check pytest python3 -m pytest --version
check filesystem df -T "$run_dir"
printf '\nENV_EXIT_CODE=%s\n' "$failed"
printf '%s\n' "$failed" > "$run_dir/exit-code.txt"
exit "$failed"
