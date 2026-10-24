"""CloudStudio-only acceptance experiments. All rows are synthetic lab values."""
import json
import sqlite3
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing

import pytest
from alembic import command
from sqlalchemy import inspect, text

from poc.lab import connect, engine_for, migration_config, snapshot, validate


def create_lab(path):
    with closing(connect(path)) as db:
        db.executescript('''
            CREATE TABLE lab_parent(id INTEGER PRIMARY KEY);
            CREATE TABLE lab_child(id INTEGER PRIMARY KEY,
                parent_id INTEGER NOT NULL REFERENCES lab_parent(id));
            CREATE TABLE lab_item(id INTEGER PRIMARY KEY, version INTEGER NOT NULL,
                payload TEXT NOT NULL);
            INSERT INTO lab_item VALUES(1, 1, 'initial');
            CREATE TABLE lab_nullable(id INTEGER PRIMARY KEY, tag TEXT UNIQUE);
            CREATE TABLE lab_marker(id INTEGER PRIMARY KEY, kind TEXT NOT NULL,
                success INTEGER NOT NULL CHECK(success IN (0,1)));
            CREATE UNIQUE INDEX lab_first_once ON lab_marker(kind) WHERE success=1;
            CREATE TABLE lab_incident(id TEXT PRIMARY KEY NOT NULL);
            CREATE TABLE lab_gate(id INTEGER PRIMARY KEY CHECK(id=1),
                active_incident TEXT REFERENCES lab_incident(id));
            INSERT INTO lab_gate VALUES(1, NULL);
        ''')


def test_file_wal_foreign_keys_each_connection(tmp_path):
    path = tmp_path / 'lab.db'
    create_lab(path)
    with closing(connect(path)) as first, closing(connect(path)) as second:
        for db in (first, second):
            assert db.execute('PRAGMA foreign_keys').fetchone() == (1,)
            assert db.execute('PRAGMA journal_mode').fetchone() == ('wal',)
            assert db.execute('PRAGMA busy_timeout').fetchone() == (1000,)
            assert db.execute('PRAGMA database_list').fetchone()[2]
            with pytest.raises(sqlite3.IntegrityError):
                db.execute('INSERT INTO lab_child VALUES(1, 999)')
            validate(db)
        print('FK=ON WAL busy_timeout=1000 on two file connections')


def test_wal_reader_and_busy_timeout_rejection(tmp_path):
    path = tmp_path / 'lab.db'
    create_lab(path)
    with closing(connect(path)) as first, closing(connect(path, 200)) as second:
        first.execute('BEGIN IMMEDIATE')
        try:
            first.execute("UPDATE lab_item SET payload='uncommitted' WHERE id=1")
            assert second.execute('SELECT payload FROM lab_item').fetchone() == ('initial',)
            started = time.monotonic()
            with pytest.raises(sqlite3.OperationalError) as error:
                second.execute('BEGIN IMMEDIATE')
            elapsed = time.monotonic() - started
            assert error.value.sqlite_errorcode & 255 == sqlite3.SQLITE_BUSY
            assert 0.15 <= elapsed < 5, elapsed
            print(f'EXPECTED SQLITE_BUSY after {elapsed:.3f}s; reader saw committed data')
        finally:
            first.rollback()
        second.execute('BEGIN IMMEDIATE')
        second.rollback()
        validate(second)


def test_waiting_writer_succeeds_after_release(tmp_path):
    path = tmp_path / 'lab.db'
    create_lab(path)
    ready = threading.Event()

    def writer():
        with closing(connect(path, 3000)) as db:
            ready.set()
            db.execute('BEGIN IMMEDIATE')
            db.execute("UPDATE lab_item SET payload='second' WHERE id=1")
            db.commit()

    with closing(connect(path)) as first, ThreadPoolExecutor(max_workers=1) as pool:
        first.execute('BEGIN IMMEDIATE')
        try:
            result = pool.submit(writer)
            assert ready.wait(3)
            time.sleep(0.25)
            assert not result.done(), 'Second writer did not wait for held lock'
        finally:
            first.commit()
        result.result(timeout=5)
        assert first.execute('SELECT payload FROM lab_item').fetchone() == ('second',)
        validate(first)


def test_two_connection_cas_and_global_first_marker(tmp_path):
    path = tmp_path / 'lab.db'
    create_lab(path)
    barrier = threading.Barrier(2, timeout=5)

    def contender():
        with closing(connect(path, 3000)) as db:
            expected = db.execute('SELECT version FROM lab_item WHERE id=1').fetchone()[0]
            barrier.wait()
            db.execute('BEGIN IMMEDIATE')
            try:
                changed = db.execute('UPDATE lab_item SET version=version+1 '
                                     'WHERE id=1 AND version=?', (expected,)).rowcount
                db.commit()
                return changed
            except BaseException:
                db.rollback()
                raise

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(contender) for _ in range(2)]
        assert sorted(f.result(timeout=10) for f in futures) == [0, 1]
    with closing(connect(path)) as first, closing(connect(path)) as second:
        assert first.execute('SELECT version FROM lab_item').fetchone() == (2,)
        first.execute("INSERT INTO lab_marker(kind,success) VALUES('first',0)")
        first.execute("INSERT INTO lab_marker(kind,success) VALUES('first',1)")
        with pytest.raises(sqlite3.IntegrityError):
            second.execute("INSERT INTO lab_marker(kind,success) VALUES('first',1)")
        assert second.execute('SELECT count(*) FROM lab_marker WHERE success=1').fetchone() == (1,)
        validate(second)


