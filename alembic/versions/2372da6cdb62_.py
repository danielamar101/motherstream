"""empty message

Revision ID: 2372da6cdb62
Revises: 
Create Date: 2025-02-12 19:02:55.193504

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '2372da6cdb62'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade():
    # Add the new columns with a default value of False
    op.add_column("users", sa.Column("is_superuser", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column("users", sa.Column("is_superduper_user", sa.Boolean(), nullable=False, server_default=sa.false()))


def downgrade():
    # Remove the columns if we roll back
    op.drop_column("users", "is_superuser")
    op.drop_column("users", "is_superduper_user")
