"""add line to predictions for extra markets

Revision ID: a1b2c3d4e5f6
Revises: 06de9ee1fdc3
Create Date: 2026-08-26 00:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, None] = '06de9ee1fdc3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('predictions', sa.Column('line', sa.Float(), nullable=True))


def downgrade() -> None:
    op.drop_column('predictions', 'line')