"""Exercise move-and-copy migration and explicit injected failure."""
from alembic import op
import sqlalchemy as sa

revision = 'm0002'
down_revision = 'm0001'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('lab_migration', recreate='always') as batch:
        batch.add_column(sa.Column('note', sa.String(40), nullable=True))
    if op.get_context().config.attributes.get('inject_failure', False):
        raise RuntimeError('injected migration failure after batch DDL')


def downgrade():
    raise RuntimeError('PoC downgrade disabled; recover from verified snapshot')
