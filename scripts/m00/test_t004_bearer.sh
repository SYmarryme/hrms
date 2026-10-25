#!/usr/bin/env bash
# CloudStudio-only backend regressions. Actual acceptance still requires Edge HTTPS.
set -euo pipefail
umask 077
ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"
[[ -z "$(git status --porcelain --untracked-files=all -- experiments/t004 scripts/m00)" ]] || { echo 'Use the reviewed clean source commit' >&2; exit 1; }
env_dir="$(realpath -e -- "${1:?usage: test_t004_bearer.sh T004_ENV_DIR}")"
case "$env_dir" in "$ROOT"/var/m00/t004-env.*) ;; *) echo 'Invalid T-004 environment' >&2; exit 1;; esac
[[ "$(cat "$env_dir/setup-exit-code.txt")" == 0 && "$(cat "$env_dir/commit.txt")" == "$(git rev-parse HEAD)" ]]
run_dir="$(mktemp -d "$ROOT/var/m00/t004-bearer-tests.XXXXXXXX")"
exec > >(tee "$run_dir/tests.log") 2>&1
trap 'rc=$?; printf "%s\n" "$rc" > "$run_dir/exit-code.txt"; printf "T004_BEARER_TEST_EXIT_CODE=%s; artifacts=%s\n" "$rc" "$run_dir"' EXIT
export T004_PUBLIC_ORIGIN=https://t004-regression.invalid
export T004_COMMIT="$(git rev-parse HEAD)"
export PYTHONNOUSERSITE=1 PYTHONDONTWRITEBYTECODE=1
unset PYTHONHOME
PYTHONPATH="$ROOT/experiments/t004" "$env_dir/venv/bin/python" -m unittest discover \
  -s experiments/t004 -p test_bearer.py -v
