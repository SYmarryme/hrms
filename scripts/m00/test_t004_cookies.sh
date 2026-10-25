#!/usr/bin/env bash
# Manual CloudStudio regression only. No public requests or real cookie storage.
set -euo pipefail
umask 077
ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"
if [[ -n "$(git status --porcelain --untracked-files=all -- experiments/t004 scripts/m00 requirements/m00-bootstrap.lock)" ]]; then
  echo 'Relevant source has local changes; synchronize the reviewed commit before testing' >&2
  exit 1
fi
env_dir="$(realpath -e -- "${1:?usage: test_t004_cookies.sh T004_ENV_DIR}")"
case "$env_dir" in "$ROOT"/var/m00/t004-env.*) ;; *) echo 'Invalid T-004 environment' >&2; exit 1;; esac
[[ "$(cat "$env_dir/setup-exit-code.txt")" == 0 ]]
[[ "$(cat "$env_dir/commit.txt")" == "$(git rev-parse HEAD)" ]] || { echo 'Re-run setup for the current commit' >&2; exit 1; }
run_dir="$(mktemp -d "$ROOT/var/m00/t004-cookie-tests.XXXXXXXX")"
exec > >(tee "$run_dir/tests.log") 2>&1
trap 'rc=$?; printf "%s\n" "$rc" > "$run_dir/exit-code.txt"; printf "T004_COOKIE_TEST_EXIT_CODE=%s; artifacts=%s\n" "$rc" "$run_dir"' EXIT
export T004_PUBLIC_ORIGIN=https://t004-regression.invalid
export T004_COMMIT="$(git rev-parse HEAD)"
export PYTHONNOUSERSITE=1 PYTHONDONTWRITEBYTECODE=1
unset PYTHONHOME
PYTHONPATH="$ROOT/experiments/t004" "$env_dir/venv/bin/python" -m unittest discover \
  -s experiments/t004 -p test_cookie_path.py -v
