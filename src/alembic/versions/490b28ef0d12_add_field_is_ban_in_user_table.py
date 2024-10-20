"""add field is_ban in user table

Revision ID: 490b28ef0d12
Revises: f62e5ac1d560
Create Date: 2024-09-30 21:40:48.249555

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '490b28ef0d12'
down_revision: Union[str, None] = 'f62e5ac1d560'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column('users', sa.Column('is_ban', sa.Boolean(), nullable=True))
    # ### end Alembic commands ###


def downgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_column('users', 'is_ban')
    # ### end Alembic commands ###
