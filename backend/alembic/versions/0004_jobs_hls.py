"""fila de jobs no Postgres e colunas de HLS do video

Revision ID: 0004_jobs_hls
Revises: 0003_metrics_read_model
Create Date: 2026-09-27 00:07:41.340372
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '0004_jobs_hls'
down_revision: Union[str, None] = '0003_metrics_read_model'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('jobs',
    sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
    sa.Column('kind', sa.String(length=40), nullable=False),
    sa.Column('payload', sa.JSON(), nullable=False),
    sa.Column('status', sa.String(length=20), server_default='queued', nullable=False),
    sa.Column('attempts', sa.Integer(), server_default='0', nullable=False),
    sa.Column('max_attempts', sa.Integer(), server_default='3', nullable=False),
    sa.Column('run_after', sa.DateTime(timezone=True), nullable=False),
    sa.Column('locked_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('last_error', sa.Text(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_jobs_status_run_after', 'jobs', ['status', 'run_after'], unique=False)
    op.add_column('videos', sa.Column('hls_url', sa.String(length=1024), nullable=True))
    op.add_column('videos', sa.Column('processing_error', sa.String(length=500), nullable=True))


def downgrade() -> None:
    op.drop_column('videos', 'processing_error')
    op.drop_column('videos', 'hls_url')
    op.drop_index('ix_jobs_status_run_after', table_name='jobs')
    op.drop_table('jobs')
