"""Add a restricted-password flag; never infer that legacy passwords were temporary."""
import sqlalchemy as sa
from alembic import op

revision='password_0004'
down_revision='course_0003'
branch_labels=None
depends_on=None

def upgrade():
    op.add_column('users',sa.Column('must_change_password',sa.Boolean(),sa.CheckConstraint('must_change_password IN (0,1)',name='ck_users_password_change_flag'),nullable=False,server_default=sa.text('0')))

def downgrade():
    raise RuntimeError('Password-security state is not silently removed; use a reviewed rollback plan')
