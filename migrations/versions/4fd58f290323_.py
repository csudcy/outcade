"""Add event_type

Revision ID: 4fd58f290323
Revises: 33e3b2d5d77d
Create Date: 2014-08-15 15:44:43.142000

"""

# revision identifiers, used by Alembic.
revision = '4fd58f290323'
down_revision = '33e3b2d5d77d'

from alembic import op
import sqlalchemy as sa


# Make a temporary model of the event table
connection = op.get_bind()
event_table = sa.Table(
    'event',
    sa.MetaData(),
    sa.Column('id', sa.Integer),
    sa.Column('event_type', sa.String),
)

def upgrade():
    # Add new columns as nullable
    op.add_column('event', sa.Column('event_type', sa.String(length=10)))

    # Update everything
    connection.execute(
        event_table.update().values(
            event_type='APPROVED'
        )
    )

    # Make columns not nullable
    op.alter_column('event', 'event_type', nullable=False)


def downgrade():
    # Drop the column
    op.drop_column('event', 'event_type')
