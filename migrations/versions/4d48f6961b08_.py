"""Add User.sync_enabled

Revision ID: 4d48f6961b08
Revises: 2a0f4997f582
Create Date: 2014-08-15 13:12:50.191000

"""

# revision identifiers, used by Alembic.
revision = '4d48f6961b08'
down_revision = '2a0f4997f582'

from alembic import op
import sqlalchemy as sa


def upgrade():
    op.add_column('user', sa.Column('sync_enabled', sa.Boolean(), nullable=False, server_default='1'))


def downgrade():
    op.drop_column('user', 'sync_enabled')
