from alembic import context
from sqlalchemy import inspect

from backend.database import Database
from backend.models import metadata
from backend.settings import Settings
from backend.migrations.schema_v1 import build_metadata

settings = context.config.attributes.get('settings') or Settings.from_env()
database = Database(settings.database_path)
with database.engine.connect() as connection:
    tables = inspect(connection).get_table_names()
    if tables and 'alembic_version' not in tables:
        raise RuntimeError('Existing unversioned database; refusing to adopt or overwrite it')
    if 'alembic_version' in tables:
        versions = connection.exec_driver_sql('SELECT version_num FROM alembic_version').scalars().all()
        if versions not in ([], ['identity_0001'], ['departments_0002'], ['course_0003']) or (not versions and len(tables) > 1):
            raise RuntimeError('Foreign or partial migration baseline; refusing to adopt it')
        required = metadata if versions == ['course_0003'] else build_metadata()
        if versions and not set(required.tables).issubset(tables):
            raise RuntimeError('Versioned database is missing required tables; refusing to repair it implicitly')
    connection.rollback()
    if connection.exec_driver_sql('PRAGMA journal_mode=WAL').scalar_one() != 'wal':
        raise RuntimeError('SQLite file WAL mode is required')
    connection.commit()
    connection.exec_driver_sql('BEGIN IMMEDIATE')
    try:
        context.configure(connection=connection, target_metadata=metadata, render_as_batch=True)
        context.run_migrations()
        if connection.exec_driver_sql('PRAGMA foreign_key_check').fetchall():
            raise RuntimeError('Foreign key integrity failure')
        connection.commit()
    except BaseException:
        connection.rollback()
        raise
database.engine.dispose()
