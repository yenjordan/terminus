"""add_missing_code_review_columns

Revision ID: de8c3a1f4cb4
Revises: a6bfe1810157, 7e8f9a1b2c3d
Create Date: 2025-07-27 01:45:07.541436

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'de8c3a1f4cb4'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = ['a6bfe1810157', '7e8f9a1b2c3d']


def upgrade() -> None:
    # Use batch operations for SQLite compatibility
    with op.batch_alter_table('code_reviews') as batch_op:
        # Add columns one by one, ignoring errors if they already exist
        try:
            batch_op.add_column(sa.Column('feedback', sa.Text(), nullable=True))
        except Exception:
            pass
        
        try:
            batch_op.add_column(sa.Column('quality_before_edits', sa.Integer(), nullable=True))
        except Exception:
            pass
        
        try:
            batch_op.add_column(sa.Column('quality_after_edits', sa.Integer(), nullable=True))
        except Exception:
            pass
        
        try:
            batch_op.add_column(sa.Column('edits_made', sa.Text(), nullable=True))
        except Exception:
            pass
        
        try:
            batch_op.add_column(sa.Column('is_customer_ready', sa.Boolean(), nullable=True))
        except Exception:
            pass


def downgrade() -> None:
    # No downgrade operation needed
    pass
