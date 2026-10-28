from contextlib import contextmanager
import os

from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import Session
from sqlalchemy.pool import NullPool


class Database:
    def __init__(self, path):
        path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        try:
            descriptor = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
            os.close(descriptor)
        except FileExistsError:
            pass  # Never overwrite or silently replace an operator's existing file.
        self.engine = create_engine('sqlite:///' + path.as_posix(), poolclass=NullPool,
                                    connect_args={'check_same_thread': False, 'timeout': 5}, hide_parameters=True)

        @event.listens_for(self.engine, 'connect')
        def configure(connection, _):
            connection.isolation_level = None
            connection.execute('PRAGMA foreign_keys=ON')
            connection.execute('PRAGMA busy_timeout=5000')

    @contextmanager
    def transaction(self, write=False):
        with Session(self.engine) as session:
            session.connection().exec_driver_sql('BEGIN IMMEDIATE' if write else 'BEGIN')
            try:
                yield session
                session.commit()
            except BaseException:
                session.rollback()
                raise

    def check_revision(self):
        from backend.models import metadata, CURRENT_REVISION
        with self.transaction() as session:
            if session.execute(text('SELECT version_num FROM alembic_version')).scalar_one() != CURRENT_REVISION:
                raise RuntimeError('Run the reviewed Alembic upgrade before starting HRMS')
            columns=session.connection().exec_driver_sql("PRAGMA table_info('users')").fetchall()
            if not any(row[1]=='must_change_password' and row[3]==1 for row in columns):
                raise RuntimeError('Password security column missing')
            tables = set(session.execute(text("SELECT name FROM sqlite_master WHERE type='table'")).scalars())
            if not set(metadata.tables).issubset(tables):
                raise RuntimeError('Versioned database is missing required tables')
            if session.connection().exec_driver_sql('PRAGMA foreign_key_check').fetchall():
                raise RuntimeError('Existing database foreign key integrity failure')
            indexes = session.connection().exec_driver_sql("PRAGMA index_list('audit_events')").fetchall()
            if not any(row[1] == 'uq_initial_admin_success' and row[2] == 1 and row[4] == 1 for row in indexes):
                raise RuntimeError('Initial administrator uniqueness index missing')
            if not any(row[1] == 'uq_first_hr_success' and row[2] == 1 and row[4] == 1 for row in indexes):
                raise RuntimeError('First HR uniqueness index missing')
            triggers = set(session.execute(text("SELECT name FROM sqlite_master WHERE type='trigger' AND tbl_name='departments'")).scalars())
            if not {'department_status_insert', 'department_status_update'}.issubset(triggers):
                raise RuntimeError('Department state guards missing')
