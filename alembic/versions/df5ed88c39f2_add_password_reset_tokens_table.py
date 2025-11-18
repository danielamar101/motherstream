"""add password reset tokens table

Revision ID: df5ed88c39f2
Revises: 5e7b4d3f3a12
Create Date: 2025-11-17 19:44:57.984426

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'df5ed88c39f2'
down_revision: Union[str, None] = '5e7b4d3f3a12'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create password_reset_tokens table
    op.create_table(
        'password_reset_tokens',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('token', sa.String(), nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=True),
        sa.Column('expires_at', sa.DateTime(), nullable=False),
        sa.Column('used', sa.Boolean(), server_default=sa.text('FALSE'), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create indexes for better performance
    op.create_index('idx_password_reset_token', 'password_reset_tokens', ['token'], unique=True)
    op.create_index('idx_password_reset_user_id', 'password_reset_tokens', ['user_id'], unique=False)
    op.create_index('idx_password_reset_expires_at', 'password_reset_tokens', ['expires_at'], unique=False)


def downgrade() -> None:
    # Drop indexes first
    op.drop_index('idx_password_reset_expires_at', table_name='password_reset_tokens')
    op.drop_index('idx_password_reset_user_id', table_name='password_reset_tokens')
    op.drop_index('idx_password_reset_token', table_name='password_reset_tokens')
    
    # Drop the table
    op.drop_table('password_reset_tokens')
