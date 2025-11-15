"""add profile picture column to users

Revision ID: 5e7b4d3f3a12
Revises: 2372da6cdb62
Create Date: 2025-11-14 17:35:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "5e7b4d3f3a12"
down_revision: Union[str, None] = "2372da6cdb62"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade():
    op.add_column("users", sa.Column("profile_picture", sa.String(), nullable=True))


def downgrade():
    op.drop_column("users", "profile_picture")

