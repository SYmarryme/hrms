"""Add department guards and one-time, attributed first-HR audit uniqueness.

No table rebuild, employee data, identity reset or change to the frozen v1 schema.
"""
from alembic import op
import sqlalchemy as sa

revision = 'departments_0002'
down_revision = 'identity_0001'
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    invalid = bind.exec_driver_sql("SELECT 1 FROM departments WHERE status NOT IN ('ACTIVE','DISABLED') LIMIT 1").first()
    if invalid:
        raise RuntimeError('Unknown existing department status; no automatic data conversion')
    op.create_index('ix_departments_parent', 'departments', ['parent_id'])
    op.create_index('uq_first_hr_success', 'audit_events', ['action_code'], unique=True,
                    sqlite_where=sa.text("action_code = 'identity.hr.initialize' AND outcome = 'SUCCESS'"))
    for event in ('INSERT', 'UPDATE'):
        bind.exec_driver_sql(f"CREATE TRIGGER department_status_{event.lower()} BEFORE {event} ON departments "
                             "WHEN NEW.status NOT IN ('ACTIVE','DISABLED') "
                             "BEGIN SELECT RAISE(ABORT, 'invalid department status'); END")


def downgrade():
    raise RuntimeError('Removing identity/department guards requires a separately reviewed migration')
