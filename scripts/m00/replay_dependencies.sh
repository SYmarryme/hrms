#!/usr/bin/env bash
# Execute manually in CloudStudio Ubuntu; never source this file.
set -euo pipefail
umask 077
ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"
mkdir -p "$ROOT/var/m00"
run_dir="$(mktemp -d "$ROOT/var/m00/replay.XXXXXXXX")"
venv_dir="$run_dir/venv"
base_python="${M00_REPLAY_PYTHON:-python3}"
stage=preflight
exec > >(tee "$run_dir/replay.log") 2>&1
finish() {
  local rc=$?
  trap - EXIT
  printf '%s\n' "$rc" > "$run_dir/exit-code.txt"
  printf 'last_stage=%s\nexit_code=%s\n' "$stage" "$rc" > "$run_dir/status.txt"
  printf '\nREPLAY_EXIT_CODE=%s; stage=%s; artifacts=%s\n' "$rc" "$stage" "$run_dir"
}
trap finish EXIT
printf 'UTC=%s\n' "$(date -u +%FT%TZ)"
git rev-parse HEAD | tee "$run_dir/commit.txt"
. /etc/os-release
printf 'OS=%s; architecture=%s\n' "$PRETTY_NAME" "$(uname -m)"
if [[ "$ID" != ubuntu || "$VERSION_ID" != 24.04 || "$(uname -m)" != x86_64 ]]; then
  printf 'REPLAY_FAIL: expected Ubuntu 24.04 x86_64 from the supplied snapshot\n' >&2
  exit 1
fi
"$base_python" -I -c 'import platform, sys; print("Python=" + platform.python_version()); sys.exit(0 if platform.python_version() == "3.11.1" else "REPLAY_FAIL: select Python 3.11.1 with M00_REPLAY_PYTHON")'
# The new directory is owned by this run. No --clear, reuse or deletion of any venv.
[[ ! -e "$venv_dir" && ! -L "$venv_dir" ]]
stage=create_venv
"$base_python" -I -m venv "$venv_dir"
replay_python="$venv_dir/bin/python"
export PATH="$venv_dir/bin:$PATH"
export VIRTUAL_ENV="$venv_dir"
unset PYTHONPATH PYTHONHOME
export PYTHONNOUSERSITE=1
export PYTHONDONTWRITEBYTECODE=1
# Ignore inherited pip indexes/configuration and pytest selection/plugins.
export PIP_CONFIG_FILE=/dev/null
export PYTEST_ADDOPTS=''
export PYTEST_PLUGINS=''
export PYTEST_DISABLE_PLUGIN_AUTOLOAD=1
pip_cmd() {
  "$replay_python" -I -m pip --isolated --disable-pip-version-check "$@"
}
stage=bootstrap_install
pip_cmd install --no-input --no-cache-dir --only-binary=:all: --no-deps \
  --index-url https://pypi.org/simple -r requirements/m00-bootstrap.lock
stage=project_install
pip_cmd install --no-input --no-cache-dir --only-binary=:all: --no-deps \
  --index-url https://pypi.org/simple -r requirements/m00.lock
stage=pip_check
pip_cmd check
stage=version_check
"$replay_python" -I scripts/m00/verify_m00_lock.py --venv "$venv_dir" \
  --output "$run_dir/versions.json"
pip_cmd freeze --all > "$run_dir/installed.freeze.txt"
"$replay_python" -I scripts/m00/env_probe.py
df -T "$run_dir"
stage=sqlite_poc
if PYTHONPATH="$ROOT/scripts/m00" "$replay_python" -m pytest -o addopts= -v -s \
    -o "cache_dir=$run_dir/pytest-cache" scripts/m00/poc/test_sqlite.py --basetemp "$run_dir/cases" \
    --junitxml="$run_dir/junit.xml"; then
  poc_rc=0
else
  poc_rc=$?
fi
printf '%s\n' "$poc_rc" > "$run_dir/poc-exit-code.txt"
printf 'POC_EXIT_CODE=%s\n' "$poc_rc"
if (( poc_rc != 0 )); then exit "$poc_rc"; fi
stage=final_verification
"$replay_python" -I scripts/m00/verify_m00_lock.py --venv "$venv_dir" \
  --junit "$run_dir/junit.xml" --output "$run_dir/verification.json"
stage=complete
printf 'REPLAY_CHECKS_OK: pip check; exact lock union; 13 PoC cases, zero failures/errors/skips\n'
