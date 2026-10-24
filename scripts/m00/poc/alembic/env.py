"""Only accepts a programmatically supplied temporary PoC path; no .env business URL."""
from alembic import context

from poc.lab import engine_for

config = context.config
engine = engine_for(config.attributes['database_path'])
try:
    with engine.connect() as connection:
        context.configure(connection=connection, target_metadata=None,
                          render_as_batch=True, transactional_ddl=True)
        with context.begin_transaction():
            context.run_migrations()
finally:
    engine.dispose()
