"""origem do espectador (xid + UTMs) e indices do export

Revision ID: 0005_viewer_attribution
Revises: 0004_jobs_hls
Create Date: 2026-10-09 00:00:00

Os dois índices são criados sem CONCURRENTLY (mesmo padrão da 0003): travam
escrita em video_analytics / video_watch_sessions enquanto são construídos, no boot.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '0005_viewer_attribution'
down_revision: Union[str, None] = '0004_jobs_hls'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('viewer_attribution',
    sa.Column('video_id', sa.String(length=36), nullable=False),
    sa.Column('session_id', sa.String(length=100), nullable=False),
    sa.Column('external_id', sa.String(length=100), nullable=True),
    sa.Column('utm_source', sa.String(length=512), nullable=True),
    sa.Column('utm_medium', sa.String(length=512), nullable=True),
    sa.Column('utm_campaign', sa.String(length=512), nullable=True),
    sa.Column('utm_content', sa.String(length=512), nullable=True),
    sa.Column('utm_term', sa.String(length=512), nullable=True),
    sa.Column('first_seen_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['video_id'], ['videos.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('video_id', 'session_id')
    )
    op.create_index('ix_video_analytics_video_session_created', 'video_analytics', ['video_id', 'session_id', 'created_at'], unique=False)
    op.create_index('ix_video_watch_sessions_updated_at', 'video_watch_sessions', ['updated_at'], unique=False)


def downgrade() -> None:
    op.drop_index('ix_video_watch_sessions_updated_at', table_name='video_watch_sessions')
    op.drop_index('ix_video_analytics_video_session_created', table_name='video_analytics')
    op.drop_table('viewer_attribution')
