"""Initial identity schema with complete FK parents; no business APIs.

Uses the IMMUTABLE versioned schema snapshot, never current application metadata.
"""
from uuid import NAMESPACE_URL, uuid5
from datetime import datetime, timezone

from alembic import op

from backend.migrations.schema_v1 import build_metadata

revision = 'identity_0001'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    metadata = build_metadata()
    bind = op.get_bind()
    metadata.create_all(bind)
    now = datetime.now(timezone.utc)
    bind.execute(metadata.tables['roles'].insert(), [
        {'id': str(uuid5(NAMESPACE_URL, 'hrms.role.' + code)), 'code': code, 'name': name,
         'created_at': now, 'updated_at': now}
        for code, name in [('EMPLOYEE', '员工'), ('MANAGER', '主管'), ('HR', '人事'), ('ADMIN', '系统管理员')]])
    for operation in ('UPDATE', 'DELETE'):
        bind.exec_driver_sql(f"CREATE TRIGGER audit_no_{operation.lower()} BEFORE {operation} ON audit_events "
                             "BEGIN SELECT RAISE(ABORT, 'audit is append-only'); END")


def downgrade():
    raise RuntimeError('Identity/audit destruction is not an automatic downgrade; use a reviewed backup/migration plan')