def test_unique_null_and_required_key_boundaries(tmp_path):
    path = tmp_path / 'lab.db'
    create_lab(path)
    with closing(connect(path)) as db:
        db.execute('INSERT INTO lab_nullable(tag) VALUES(NULL),(NULL)')
        assert db.execute('SELECT count(*) FROM lab_nullable WHERE tag IS NULL').fetchone() == (2,)
        db.execute("INSERT INTO lab_nullable(tag) VALUES('same')")
        with pytest.raises(sqlite3.IntegrityError):
            db.execute("INSERT INTO lab_nullable(tag) VALUES('same')")
        with pytest.raises(sqlite3.IntegrityError):
            db.execute('INSERT INTO lab_incident(id) VALUES(NULL)')
        db.execute("INSERT INTO lab_incident VALUES('incident-1')")
        with pytest.raises(sqlite3.IntegrityError):
            db.execute("INSERT INTO lab_incident VALUES('incident-1')")
        validate(db)


def test_global_first_marker_race(tmp_path):
    path = tmp_path / 'lab.db'
    create_lab(path)
    barrier = threading.Barrier(2, timeout=5)

    def contender():
        with closing(connect(path, 3000)) as db:
            barrier.wait()
            db.execute('BEGIN IMMEDIATE')
            try:
                db.execute("INSERT INTO lab_marker(kind,success) VALUES('first',1)")
                db.commit()
                return 'accepted'
            except sqlite3.IntegrityError:
                db.rollback()
                return 'rejected'

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(contender) for _ in range(2)]
        assert sorted(f.result(timeout=10) for f in futures) == ['accepted', 'rejected']
    with closing(connect(path)) as db:
        assert db.execute('SELECT count(*) FROM lab_marker').fetchone() == (1,)
        validate(db)


@pytest.mark.parametrize('ids', [('incident-A', 'incident-A'), ('incident-A', 'incident-B')])
def test_incident_race_rechecks_global_gate_under_lock(tmp_path, ids):
    path = tmp_path / 'lab.db'
    create_lab(path)
    barrier = threading.Barrier(2, timeout=5)

    def contender(incident):
        with closing(connect(path, 3000)) as db:
            # Both see the same stale outside-transaction state.
            assert db.execute('SELECT active_incident FROM lab_gate').fetchone() == (None,)
            barrier.wait()
            db.execute('BEGIN IMMEDIATE')
            try:
                if db.execute('SELECT active_incident FROM lab_gate').fetchone()[0] is not None:
                    db.rollback()
                    return 'rejected'
                db.execute('INSERT INTO lab_incident VALUES(?)', (incident,))
                assert db.execute('UPDATE lab_gate SET active_incident=? '
                                  'WHERE id=1 AND active_incident IS NULL', (incident,)).rowcount == 1
                db.commit()
                return 'accepted'
            except BaseException:
                db.rollback()
                raise

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(contender, value) for value in ids]
        assert sorted(f.result(timeout=10) for f in futures) == ['accepted', 'rejected']
    with closing(connect(path)) as db:
        assert db.execute('SELECT count(*) FROM lab_incident').fetchone() == (1,)
        validate(db)
    print('Synthetic gate only; no production recovery or authorization logic')


def test_injected_dml_failure_rolls_back_all_writes(tmp_path):
    path = tmp_path / 'lab.db'
    create_lab(path)
    with closing(connect(path)) as db:
        with pytest.raises(RuntimeError, match='injected'):
            db.execute('BEGIN IMMEDIATE')
            try:
                db.execute('INSERT INTO lab_parent VALUES(1)')
                db.execute('INSERT INTO lab_child VALUES(1,1)')
                db.execute("INSERT INTO lab_marker(kind,success) VALUES('first',1)")
                raise RuntimeError('injected DML failure')
            except BaseException:
                db.rollback()
                raise
        for table in ('lab_parent', 'lab_child', 'lab_marker'):
            assert db.execute(f'SELECT count(*) FROM {table}').fetchone() == (0,)
        validate(db)


