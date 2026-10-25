#!/usr/bin/env bash
# Ubuntu only: retain a private consistent online backup before a non-destructive upgrade.
set -euo pipefail
umask 077
ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"
mkdir -p var/core
run_dir="$(mktemp -d "$ROOT/var/core/migration.XXXXXXXX")"
trap 'rc=$?; printf "%s\n" "$rc" > "$run_dir/exit-code.txt"; printf "CORE_MIGRATION_EXIT_CODE=%s; private artifacts=%s\n" "$rc" "$run_dir"' EXIT
var/core/venv/bin/python - "$run_dir" <<'PY'
from pathlib import Path
import sqlite3
import sys
from backend.settings import Settings
source = Settings.from_env().database_path
if source.exists():
    destination = Path(sys.argv[1]) / 'before.sqlite3'
    with sqlite3.connect(source.as_uri() + '?mode=ro', uri=True) as original:
        with sqlite3.connect(destination) as backup:
            original.backup(backup)
            if backup.execute('PRAGMA integrity_check').fetchall() != [('ok',)]:
                raise RuntimeError('Backup integrity check failed; migration cancelled')
    destination.chmod(0o600)
    print('Private consistent backup retained; not a restore authorization.')
PY
var/core/venv/bin/python -m alembic -c backend/alembic.ini upgrade head > "$run_dir/migration.log" 2>&1
var/core/venv/bin/python - <<'PY'
from backend.database import Database
from backend.settings import Settings
Database(Settings.from_env().database_path).check_revision()
PY
