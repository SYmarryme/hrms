#!/usr/bin/env bash
set -euo pipefail
umask 077
ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"
if [[ -n "$(git status --porcelain --untracked-files=all -- experiments/t004 scripts/m00 requirements/m00-bootstrap.lock)" ]]; then
  echo 'Relevant source has local changes; synchronize the reviewed commit before setup' >&2
  exit 1
fi
mkdir -p var/m00
env_dir="$(mktemp -d "$ROOT/var/m00/t004-env.XXXXXXXX")"
exec > >(tee "$env_dir/setup.log") 2>&1
printf 'T004_ENV_DIR=%s\n' "$env_dir"
trap 'rc=$?; printf "%s\n" "$rc" > "$env_dir/setup-exit-code.txt"' EXIT
base_python="${T004_BASE_PYTHON:-$ROOT/.venv/bin/python}"
"$base_python" -I -c 'import sys; assert sys.version_info >= (3,11), "Python >=3.11 required"'
node -e 'const [a,b]=process.versions.node.split(".").map(Number); if(!((a===20&&b>=19)||(a===22&&b>=12)||a>22))process.exit(1); console.log("Node="+process.versions.node)'
npm --version
"$base_python" -I -m venv "$env_dir/venv"
export PIP_CONFIG_FILE=/dev/null
"$env_dir/venv/bin/python" -I -m pip --isolated --disable-pip-version-check install \
  --no-input --no-cache-dir --only-binary=:all: --index-url https://pypi.org/simple \
  -r requirements/m00-bootstrap.lock
"$env_dir/venv/bin/python" -I -m pip --isolated --disable-pip-version-check install \
  --no-input --no-cache-dir --only-binary=:all: --index-url https://pypi.org/simple \
  -r experiments/t004/requirements.in
"$env_dir/venv/bin/python" -I -m pip --isolated check
"$env_dir/venv/bin/python" -I -m pip --isolated freeze --all > "$env_dir/python.freeze.txt"
mkdir -p "$env_dir/frontend/src"
cp -- experiments/t004/frontend/{package.json,index.html,vite.config.mjs} "$env_dir/frontend/"
cp -- experiments/t004/frontend/src/main.ts "$env_dir/frontend/src/"
printf 't004-outside-should-not-serve\n' > "$env_dir/outside-canary.txt"
cd "$env_dir/frontend"
: > "$env_dir/npm-user-empty"
: > "$env_dir/npm-global-empty"
npm --userconfig "$env_dir/npm-user-empty" --globalconfig "$env_dir/npm-global-empty" --cache "$env_dir/npm-cache" \
  --registry https://registry.npmjs.org install --package-lock-only --ignore-scripts --no-audit --no-fund
npm --userconfig "$env_dir/npm-user-empty" --globalconfig "$env_dir/npm-global-empty" --cache "$env_dir/npm-cache" \
  --registry https://registry.npmjs.org ci --no-audit --no-fund
npm ls --all > "$env_dir/npm-tree.txt"
node --version > "$env_dir/node-version.txt"
npm --version > "$env_dir/npm-version.txt"
cd "$ROOT"
git rev-parse HEAD > "$env_dir/commit.txt"
printf 'T004_SETUP_EXIT_CODE=0\nT004_ENV_DIR=%s\n' "$env_dir"
