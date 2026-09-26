"""metrics read model: trechos assistidos, rollups por hora/dia e watermarks

Revision ID: 0003_metrics_read_model
Revises: 0002_video_storage
Create Date: 2026-09-26 20:21:08.531339
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = '0003_metrics_read_model'
down_revision: Union[str, None] = '0002_video_storage'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('metrics_rollup_state',
    sa.Column('name', sa.String(length=50), nullable=False),
    sa.Column('rolled_until', sa.DateTime(timezone=True), nullable=False),
    sa.PrimaryKeyConstraint('name')
    )
    op.create_table('video_metrics_daily',
    sa.Column('video_id', sa.String(length=36), nullable=False),
    sa.Column('day', sa.Date(), nullable=False),
    sa.Column('unique_impressions', sa.Integer(), nullable=False),
    sa.Column('unique_plays', sa.Integer(), nullable=False),
    sa.ForeignKeyConstraint(['video_id'], ['videos.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('video_id', 'day')
    )
    op.create_table('video_metrics_hourly',
    sa.Column('video_id', sa.String(length=36), nullable=False),
    sa.Column('hour_utc', sa.DateTime(timezone=True), nullable=False),
    sa.Column('impressions', sa.Integer(), nullable=False),
    sa.Column('plays', sa.Integer(), nullable=False),
    sa.Column('clicks', sa.Integer(), nullable=False),
    sa.Column('p25', sa.Integer(), nullable=False),
    sa.Column('p50', sa.Integer(), nullable=False),
    sa.Column('p75', sa.Integer(), nullable=False),
    sa.Column('p100', sa.Integer(), nullable=False),
    sa.ForeignKeyConstraint(['video_id'], ['videos.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('video_id', 'hour_utc')
    )
    op.create_table('video_retention_daily',
    sa.Column('video_id', sa.String(length=36), nullable=False),
    sa.Column('day', sa.Date(), nullable=False),
    sa.Column('sessions', sa.Integer(), nullable=False),
    sa.Column('watch_seconds', sa.Float(), nullable=False),
    sa.Column('counts', postgresql.ARRAY(sa.Integer()), nullable=False),
    sa.ForeignKeyConstraint(['video_id'], ['videos.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('video_id', 'day')
    )
    op.create_table('video_watch_sessions',
    sa.Column('video_id', sa.String(length=36), nullable=False),
    sa.Column('session_id', sa.String(length=100), nullable=False),
    sa.Column('event_date', sa.Date(), nullable=False),
    sa.Column('ranges', sa.JSON(), nullable=False),
    sa.Column('watched_seconds', sa.Float(), nullable=False),
    sa.Column('duration', sa.Float(), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['video_id'], ['videos.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('video_id', 'session_id', 'event_date')
    )
    op.create_index('ix_video_watch_sessions_date', 'video_watch_sessions', ['event_date'], unique=False)
    op.create_index('ix_video_analytics_video_type_created', 'video_analytics', ['video_id', 'event_type', 'created_at'], unique=False)


def downgrade() -> None:
    op.drop_index('ix_video_analytics_video_type_created', table_name='video_analytics')
    op.drop_index('ix_video_watch_sessions_date', table_name='video_watch_sessions')
    op.drop_table('video_watch_sessions')
    op.drop_table('video_retention_daily')
    op.drop_table('video_metrics_hourly')
    op.drop_table('video_metrics_daily')
    op.drop_table('metrics_rollup_state')
