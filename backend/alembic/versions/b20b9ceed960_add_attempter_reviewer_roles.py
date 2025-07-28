"""add_attempter_reviewer_roles

Revision ID: b20b9ceed960
Revises: 3c22877cc2cf
Create Date: 2025-07-23 14:35:15.052015

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b20b9ceed960'
down_revision: Union[str, None] = '3c22877cc2cf'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
