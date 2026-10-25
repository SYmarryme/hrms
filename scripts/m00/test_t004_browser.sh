#!/usr/bin/env bash
# Manual CloudStudio only. No HAR, trace, video or cookie/storage-state exports.
set -euo pipefail
umask 077
ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"
[[ -z "$(git status --porcelain --untracked-files=all -- experiments/t004 scripts/m00)" ]] || { echo 'Source is dirty; use the reviewed commit' >&2; exit 1; }
env_dir="$(realpath -e -- "${1:?usage: test_t004_browser.sh T004_ENV_DIR HTTPS_ORIGIN}")"
origin="${2:?bare HTTPS origin required}"
case "$env_dir" in "$ROOT"/var/m00/t004-env.*) ;; *) echo 'Invalid T-004 environment' >&2; exit 1;; esac
[[ "$(cat "$env_dir/setup-exit-code.txt")" == 0 && "$(cat "$env_dir/commit.txt")" == "$(git rev-parse HEAD)" ]]
run_dir="$(mktemp -d "$ROOT/var/m00/t004-browser.XXXXXXXX")"
exec > >(tee "$run_dir/run.log") 2>&1
printf 'T004_BROWSER_ARTIFACTS=%s\n' "$run_dir"
trap 'rc=$?; printf "%s\n" "$rc" > "$run_dir/exit-code.txt"; printf "T004_BROWSER_EXIT_CODE=%s\n" "$rc"' EXIT
unset DEBUG PWDEBUG PYTHONHOME PYTHONPATH
export PYTHONNOUSERSITE=1 PYTHONDONTWRITEBYTECODE=1 PIP_CONFIG_FILE=/dev/null
export PLAYWRIGHT_BROWSERS_PATH="$run_dir/browsers"
export XDG_CACHE_HOME="$run_dir/cache" TMPDIR="$run_dir/tmp"
mkdir -p "$TMPDIR"
"$env_dir/venv/bin/python" -I -m venv "$run_dir/venv"
python="$run_dir/venv/bin/python"
"$python" -I -m pip --isolated --disable-pip-version-check install --no-cache-dir --only-binary=:all: \
  --index-url https://pypi.org/simple -r requirements/m00-bootstrap.lock
"$python" -I -m pip --isolated --disable-pip-version-check install --no-cache-dir --only-binary=:all: \
  --index-url https://pypi.org/simple -r experiments/t004/requirements.browser.in
"$python" -I -m pip --isolated check
"$python" -I -m pip --isolated freeze --all > "$run_dir/python.freeze.txt"
PYTHONPATH="$ROOT/scripts/m00" "$python" -m unittest discover -s experiments/t004 -p test_cookie_trace.py -v
"$python" -I -m playwright install chromium
"$python" -I scripts/m00/t004_browser.py --origin "$origin" --commit "$(git rev-parse HEAD)" --output "$run_dir/result.json"
