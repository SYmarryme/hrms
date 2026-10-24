"""Independent laboratory schema, unrelated to any approved HRMS table."""
from alembic import op
import sqlalchemy as sa

revision = 'm0001'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('lab_migration', sa.Column('id', sa.Integer, primary_key=True),
                    sa.Column('label', sa.String(40), nullable=False))


def downgrade():
    raise RuntimeError('PoC downgrade disabled; restore pre-migration snapshot into a new directory')
