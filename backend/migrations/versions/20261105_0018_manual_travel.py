"""Manual travel entries (Bus / Train / Other) and the GPS-tracked flag on vehicle types.

GPS-tracked vehicles (Own bike, Own car, Company vehicle) keep the trip workflow. Vehicles with
is_gps_tracked = 0 have no Start / Stop trip: the engineer records the kilometres by hand in
trk.manual_travel. Both are linked to the service call and the engineer, and trk.v_service_call_travel
presents them as one list for reporting and reimbursement.

Supporting tickets are attached through the common core.attachment table (entity_type
'trk.manual_travel'); there is no travel-specific upload table.

Idempotent on purpose: every statement checks first, so it is safe to run more than once.

Revision ID: 0018_manual_travel
Revises: 0016_trk_gps_diagnostics
Created: 2026-11-05
"""

from alembic import op

revision = "0018_manual_travel"
down_revision = "0016_trk_gps_diagnostics"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        -- Unbracketed on purpose: trk.trip_vehicle_type is created by a helper in migration 0012 that the
        -- model generator does not parse, and its model is hand-written (db/models/trk.py).
        IF COL_LENGTH('trk.trip_vehicle_type', 'is_gps_tracked') IS NULL
            ALTER TABLE trk.trip_vehicle_type ADD is_gps_tracked BIT NOT NULL
                CONSTRAINT DF_trk_trip_vehicle_type_is_gps_tracked DEFAULT (1) WITH VALUES;
    """)
    # The column is created by the batch above, so the seed runs as separate dynamic SQL.
    op.execute("""
        EXEC(N'
        INSERT INTO [trk].[trip_vehicle_type] ([code], [name], [description], [sort_order], [is_gps_tracked])
        SELECT v.* FROM (VALUES
            (N''Bus'', N''Bus'', N''Non-tracking travel: kilometres entered manually'', 5, 0),
            (N''Train'', N''Train'', N''Non-tracking travel: kilometres entered manually'', 6, 0),
            (N''Other'', N''Other'', N''Non-tracking travel: kilometres entered manually'', 7, 0)
        ) v([code], [name], [description], [sort_order], [is_gps_tracked])
        WHERE NOT EXISTS (SELECT 1 FROM [trk].[trip_vehicle_type] x WHERE x.[code] = v.[code]);
        ');
    """)
    op.execute("""
        IF OBJECT_ID('trk.manual_travel', 'U') IS NULL
        CREATE TABLE [trk].[manual_travel] (
            [id] BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT [PK_trk_manual_travel] PRIMARY KEY,
            [service_call_id] BIGINT NOT NULL
                CONSTRAINT [FK_trk_manual_travel_service_call] REFERENCES [svc].[service_call] ([id]),
            [employee_id] BIGINT NOT NULL
                CONSTRAINT [FK_trk_manual_travel_employee] REFERENCES [core].[employee] ([id]),
            [vehicle_type] NVARCHAR(30) NOT NULL
                CONSTRAINT [FK_trk_manual_travel_vehicle_type] REFERENCES [trk].[trip_vehicle_type] ([code]),
            [travel_date] DATE NOT NULL,
            [distance_km] DECIMAL(8,2) NOT NULL,
            [notes] NVARCHAR(500) NULL,
            [client_uuid] UNIQUEIDENTIFIER NULL,
            [created_at] DATETIME2(0) NOT NULL CONSTRAINT [DF_trk_manual_travel_created_at] DEFAULT (SYSUTCDATETIME()),
            [created_by_user_id] BIGINT NULL,
            [updated_at] DATETIME2(0) NULL,
            [updated_by_user_id] BIGINT NULL,
            [is_active] BIT NOT NULL CONSTRAINT [DF_trk_manual_travel_is_active] DEFAULT (1),
            [row_version] ROWVERSION NOT NULL,
            CONSTRAINT [CK_trk_manual_travel_distance] CHECK ([distance_km] > 0 AND [distance_km] <= 5000)
        );
    """)
    op.execute("""
        IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'IX_trk_manual_travel_service_call_id')
            CREATE NONCLUSTERED INDEX [IX_trk_manual_travel_service_call_id]
                ON [trk].[manual_travel] ([service_call_id], [travel_date]);
        IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'IX_trk_manual_travel_employee_id')
            CREATE NONCLUSTERED INDEX [IX_trk_manual_travel_employee_id]
                ON [trk].[manual_travel] ([employee_id], [travel_date]);
        IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'UX_trk_manual_travel_client_uuid')
            CREATE UNIQUE NONCLUSTERED INDEX [UX_trk_manual_travel_client_uuid]
                ON [trk].[manual_travel] ([client_uuid]) WHERE [client_uuid] IS NOT NULL;
    """)
    # One travel list per service call, whatever the workflow. A GPS trip reaches its call through
    # trackable_activity -> service_visit; the view hides that join for reports.
    op.execute("""
        CREATE OR ALTER VIEW [trk].[v_service_call_travel] AS
        SELECT N'GPS' AS [record_source], t.[id] AS [record_id], v.[service_call_id], t.[employee_id],
               t.[vehicle_type], CAST(t.[start_at] AS DATE) AS [travel_date],
               COALESCE(t.[adjusted_distance_km], t.[map_distance_km], t.[gps_distance_km]) AS [distance_km],
               t.[status] AS [status]
        FROM [trk].[trip] t
        JOIN [trk].[trackable_activity] a ON a.[id] = t.[trackable_activity_id]
            AND a.[module_code] = N'SVC' AND a.[source_table] = N'service_visit'
        JOIN [svc].[service_visit] v ON v.[id] = a.[source_id]
        WHERE t.[is_active] = 1
        UNION ALL
        SELECT N'Manual', m.[id], m.[service_call_id], m.[employee_id], m.[vehicle_type], m.[travel_date],
               m.[distance_km], N'Recorded'
        FROM [trk].[manual_travel] m
        WHERE m.[is_active] = 1;
    """)


def downgrade() -> None:
    op.execute("DROP VIEW IF EXISTS [trk].[v_service_call_travel];")
    op.execute("DROP TABLE IF EXISTS [trk].[manual_travel];")
    op.execute("""
        DELETE FROM [trk].[trip_vehicle_type] WHERE [code] IN (N'Bus', N'Train', N'Other')
            AND NOT EXISTS (SELECT 1 FROM [trk].[trip] WHERE [vehicle_type] IN (N'Bus', N'Train', N'Other'));
        IF COL_LENGTH('trk.trip_vehicle_type', 'is_gps_tracked') IS NOT NULL
        BEGIN
            ALTER TABLE trk.trip_vehicle_type DROP CONSTRAINT DF_trk_trip_vehicle_type_is_gps_tracked;
            ALTER TABLE trk.trip_vehicle_type DROP COLUMN is_gps_tracked;
        END
    """)
