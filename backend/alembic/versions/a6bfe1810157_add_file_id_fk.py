"""add_file_id_fk

Revision ID: a6bfe1810157
Revises: a5247ead5376
Create Date: 2025-07-25 19:19:53.366680

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a6bfe1810157'
down_revision: Union[str, None] = 'a5247ead5376'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
