"""Additive course MVP schema. Keep v1 identity/history tables intact."""
import sqlalchemy as sa


def extend(m):
    def fk(name, target):
        return sa.Column(name, sa.String(36), sa.ForeignKey(target, ondelete='RESTRICT'), nullable=False)
    def ident():
        return [sa.Column('id', sa.String(36), primary_key=True), sa.Column('created_at', sa.DateTime(), nullable=False),
                sa.Column('updated_at', sa.DateTime(), nullable=False), sa.Column('version_no', sa.Integer(), nullable=False, server_default='1')]
    sa.Table('course_manager_departments', m, fk('user_id', 'users.id'), fk('department_id', 'departments.id'),
             sa.PrimaryKeyConstraint('user_id', 'department_id'))
    sa.Table('course_attendance_rules', m, *ident(), sa.Column('effective_from', sa.Date(), nullable=False, unique=True),
             sa.Column('weekdays', sa.JSON(), nullable=False), sa.Column('start_time', sa.String(5), nullable=False),
             sa.Column('end_time', sa.String(5), nullable=False), sa.Column('grace_minutes', sa.Integer(), nullable=False),
             sa.CheckConstraint('grace_minutes >= 0 AND grace_minutes <= 120'))
    sa.Table('course_attendance', m, *ident(), fk('employee_id', 'employees.id'),
             sa.Column('work_date', sa.Date(), nullable=False), sa.Column('clock_in_at', sa.DateTime(), nullable=False),
             sa.Column('clock_out_at', sa.DateTime()), sa.UniqueConstraint('employee_id', 'work_date'))
    sa.Table('course_leaves', m, *ident(), fk('employee_id', 'employees.id'), fk('department_id', 'departments.id'),
             sa.Column('start_date', sa.Date(), nullable=False), sa.Column('end_date', sa.Date(), nullable=False),
             sa.Column('leave_type', sa.String(16), nullable=False), sa.Column('reason', sa.String(500), nullable=False),
             sa.Column('status', sa.String(16), nullable=False), sa.Column('decided_by', sa.String(36), sa.ForeignKey('users.id')),
             sa.Column('decided_at', sa.DateTime()), sa.Column('opinion', sa.String(500)),
             sa.CheckConstraint("status IN ('PENDING','APPROVED','REJECTED','CANCELLED')"),
             sa.CheckConstraint("leave_type IN ('ANNUAL','SICK','PERSONAL','OTHER')"),
             sa.CheckConstraint('end_date >= start_date'))
    sa.Table('course_salaries', m, *ident(), fk('employee_id', 'employees.id'), sa.Column('month', sa.String(7), nullable=False),
             sa.Column('amount_cents', sa.BigInteger(), nullable=False), sa.CheckConstraint('amount_cents >= 0'),
             sa.UniqueConstraint('employee_id', 'month'))
    sa.Table('course_salary_history', m, sa.Column('id', sa.String(36), primary_key=True), fk('salary_id', 'course_salaries.id'),
             sa.Column('version_no', sa.Integer(), nullable=False), sa.Column('amount_cents', sa.BigInteger(), nullable=False),
             fk('actor_user_id', 'users.id'), sa.Column('recorded_at', sa.DateTime(), nullable=False),
             sa.UniqueConstraint('salary_id', 'version_no'))
    for name, cols in [('course_leaves', ('department_id', 'status')), ('course_attendance', ('work_date',)),
                       ('employees', ('current_department_id', 'employment_status'))]:
        sa.Index('ix_course_' + name + '_lookup', *(m.tables[name].c[c] for c in cols))
    return m
