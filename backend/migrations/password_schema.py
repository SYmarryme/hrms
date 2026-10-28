"""Password-security extension; old migration snapshots remain immutable."""
import sqlalchemy as sa

def extend(metadata):
    table=metadata.tables['users']
    table.append_column(sa.Column('must_change_password',sa.Boolean(),nullable=False,server_default=sa.text('0')))
    table.append_constraint(sa.CheckConstraint('must_change_password IN (0,1)',name='ck_users_password_change_flag'))
    return metadata
