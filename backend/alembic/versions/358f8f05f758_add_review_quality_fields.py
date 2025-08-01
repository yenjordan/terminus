"""add_review_quality_fields

Revision ID: 358f8f05f758
Revises: ced145d5a92a
Create Date: 2025-07-25 18:00:35.651057

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '358f8f05f758'
down_revision: Union[str, None] = 'ced145d5a92a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_index('ix_files_id', table_name='files')
    op.drop_index('ix_files_name', table_name='files')
    op.drop_index('ix_files_path', table_name='files')
    op.drop_table('files')
    op.drop_index('ix_sessions_id', table_name='sessions')
    op.drop_index('ix_sessions_name', table_name='sessions')
    op.drop_table('sessions')
    op.add_column('code_reviews', sa.Column('edits_description', sa.Text(), nullable=True))
    op.add_column('code_reviews', sa.Column('is_good_enough', sa.Boolean(), nullable=True))
    op.drop_column('code_reviews', 'is_customer_ready')
    op.drop_column('code_reviews', 'updated_at')
    op.drop_column('code_reviews', 'edits_made')
    op.drop_index('ix_code_submissions_task_id', table_name='code_submissions')
    op.drop_column('code_submissions', 'task_id')
    op.drop_column('code_submissions', 'file_id')
    op.drop_column('code_submissions', 'claimed_at')
    op.drop_column('code_submissions', 'claimed_by')
    # ### end Alembic commands ###


def downgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column('code_submissions', sa.Column('claimed_by', sa.INTEGER(), nullable=True))
    op.add_column('code_submissions', sa.Column('claimed_at', sa.DATETIME(), nullable=True))
    op.add_column('code_submissions', sa.Column('file_id', sa.INTEGER(), nullable=True))
    op.add_column('code_submissions', sa.Column('task_id', sa.VARCHAR(), nullable=True))
    op.create_index('ix_code_submissions_task_id', 'code_submissions', ['task_id'], unique=False)
    op.add_column('code_reviews', sa.Column('edits_made', sa.TEXT(), nullable=True))
    op.add_column('code_reviews', sa.Column('updated_at', sa.DATETIME(), nullable=True))
    op.add_column('code_reviews', sa.Column('is_customer_ready', sa.BOOLEAN(), nullable=True))
    op.drop_column('code_reviews', 'is_good_enough')
    op.drop_column('code_reviews', 'edits_description')
    op.create_table('sessions',
    sa.Column('id', sa.INTEGER(), nullable=False),
    sa.Column('name', sa.VARCHAR(), nullable=True),
    sa.Column('description', sa.VARCHAR(), nullable=True),
    sa.Column('is_active', sa.BOOLEAN(), nullable=True),
    sa.Column('user_id', sa.INTEGER(), nullable=True),
    sa.Column('last_accessed', sa.DATETIME(), nullable=True),
    sa.Column('created_at', sa.DATETIME(), nullable=True),
    sa.Column('updated_at', sa.DATETIME(), nullable=True),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_sessions_name', 'sessions', ['name'], unique=False)
    op.create_index('ix_sessions_id', 'sessions', ['id'], unique=False)
    op.create_table('files',
    sa.Column('id', sa.INTEGER(), nullable=False),
    sa.Column('name', sa.VARCHAR(), nullable=True),
    sa.Column('path', sa.VARCHAR(), nullable=True),
    sa.Column('content', sa.TEXT(), nullable=True),
    sa.Column('file_type', sa.VARCHAR(), nullable=True),
    sa.Column('session_id', sa.INTEGER(), nullable=True),
    sa.Column('size_bytes', sa.INTEGER(), nullable=True),
    sa.Column('created_at', sa.DATETIME(), nullable=True),
    sa.Column('updated_at', sa.DATETIME(), nullable=True),
    sa.ForeignKeyConstraint(['session_id'], ['sessions.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_files_path', 'files', ['path'], unique=False)
    op.create_index('ix_files_name', 'files', ['name'], unique=False)
    op.create_index('ix_files_id', 'files', ['id'], unique=False)
    # ### end Alembic commands ###
