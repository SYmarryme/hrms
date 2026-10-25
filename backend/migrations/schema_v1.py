"""Immutable v1 identity FK closure, not a declaration of all 54 business tables.

Each call returns NEW metadata. Later application metadata changes cannot mutate
the historical migration. Extend through new revisions, never edit this snapshot.
"""
import sqlalchemy as sa


def build_metadata():
    m = sa.MetaData()
    def col(name, kind=sa.String(36), nullable=False, **kw):
        return sa.Column(name, kind, nullable=nullable, **kw)
    def fk(name, target, nullable=False):
        return sa.Column(name, sa.String(36), sa.ForeignKey(target, ondelete='RESTRICT'), nullable=nullable)
    def identity():
        return [col('id', primary_key=True), col('created_at', sa.DateTime()), col('updated_at', sa.DateTime())]
    def version():
        return col('version_no', sa.Integer(), server_default='1')
    sa.Table('departments', m, *identity(), col('code', sa.String(64), unique=True), col('name', sa.String(128)),
             fk('parent_id', 'departments.id', True), col('status', sa.String(32)), version(),
             sa.CheckConstraint('parent_id IS NULL OR parent_id != id', name='department_no_self_parent'))
    sa.Table('positions', m, *identity(), fk('department_id', 'departments.id'), col('code', sa.String(64)),
             col('name', sa.String(128)), col('grade_code', sa.String(64)), fk('reports_to_position_id', 'positions.id', True),
             col('status', sa.String(32)), version(), sa.UniqueConstraint('department_id', 'code'),
             sa.UniqueConstraint('id', 'department_id'),
             sa.CheckConstraint('reports_to_position_id IS NULL OR reports_to_position_id != id'))
    sa.Table('employees', m, *identity(), col('employee_no', sa.String(64), unique=True), col('full_name', sa.String(128)),
             fk('current_department_id', 'departments.id', True), fk('current_position_id', 'positions.id', True),
             col('employment_status', sa.String(32)), col('hire_date', sa.Date(), True), col('termination_date', sa.Date(), True),
             version(), sa.CheckConstraint("employment_status IN ('PRE_HIRE','PROBATION','ACTIVE','EXIT_PROCESSING','TERMINATED')"))
    sa.Table('users', m, *identity(), col('username', sa.String(64), unique=True), col('password_hash', sa.String(512)),
             fk('employee_id', 'employees.id', True), col('status', sa.String(16)), col('password_changed_at', sa.DateTime(), True),
             version(), sa.UniqueConstraint('employee_id'), sa.CheckConstraint("status IN ('ACTIVE','DISABLED')"))
    sa.Table('roles', m, *identity(), col('code', sa.String(32), unique=True), col('name', sa.String(128)),
             sa.CheckConstraint("code IN ('EMPLOYEE','MANAGER','HR','ADMIN')"))
    sa.Table('role_assignments', m, *identity(), fk('user_id', 'users.id'), fk('role_id', 'roles.id'),
             col('valid_from_at', sa.DateTime()), col('valid_to_at', sa.DateTime(), True), fk('assigned_by', 'users.id', True),
             col('revoked_at', sa.DateTime(), True), col('reason', sa.String(256)),
             col('bootstrap_origin', sa.Boolean(), server_default=sa.false()),
             sa.CheckConstraint('(bootstrap_origin = 1 AND assigned_by IS NULL) OR '
                                '(bootstrap_origin = 0 AND assigned_by IS NOT NULL AND assigned_by != user_id)'),
             sa.CheckConstraint('valid_to_at IS NULL OR valid_to_at > valid_from_at'))
    sa.Table('auth_sessions', m, col('id', primary_key=True), fk('user_id', 'users.id'),
             col('token_hash', sa.String(64), unique=True), col('created_at', sa.DateTime()), col('expires_at', sa.DateTime()),
             col('revoked_at', sa.DateTime(), True), col('last_seen_at', sa.DateTime(), True),
             col('user_agent_digest', sa.String(64), True), sa.CheckConstraint('expires_at > created_at'))
    sa.Table('approval_cases', m, *identity(), col('case_type', sa.String(64)), fk('requester_employee_id', 'employees.id'),
             col('status', sa.String(32)), col('current_version', sa.Integer()),
             fk('submitted_appointment_proposal_version_id', 'management_appointment_proposal_versions.id', True),
             col('submitted_at', sa.DateTime(), True), fk('department_id_snapshot', 'departments.id', True),
             col('reason', sa.Text(), True), col('closed_at', sa.DateTime(), True))
    sa.Table('management_appointment_proposal_versions', m, col('id', primary_key=True), col('created_at', sa.DateTime()),
             fk('approval_case_id', 'approval_cases.id'), col('proposal_revision', sa.Integer()), fk('employee_id', 'employees.id'),
             col('appointment_type', sa.String(32)), col('title_snapshot', sa.String(128)), col('valid_from_at', sa.DateTime()),
             col('valid_to_at', sa.DateTime(), True), col('reason', sa.Text()), fk('created_by_user_id', 'users.id'),
             col('content_digest', sa.String(64)), sa.UniqueConstraint('approval_case_id', 'proposal_revision'))
    sa.Table('employee_lifecycle_events', m, col('id', primary_key=True), col('created_at', sa.DateTime()),
             fk('employee_id', 'employees.id'), col('event_type', sa.String(64)), col('old_status', sa.String(32), True),
             col('new_status', sa.String(32), True), col('planned_date', sa.Date(), True), col('effective_date', sa.Date(), True),
             fk('approval_case_id', 'approval_cases.id', True), col('reason', sa.Text()), col('payload_snapshot', sa.JSON()),
             col('executed_at', sa.DateTime(), True))
    sa.Table('employee_assignments', m, *identity(), fk('employee_id', 'employees.id'), fk('department_id', 'departments.id'),
             fk('position_id', 'positions.id'), col('valid_from', sa.Date()), col('valid_to', sa.Date(), True),
             fk('change_event_id', 'employee_lifecycle_events.id', True),
             sa.ForeignKeyConstraint(['position_id', 'department_id'], ['positions.id', 'positions.department_id'], ondelete='RESTRICT'),
             sa.CheckConstraint('valid_to IS NULL OR valid_to >= valid_from'))
    audit = sa.Table('audit_events', m, col('id', primary_key=True), col('occurred_at', sa.DateTime()),
             fk('actor_user_id', 'users.id', True), col('action_code', sa.String(128)), col('resource_type', sa.String(64)),
             col('resource_id', sa.String(64)), col('outcome', sa.String(32)), col('request_id', sa.String(36)),
             col('reason_code', sa.String(64), True), col('metadata_redacted', sa.JSON()))
    sa.Index('uq_initial_admin_success', audit.c.action_code, unique=True,
             sqlite_where=sa.text("action_code = 'system.bootstrap.complete' AND outcome = 'SUCCESS'"))
    sa.Table('outbox_events', m, col('id', primary_key=True), col('event_type', sa.String(128)), col('object_type', sa.String(64)),
             col('object_id', sa.String(64)), col('idempotency_key', sa.String(128), unique=True), col('payload_redacted', sa.JSON()),
             col('status', sa.String(32)), col('attempts', sa.Integer(), server_default='0'), col('next_attempt_at', sa.DateTime(), True),
             col('created_at', sa.DateTime()), col('last_error_code', sa.String(64), True), col('failed_at', sa.DateTime(), True),
             col('last_attempt_at', sa.DateTime(), True),
             sa.CheckConstraint("status IN ('PENDING','PROCESSING','DELIVERED','FAILED_NEEDS_ATTENTION')"))
    sa.Index('ix_session_user_expiry', m.tables['auth_sessions'].c.user_id, m.tables['auth_sessions'].c.expires_at)
    return m