def test_sqlalchemy_each_connection_and_explicit_transaction(tmp_path):
    engine = engine_for(tmp_path / 'sqlalchemy.db')
    try:
        with engine.connect() as first, engine.connect() as second:
            for conn in (first, second):
                assert conn.exec_driver_sql('PRAGMA foreign_keys').scalar_one() == 1
                assert conn.exec_driver_sql('PRAGMA journal_mode').scalar_one() == 'wal'
                assert conn.exec_driver_sql('PRAGMA busy_timeout').scalar_one() == 1000
        with pytest.raises(RuntimeError, match='injected'):
            with engine.begin() as conn:
                conn.execute(text('CREATE TABLE lab_explicit(id INTEGER PRIMARY KEY)'))
                raise RuntimeError('injected explicit DDL failure')
        assert 'lab_explicit' not in inspect(engine).get_table_names()
    finally:
        engine.dispose()


def test_legacy_sqlite_ddl_limit_is_recorded(tmp_path):
    # With the legacy driver defaults CREATE TABLE may not issue BEGIN.
    with closing(sqlite3.connect(tmp_path / 'legacy.db', isolation_level='DEFERRED')) as db:
        db.execute('PRAGMA foreign_keys=ON')
        assert db.execute('PRAGMA foreign_keys').fetchone() == (1,)
        db.execute('CREATE TABLE lab_legacy(id INTEGER)')
        db.execute('INSERT INTO lab_legacy VALUES(1)')
        db.rollback()
        assert db.execute('SELECT count(*) FROM lab_legacy').fetchone() == (0,)
        assert db.execute("SELECT name FROM sqlite_master WHERE name='lab_legacy'").fetchone()
    print('OBSERVED: legacy DDL survived rollback; no general DDL rollback guarantee')


def test_online_backup_wal_isolated_restore_and_corrupt_rejection(tmp_path):
    path = tmp_path / 'source' / 'lab.db'
    path.parent.mkdir()
    create_lab(path)
    with closing(connect(path)) as writer:
        writer.execute('PRAGMA wal_autocheckpoint=0')
        writer.execute("UPDATE lab_item SET payload='committed WAL' WHERE id=1")
        assert path.with_name(path.name + '-wal').stat().st_size > 0
        writer.execute('BEGIN IMMEDIATE')
        try:
            writer.execute("UPDATE lab_item SET payload='pending' WHERE id=1")
            backup = tmp_path / 'backup' / 'snapshot.db'
            snapshot(path, backup)
        finally:
            writer.rollback()
    restored = tmp_path / 'isolated-restore' / 'restored.db'
    snapshot(backup, restored)
    with closing(connect(path)) as source, closing(connect(restored)) as target:
        assert target.execute('SELECT payload FROM lab_item').fetchone() == ('committed WAL',)
        assert list(source.iterdump()) == list(target.iterdump())
        validate(target)
    with pytest.raises(FileExistsError):
        snapshot(backup, restored)
    corrupt = tmp_path / 'corrupt.db'
    corrupt.write_bytes(b'not a sqlite database')
    with pytest.raises(sqlite3.DatabaseError):
        snapshot(corrupt, tmp_path / 'rejected' / 'never-approved.db')


def test_alembic_zero_upgrade_repeat_batch_and_failure_restore(tmp_path):
    fresh = tmp_path / 'fresh.db'
    cfg = migration_config(fresh)
    command.upgrade(cfg, 'head')
    command.upgrade(cfg, 'head')
    with closing(connect(fresh)) as db:
        assert db.execute('SELECT version_num FROM alembic_version').fetchone() == ('m0002',)
        assert 'note' in [row[1] for row in db.execute('PRAGMA table_info(lab_migration)')]
        validate(db)

    path = tmp_path / 'failure.db'
    cfg = migration_config(path)
    command.upgrade(cfg, 'm0001')
    with closing(connect(path)) as db:
        db.execute("INSERT INTO lab_migration(id,label) VALUES(1,'synthetic')")
    backup = tmp_path / 'backup' / 'pre-migration.db'
    snapshot(path, backup)
    cfg.attributes['inject_failure'] = True
    with pytest.raises(RuntimeError, match='injected migration failure'):
        command.upgrade(cfg, 'head')
    with closing(connect(path)) as db:
        observation = {
            'version': db.execute('SELECT version_num FROM alembic_version').fetchone()[0],
            'columns': [row[1] for row in db.execute('PRAGMA table_info(lab_migration)')],
            'rows': db.execute('SELECT id,label FROM lab_migration').fetchall(),
            'state': 'QUARANTINED_AFTER_EXPECTED_FAILURE',
        }
        (tmp_path / 'migration-failure.json').write_text(json.dumps(observation, indent=2), encoding='utf-8')
        print(json.dumps(observation))
        # Only this explicitly configured transaction mode is asserted, not all SQLite DDL.
        assert observation['version'] == 'm0001'
        assert observation['columns'] == ['id', 'label']
        assert observation['rows'] == [(1, 'synthetic')]
        validate(db)
    restored = tmp_path / 'migration-recovery' / 'restored.db'
    snapshot(backup, restored)
    command.upgrade(migration_config(restored), 'head')
    with closing(connect(restored)) as db:
        assert db.execute('SELECT id,label,note FROM lab_migration').fetchone() == (1, 'synthetic', None)
        assert db.execute('SELECT version_num FROM alembic_version').fetchone() == ('m0002',)
        validate(db)
