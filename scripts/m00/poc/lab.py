"""Infrastructure for temporary PoC files only; never imported by an HRMS app."""
import sqlite3
from contextlib import closing
from pathlib import Path

from alembic.config import Config
from sqlalchemy import create_engine, event
from sqlalchemy.engine import URL


def connect(path: Path, timeout_ms: int = 1000) -> sqlite3.Connection:
    if not isinstance(path, Path) or not path.name.endswith('.db'):
        raise ValueError('PoC requires a .db file Path, never :memory:')
    db = sqlite3.connect(path, isolation_level=None, timeout=timeout_ms / 1000)
    try:
        db.execute('PRAGMA foreign_keys=ON')
        # Do not set WAL repeatedly on existing WAL files during writer contention.
        if db.execute('PRAGMA journal_mode').fetchone()[0] != 'wal':
            assert db.execute('PRAGMA journal_mode=WAL').fetchone()[0] == 'wal'
        db.execute(f'PRAGMA busy_timeout={int(timeout_ms)}')
        assert db.execute('PRAGMA foreign_keys').fetchone()[0] == 1
        return db
    except BaseException:
        db.close()
        raise


def validate(db: sqlite3.Connection) -> None:
    assert db.execute('PRAGMA foreign_key_check').fetchall() == []
    assert db.execute('PRAGMA integrity_check').fetchall() == [('ok',)]


def engine_for(path: Path):
    engine = create_engine(URL.create('sqlite', database=str(path)))

    @event.listens_for(engine, 'connect')
    def configure(dbapi_connection, _record):
        # SQLAlchemy owns BEGIN explicitly, also on drivers using legacy DDL behavior.
        dbapi_connection.isolation_level = None
        cursor = dbapi_connection.cursor()
        try:
            cursor.execute('PRAGMA foreign_keys=ON')
            cursor.execute('PRAGMA journal_mode=WAL')
            assert cursor.fetchone()[0] == 'wal'
            cursor.execute('PRAGMA busy_timeout=1000')
        finally:
            cursor.close()

    @event.listens_for(engine, 'begin')
    def begin(connection):
        connection.exec_driver_sql('BEGIN')

    return engine


def migration_config(path: Path) -> Config:
    config = Config()
    config.set_main_option('script_location', str(Path(__file__).parent / 'alembic'))
    config.attributes['database_path'] = path
    return config


def snapshot(source: Path, destination: Path) -> None:
    """Online backup to a new, different file; refuse overwrites, check both ends."""
    if source.resolve() == destination.resolve():
        raise ValueError('Snapshot must use a different file')
    if not source.is_file():
        raise FileNotFoundError(source)
    with closing(sqlite3.connect(source.resolve().as_uri() + '?mode=ro', uri=True)) as src:
        src.execute('PRAGMA foreign_keys=ON')
        src.execute('PRAGMA busy_timeout=1000')
        assert src.execute('PRAGMA foreign_keys').fetchone() == (1,)
        validate(src)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.touch(exist_ok=False)
        with closing(sqlite3.connect(destination)) as dest:
            dest.execute('PRAGMA foreign_keys=ON')
            dest.execute('PRAGMA busy_timeout=1000')
            assert dest.execute('PRAGMA foreign_keys').fetchone() == (1,)
            src.backup(dest, pages=128, sleep=0.05)
            validate(dest)
