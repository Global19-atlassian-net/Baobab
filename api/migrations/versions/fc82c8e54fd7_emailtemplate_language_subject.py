"""Add language and subject to email template

Revision ID: fc82c8e54fd7
Revises: 88cc4397bdf5
Create Date: 2020-08-06 21:14:20.137975

"""

# revision identifiers, used by Alembic.
revision = 'fc82c8e54fd7'
down_revision = '88cc4397bdf5'

from alembic import op
import sqlalchemy as sa


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column('email_template', sa.Column('language', sa.String(length=2), nullable=True))
    op.execute("""UPDATE email_template SET language='en'""")
    op.alter_column('email_template', 'language', nullable=False)
    op.add_column('email_template', sa.Column('subject', sa.String(), nullable=True))

    # TODO: SET SUBJECT ON EXISTING EMAILS! 

    op.alter_column('email_template', 'subject', nullable=False)
    op.drop_constraint(u'uq_email_template_key_event_id', 'email_template', type_='unique')
    op.create_unique_constraint('uq_email_template_key_event_id', 'email_template', ['key', 'event_id', 'language'])
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_constraint('uq_email_template_key_event_id', 'email_template', type_='unique')
    op.create_unique_constraint(u'uq_email_template_key_event_id', 'email_template', ['key', 'event_id'])
    op.drop_column('email_template', 'subject')
    op.drop_column('email_template', 'language')
    # ### end Alembic commands ###
