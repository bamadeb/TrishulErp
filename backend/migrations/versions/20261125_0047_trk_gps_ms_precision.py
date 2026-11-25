"""GPS points keep their capture time to the millisecond.

trk.trip_gps_point.recorded_at was DATETIME2(0): SQL Server rounded the phone's capture time to the second
(15:01:56.902 -> 15:01:57) while the upload's dedup compared milliseconds. So

  * a resent batch (an offline trip synced again after a lost response) was not recognised as already
    stored, and its insert hit UX_trk_trip_gps_point_dedup: HTTP 500 on every retry (trip 301,
    2026-11-23, trace a805718a50034124b28400fb7685479b);
  * two real points less than a second apart (the app records about once a second while moving) rounded
    to the same second and failed the same way, even on a first upload.

DATETIME2(3) stores what the phone sends. Existing rows keep their whole-second values; the upload matches a
resent point to them once (trk/service.py upload_gps). The unique index is the same, on the new precision.

Revision ID: 0047_trk_gps_ms_precision
Revises: 0046_face_attendance
Created: 2026-11-25
"""

from alembic import op

revision = "0047_trk_gps_ms_precision"
down_revision = "0046_face_attendance"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("DROP INDEX [UX_trk_trip_gps_point_dedup] ON [trk].[trip_gps_point];")
    op.execute("ALTER TABLE [trk].[trip_gps_point] ALTER COLUMN [recorded_at] DATETIME2(3) NOT NULL;")
    op.execute("""
        CREATE UNIQUE NONCLUSTERED INDEX [UX_trk_trip_gps_point_dedup]
            ON [trk].[trip_gps_point] ([trip_id], [recorded_at]);
    """)


def downgrade() -> None:
    # Back to whole seconds: points less than a second apart would collide, so keep the first of each.
    op.execute("DROP INDEX [UX_trk_trip_gps_point_dedup] ON [trk].[trip_gps_point];")
    op.execute("""
        WITH ranked AS (
            SELECT [id], ROW_NUMBER() OVER (
                PARTITION BY [trip_id], CAST([recorded_at] AS DATETIME2(0)) ORDER BY [recorded_at], [id]
            ) AS [n]
            FROM [trk].[trip_gps_point]
        )
        DELETE FROM ranked WHERE [n] > 1;
    """)
    op.execute("ALTER TABLE [trk].[trip_gps_point] ALTER COLUMN [recorded_at] DATETIME2(0) NOT NULL;")
    op.execute("""
        CREATE UNIQUE NONCLUSTERED INDEX [UX_trk_trip_gps_point_dedup]
            ON [trk].[trip_gps_point] ([trip_id], [recorded_at]);
    """)
