"""Synthetic SQLite marker before/after a MANUAL CloudStudio workspace restart."""
import argparse
import hashlib
import json
import sqlite3
import subprocess
import sys
import tempfile
import uuid
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def digest(rows):
    return hashlib.sha256(json.dumps(rows, separators=(',', ':')).encode()).hexdigest()


def prepare(data_root):
    if not data_root.is_absolute() or not data_root.is_dir():
        raise ValueError('--data-root must be an existing absolute directory selected by the operator')
    resolved = data_root.resolve()
    if resolved.is_relative_to(ROOT / 'experiments/t004/frontend') or any(
            part.name == 'frontend' and part.parent.name.startswith('t004-env.')
            for part in (resolved, *resolved.parents)):
        raise ValueError('The data root must not be a served frontend directory')
    folder = Path(tempfile.mkdtemp(prefix='hrms-t004.', dir=data_root))
    database = folder / 'marker.sqlite3'
    marker = uuid.uuid4().hex
    with closing(sqlite3.connect(database)) as db:
        db.execute('PRAGMA foreign_keys=ON')
        assert db.execute('PRAGMA foreign_keys').fetchone() == (1,)
        assert db.execute('PRAGMA journal_mode=WAL').fetchone() == ('wal',)
        db.execute('PRAGMA busy_timeout=1000')
        db.execute('CREATE TABLE t004_marker(id INTEGER PRIMARY KEY CHECK(id=1), marker TEXT NOT NULL)')
        db.execute('INSERT INTO t004_marker VALUES(1,?)', (marker,))
        db.commit()
        rows = db.execute('SELECT id,marker FROM t004_marker ORDER BY id').fetchall()
        assert db.execute('PRAGMA integrity_check').fetchall() == [('ok',)]
    return {'database': str(database.resolve()), 'marker': marker, 'row_digest': digest(rows),
            'commit': subprocess.check_output(['git', '-C', str(ROOT), 'rev-parse', 'HEAD'], text=True).strip(),
            'prepared_utc': datetime.now(timezone.utc).isoformat()}


def verify(receipt):
    expected = json.loads(receipt.read_text(encoding='utf-8'))
    current_commit = subprocess.check_output(['git', '-C', str(ROOT), 'rev-parse', 'HEAD'], text=True).strip()
    assert current_commit == expected['commit'], 'Code commit differs from the pre-restart baseline'
    database = Path(expected['database'])
    if not database.is_absolute() or database.name != 'marker.sqlite3' or not database.parent.name.startswith('hrms-t004.'):
        raise ValueError('Receipt does not name an isolated T-004 marker database')
    if not database.is_file():
        raise FileNotFoundError('Marker database is missing; do not recreate it')
    with closing(sqlite3.connect(database.as_uri() + '?mode=ro', uri=True)) as db:
        db.execute('PRAGMA foreign_keys=ON')
        assert db.execute('PRAGMA foreign_keys').fetchone() == (1,)
        db.execute('PRAGMA busy_timeout=1000')
        rows = db.execute('SELECT id,marker FROM t004_marker ORDER BY id').fetchall()
        assert rows == [(1, expected['marker'])], 'Stored marker changed'
        assert digest(rows) == expected['row_digest'], 'Stored row digest changed'
        assert db.execute('PRAGMA journal_mode').fetchone() == ('wal',)
        assert db.execute('PRAGMA foreign_key_check').fetchall() == []
        assert db.execute('PRAGMA integrity_check').fetchall() == [('ok',)]
    return {'logical_content': 'MATCH', 'integrity': 'ok', 'prepared_commit': expected['commit'],
            'workspace_restart': 'MANUAL_EVIDENCE_REQUIRED'}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('action', choices=['prepare', 'verify'])
    parser.add_argument('--data-root', type=Path)
    parser.add_argument('--receipt', type=Path)
    args = parser.parse_args()
    (ROOT / 'var/m00').mkdir(parents=True, exist_ok=True)
    log_dir = Path(tempfile.mkdtemp(prefix='t004-persistence.', dir=ROOT / 'var/m00'))
    try:
        if args.action == 'prepare':
            if args.data_root is None:
                raise ValueError('--data-root is required')
            report = prepare(args.data_root)
            (log_dir / 'receipt.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
            report = {'result': 'PREPARED', 'receipt': str(log_dir / 'receipt.json'),
                      'workspace_restart': 'NOT_RUN'}
        else:
            if args.receipt is None:
                raise ValueError('--receipt is required; keep an independent pre-restart copy')
            report = {'result': 'PASS', **verify(args.receipt)}
        code = 0
    except (OSError, ValueError, KeyError, AssertionError, sqlite3.Error) as error:
        report = {'result': 'FAIL', 'error_type': type(error).__name__,
                  'message': str(error) if isinstance(error, (AssertionError, ValueError)) else 'Missing/unreadable/invalid experiment data; inspect the private environment'}
        code = 1
    (log_dir / 'result.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    (log_dir / 'exit-code.txt').write_text(str(code) + '\n', encoding='utf-8')
    print(json.dumps(report, indent=2))
    print(f'T004_PERSISTENCE_EXIT_CODE={code}; artifacts={log_dir}')
    sys.exit(code)
