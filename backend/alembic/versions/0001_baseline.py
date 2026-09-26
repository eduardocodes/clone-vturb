"""baseline: schema existente antes do Alembic (gerado de create_all)

Revision ID: 0001_baseline
Revises: 
Create Date: 2026-09-26 19:43:45.239927
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '0001_baseline'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('backup_records',
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('filename', sa.String(length=255), nullable=False),
    sa.Column('size_bytes', sa.BigInteger(), nullable=False),
    sa.Column('status', sa.String(length=50), nullable=False),
    sa.Column('storage_path', sa.String(length=500), nullable=False),
    sa.Column('is_external', sa.Boolean(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_backup_records_created_at'), 'backup_records', ['created_at'], unique=False)
    op.create_index(op.f('ix_backup_records_filename'), 'backup_records', ['filename'], unique=False)
    op.create_table('backup_schedules',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('is_active', sa.Boolean(), nullable=False),
    sa.Column('frequency', sa.String(length=50), nullable=False),
    sa.Column('interval_value', sa.Integer(), nullable=False),
    sa.Column('s3_folder', sa.String(length=255), nullable=False),
    sa.Column('retention_limit', sa.Integer(), nullable=False),
    sa.Column('last_backup_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('next_backup_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('email_verification_codes',
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('email', sa.String(length=255), nullable=False),
    sa.Column('token', sa.String(length=64), nullable=False),
    sa.Column('code', sa.String(length=10), nullable=False),
    sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('is_verified', sa.Boolean(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_email_verification_codes_email'), 'email_verification_codes', ['email'], unique=False)
    op.create_index(op.f('ix_email_verification_codes_token'), 'email_verification_codes', ['token'], unique=False)
    op.create_table('password_reset_tokens',
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('user_id', sa.String(length=36), nullable=False),
    sa.Column('token', sa.String(length=64), nullable=False),
    sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('is_used', sa.Boolean(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_password_reset_tokens_token'), 'password_reset_tokens', ['token'], unique=True)
    op.create_index(op.f('ix_password_reset_tokens_user_id'), 'password_reset_tokens', ['user_id'], unique=False)
    op.create_table('user_invites',
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('token', sa.String(length=64), nullable=False),
    sa.Column('role', sa.String(length=50), nullable=False),
    sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('is_used', sa.Boolean(), nullable=False),
    sa.Column('used_by_email', sa.String(length=255), nullable=True),
    sa.Column('created_by_user_id', sa.String(length=36), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_user_invites_token'), 'user_invites', ['token'], unique=True)
    op.create_table('users',
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('email', sa.String(length=255), nullable=False),
    sa.Column('name', sa.String(length=255), nullable=True),
    sa.Column('password_hash', sa.String(length=255), nullable=False),
    sa.Column('role', sa.String(length=50), nullable=False),
    sa.Column('is_super_admin', sa.Boolean(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_users_email'), 'users', ['email'], unique=True)
    op.create_table('videos',
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('title', sa.String(length=255), nullable=False),
    sa.Column('video_url', sa.String(length=1024), nullable=False),
    sa.Column('thumbnail_url', sa.String(length=1024), nullable=True),
    sa.Column('duration', sa.Float(), nullable=True),
    sa.Column('player_settings', sa.JSON(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('video_analytics',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('video_id', sa.String(length=36), nullable=False),
    sa.Column('event_type', sa.String(length=50), nullable=False),
    sa.Column('watch_time_seconds', sa.Float(), nullable=True),
    sa.Column('session_id', sa.String(length=100), nullable=True),
    sa.Column('referer', sa.String(length=512), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
    sa.ForeignKeyConstraint(['video_id'], ['videos.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_video_analytics_created_at'), 'video_analytics', ['created_at'], unique=False)
    op.create_index(op.f('ix_video_analytics_event_type'), 'video_analytics', ['event_type'], unique=False)
    op.create_index(op.f('ix_video_analytics_video_id'), 'video_analytics', ['video_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_video_analytics_video_id'), table_name='video_analytics')
    op.drop_index(op.f('ix_video_analytics_event_type'), table_name='video_analytics')
    op.drop_index(op.f('ix_video_analytics_created_at'), table_name='video_analytics')
    op.drop_table('video_analytics')
    op.drop_table('videos')
    op.drop_index(op.f('ix_users_email'), table_name='users')
    op.drop_table('users')
    op.drop_index(op.f('ix_user_invites_token'), table_name='user_invites')
    op.drop_table('user_invites')
    op.drop_index(op.f('ix_password_reset_tokens_user_id'), table_name='password_reset_tokens')
    op.drop_index(op.f('ix_password_reset_tokens_token'), table_name='password_reset_tokens')
    op.drop_table('password_reset_tokens')
    op.drop_index(op.f('ix_email_verification_codes_token'), table_name='email_verification_codes')
    op.drop_index(op.f('ix_email_verification_codes_email'), table_name='email_verification_codes')
    op.drop_table('email_verification_codes')
    op.drop_table('backup_schedules')
    op.drop_index(op.f('ix_backup_records_filename'), table_name='backup_records')
    op.drop_index(op.f('ix_backup_records_created_at'), table_name='backup_records')
    op.drop_table('backup_records')
