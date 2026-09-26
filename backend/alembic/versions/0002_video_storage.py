"""video storage: chave do arquivo no storage, tamanho e status de processamento

Revision ID: 0002_video_storage
Revises: 0001_baseline
Create Date: 2026-09-26 20:06:32.605443
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '0002_video_storage'
down_revision: Union[str, None] = '0001_baseline'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('videos', sa.Column('storage_key', sa.String(length=512), nullable=True))
    op.add_column('videos', sa.Column('source_size_bytes', sa.BigInteger(), nullable=True))
    op.add_column('videos', sa.Column('status', sa.String(length=20), server_default='ready', nullable=False))


def downgrade() -> None:
    op.drop_column('videos', 'status')
    op.drop_column('videos', 'source_size_bytes')
    op.drop_column('videos', 'storage_key')
