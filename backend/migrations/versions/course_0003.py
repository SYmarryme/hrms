"""Add course MVP tables only; no rewriting existing identity or employment data."""
from alembic import op
from backend.migrations.schema_v1 import build_metadata
from backend.migrations.course_schema import extend

revision = 'course_0003'
down_revision = 'departments_0002'
branch_labels = None
depends_on = None


def upgrade():
    metadata = extend(build_metadata())
    bind = op.get_bind()
    for table in metadata.tables.values():
        if table.name.startswith('course_'):
            table.create(bind)
    next(index for index in metadata.tables['employees'].indexes if index.name == 'ix_course_employees_lookup').create(bind)
    for event in ('UPDATE', 'DELETE'):
        bind.exec_driver_sql(f"CREATE TRIGGER salary_history_no_{event.lower()} BEFORE {event} ON course_salary_history "
                             "BEGIN SELECT RAISE(ABORT, 'salary history is append-only'); END")


def downgrade():
    raise RuntimeError('Course business history is not automatically destroyed; use a reviewed backup plan')
