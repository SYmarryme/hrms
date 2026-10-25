#!/usr/bin/env bash
set -euo pipefail
umask 077
ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"
mkdir -p var/core
run_dir="$(mktemp -d "$ROOT/var/core/install.XXXXXXXX")"
exec > >(tee "$run_dir/install.log") 2>&1
trap 'rc=$?; printf "%s\n" "$rc" > "$run_dir/exit-code.txt"; printf "CORE_SETUP_EXIT_CODE=%s; artifacts=%s\n" "$rc" "$run_dir"' EXIT
base_python="${HRMS_BASE_PYTHON:-python3}"
"$base_python" -c 'import sys; assert sys.version_info >= (3,11), "Python >=3.11 required"'
node -e 'const [a,b]=process.versions.node.split(".").map(Number); if(!((a===20&&b>=19)||(a===22&&b>=12)||a>22))process.exit(1)'
if [[ ! -x var/core/venv/bin/python ]]; then "$base_python" -m venv var/core/venv; fi
export PIP_CONFIG_FILE=/dev/null
var/core/venv/bin/python -m pip --isolated --disable-pip-version-check install --only-binary=:all: \
  --index-url https://pypi.org/simple -r requirements/core-test.in
var/core/venv/bin/python -m pip --isolated check
var/core/venv/bin/python -m pip --isolated freeze --all > "$run_dir/python.freeze.txt"
: > "$run_dir/npm-user-empty"
: > "$run_dir/npm-global-empty"
npm_flags=(--prefix frontend --userconfig "$run_dir/npm-user-empty" --globalconfig "$run_dir/npm-global-empty" --cache "$ROOT/var/core/npm-cache" --registry https://registry.npmjs.org)
npm "${npm_flags[@]}" install --no-audit --no-fund
npm "${npm_flags[@]}" ls --all > "$run_dir/npm-tree.txt"
cp frontend/package-lock.json "$run_dir/frontend-package-lock.json"
printf 'Core environment ready. Next: explicit Alembic upgrade, private CLI init-admin, then start.\n'
