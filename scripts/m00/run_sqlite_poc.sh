#!/usr/bin/env bash
set -euo pipefail
umask 077
ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"
mkdir -p var/m00
run_dir="$(mktemp -d "$ROOT/var/m00/poc.XXXXXXXX")"
exec > >(tee "$run_dir/poc.log") 2>&1
trap 'rc=$?; printf "%s\n" "$rc" > "$run_dir/exit-code.txt"' EXIT
printf 'UTC=%s\n' "$(date -u +%FT%TZ)"
git rev-parse HEAD
python3 scripts/m00/env_probe.py
df -T "$run_dir"
set +e
PYTHONPATH="$ROOT/scripts/m00${PYTHONPATH:+:$PYTHONPATH}" \
  python3 -m pytest -v -s scripts/m00/poc/test_sqlite.py \
  --basetemp "$run_dir/cases" --junitxml="$run_dir/junit.xml"
rc=$?
set -e
printf '%s\n' "$rc" > "$run_dir/exit-code.txt"
printf '\nPOC_EXIT_CODE=%s; artifacts=%s\n' "$rc" "$run_dir"
exit "$rc"
