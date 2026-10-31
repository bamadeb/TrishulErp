"""Manual kilometre adjustment of a trip by a Team Lead, with a full audit trail.

GPS-based distance is unreliable in some regions, so an authorised Team Lead may override a trip's
distance. The original GPS value (trk.trip.gps_distance_km) is NEVER overwritten: the manual value
goes in a new nullable column (adjusted_distance_km) and every change is appended to the immutable
log trk.trip_distance_adjustment (who, when, before, after, reason). Reporting takes the effective
distance as COALESCE(adjusted_distance_km, map_distance_km, gps_distance_km).

Only holders of the new trk.trip.adjust permission may adjust (Team Lead / Sales Manager / Admin);
the existing trk.trip.view.team stays read-only.

Additive and reversible: new nullable column + new flag with a default, a new table, and a permission.

Revision ID: 0008
Revises: 0006_trk_trip_tracking
Created: 2026-10-31
"""

from alembic import op

revision = "0008"
down_revision = "0006_trk_trip_tracking"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ---- trk.trip: the manual value lives beside the untouched GPS value ----
    op.execute("""
        ALTER TABLE [trk].[trip] ADD
            [adjusted_distance_km] DECIMAL(8,2) NULL,
            [is_distance_adjusted] BIT NOT NULL
                CONSTRAINT [DF_trk_trip_is_distance_adjusted] DEFAULT (0);
    """)
    op.execute("""
        ALTER TABLE [trk].[trip] ADD CONSTRAINT [CK_trk_trip_adjusted_distance_km]
            CHECK ([adjusted_distance_km] IS NULL OR [adjusted_distance_km] >= 0);
    """)

    # ---- immutable audit log: one row per adjustment (append-only, keeps full history) ----
    op.execute("""
        CREATE TABLE [trk].[trip_distance_adjustment] (
            [id] BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT [PK_trk_trip_distance_adjustment] PRIMARY KEY,
            [trip_id] BIGINT NOT NULL,
            [previous_distance_km] DECIMAL(8,2) NULL,
            [new_distance_km] DECIMAL(8,2) NOT NULL,
            [gps_distance_km_at_adjustment] DECIMAL(8,2) NULL,
            [reason] NVARCHAR(500) NOT NULL,
            [adjusted_by_user_id] BIGINT NOT NULL,
            [adjusted_at] DATETIME2(0) NOT NULL
                CONSTRAINT [DF_trk_trip_distance_adjustment_adjusted_at] DEFAULT (SYSUTCDATETIME()),
            CONSTRAINT [CK_trk_trip_distance_adjustment_new_distance_km] CHECK ([new_distance_km] >= 0),
            CONSTRAINT [FK_trk_trip_distance_adjustment_trip_id]
                FOREIGN KEY ([trip_id]) REFERENCES [trk].[trip] ([id])
        );
    """)
    op.execute("""
        CREATE NONCLUSTERED INDEX [IX_trk_trip_distance_adjustment_trip_id]
            ON [trk].[trip_distance_adjustment] ([trip_id], [adjusted_at] DESC);
    """)

    # ---- permission: only authorised roles may adjust (view.team stays read-only) ----
    op.execute("""
        IF NOT EXISTS (SELECT 1 FROM [core].[permission] WHERE [code] = N'trk.trip.adjust')
            INSERT INTO [core].[permission] ([code], [module], [description])
            VALUES (N'trk.trip.adjust', N'Tracking', N'Manually adjust a trip''s recorded distance (Team Lead)');
    """)
    op.execute("""
        INSERT INTO [core].[role_permission] ([role_id], [permission_id])
        SELECT r.[id], p.[id]
        FROM [core].[role] r
        JOIN [core].[permission] p ON p.[code] = N'trk.trip.adjust'
        WHERE r.[code] IN (N'TEAM_LEAD', N'SALES_MANAGER', N'ADMIN')
          AND NOT EXISTS (SELECT 1 FROM [core].[role_permission] rp
                          WHERE rp.[role_id] = r.[id] AND rp.[permission_id] = p.[id]);
    """)


def downgrade() -> None:
    op.execute("""
        DELETE rp FROM [core].[role_permission] rp
        JOIN [core].[permission] p ON p.[id] = rp.[permission_id]
        WHERE p.[code] = N'trk.trip.adjust';
        DELETE FROM [core].[permission] WHERE [code] = N'trk.trip.adjust';
    """)
    op.execute("DROP TABLE IF EXISTS [trk].[trip_distance_adjustment];")
    op.execute("""
        IF EXISTS (SELECT 1 FROM sys.check_constraints WHERE [name] = N'CK_trk_trip_adjusted_distance_km')
            ALTER TABLE [trk].[trip] DROP CONSTRAINT [CK_trk_trip_adjusted_distance_km];
        IF EXISTS (SELECT 1 FROM sys.default_constraints WHERE [name] = N'DF_trk_trip_is_distance_adjusted')
            ALTER TABLE [trk].[trip] DROP CONSTRAINT [DF_trk_trip_is_distance_adjusted];
    """)
    op.execute("ALTER TABLE [trk].[trip] DROP COLUMN [is_distance_adjusted], [adjusted_distance_km];")
