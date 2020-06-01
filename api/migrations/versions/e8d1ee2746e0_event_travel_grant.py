"""Add travel grant column to event.

Revision ID: e8d1ee2746e0
Revises: 7f37bf248c81
Create Date: 2020-05-24 15:35:18.742658

"""

# revision identifiers, used by Alembic.
revision = 'e8d1ee2746e0'
down_revision = '7f37bf248c81'

from alembic import op
import sqlalchemy as sa


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column('event', sa.Column('travel_grant', sa.Boolean(), nullable=True))
    op.execute("""UPDATE event SET travel_grant=True WHERE name IN ('indaba 2019', 'Test Event')""")
    op.execute("""UPDATE event SET travel_grant=False WHERE name NOT IN ('indaba 2019', 'Test Event')""")
    op.alter_column('event', 'travel_grant', existing_type=sa.Boolean(), nullable=False)
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_column('event', 'travel_grant')
    # ### end Alembic commands ###