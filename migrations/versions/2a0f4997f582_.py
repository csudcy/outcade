"""Initial create

Revision ID: 2a0f4997f582
Revises: None
Create Date: 2014-08-14 22:08:27.256000

"""

# revision identifiers, used by Alembic.
revision = '2a0f4997f582'
down_revision = None

from alembic import op
import sqlalchemy as sa


def upgrade():
    op.create_table('user',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=100), nullable=True),
        sa.Column('is_admin', sa.Boolean(), nullable=False),
        sa.Column('exchange_username', sa.String(length=100), nullable=False),
        sa.Column('exchange_password_encrypted', sa.String(length=200), nullable=False),
        sa.Column('exchange_last_sync_time', sa.DateTime(), nullable=True),
        sa.Column('exchange_last_sync_status', sa.Text(), nullable=True),
        sa.Column('cascade_username', sa.String(length=100), nullable=False),
        sa.Column('cascade_password_encrypted', sa.String(length=200), nullable=False),
        sa.Column('cascade_last_sync_time', sa.DateTime(), nullable=True),
        sa.Column('cascade_last_sync_status', sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_table('event',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('start', sa.DateTime(), nullable=False),
        sa.Column('end', sa.DateTime(), nullable=False),
        sa.Column('updated', sa.Boolean(), nullable=False),
        sa.Column('deleted', sa.Boolean(), nullable=False),
        sa.Column('exchange_id', sa.String(length=200), nullable=True),
        sa.Column('last_update', sa.DateTime(), nullable=True),
        sa.Column('last_push', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['user.id'], onupdate='CASCADE', ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )


def downgrade():
    op.drop_table('event')
    op.drop_table('user')
