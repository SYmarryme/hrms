#!/usr/bin/env bash
# Ubuntu only. Temp databases, test reports and logs stay in ignored var/.
set -euo pipefail
umask 077
ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"
mkdir -p var/core
run_dir="$(mktemp -d "$ROOT/var/core/tests.XXXXXXXX")"
exec > >(tee "$run_dir/tests.log") 2>&1
trap 'rc=$?; printf "%s\n" "$rc" > "$run_dir/exit-code.txt"; printf "CORE_TEST_EXIT_CODE=%s; artifacts=%s\n" "$rc" "$run_dir"' EXIT
export PYTHONDONTWRITEBYTECODE=1
PYTHONPATH="$ROOT" var/core/venv/bin/python -m pytest backend/tests -q --tb=short \
  --basetemp "$run_dir/tmp" --junitxml "$run_dir/backend-junit.xml"
npm --prefix frontend test
npm --prefix frontend run typecheck
npm --prefix frontend run build
