"""Remarks on a trip, saved when the engineer stops it (POST /trk/trips/{tripId}/stop).

trk.trip.remarks  NVARCHAR(500) NULL. Existing trips keep NULL.

Idempotent: every statement checks first.

Revision ID: 0025_trip_remarks
Revises: 0024_warehouse_permissions
Created: 2026-11-06
"""

from alembic import op

revision = "0025_trip_remarks"
down_revision = "0024_warehouse_permissions"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        IF COL_LENGTH(N'trk.trip', N'remarks') IS NULL
            ALTER TABLE [trk].[trip] ADD [remarks] NVARCHAR(500) NULL;
    """)


def downgrade() -> None:
    op.execute("""
        IF COL_LENGTH(N'trk.trip', N'remarks') IS NOT NULL
            ALTER TABLE [trk].[trip] DROP COLUMN [remarks];
    """)
