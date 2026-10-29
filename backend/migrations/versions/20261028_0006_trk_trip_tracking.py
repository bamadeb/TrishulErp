"""Common, cross-module trip tracking: the trk schema (trackable_activity, trip, trip_gps_point).

A trip no longer hangs off svc.service_visit directly; it hangs off trk.trackable_activity, a
polymorphic registry each module writes a row into (module_code + source_table + source_id). This
makes trip tracking reusable by Service, Pre-Sales and future modules with real foreign keys.

Existing svc.trip / svc.trip_gps_point rows are copied into trk (a trackable_activity is created per
referenced service_visit). The old svc tables are LEFT IN PLACE (deprecated) so nothing breaks and the
step is reversible; drop them in a later migration once trk is confirmed.

NOTE: chains from 0005_presales_assigned. The live DB's alembic_version was stamped at an unrelated
revision 0005 from another branch — reconcile the heads with `alembic merge` before upgrading.

Revision ID: 0006_trk_trip_tracking
Revises: 0005_presales_assigned
Created: 2026-10-28
"""

from alembic import op

revision = "0006_trk_trip_tracking"
down_revision = "0005_presales_assigned"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("IF SCHEMA_ID(N'trk') IS NULL EXEC(N'CREATE SCHEMA [trk]');")

    op.execute("""
        CREATE TABLE [trk].[trackable_activity] (
            [id] BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT [PK_trk_trackable_activity] PRIMARY KEY,
            [module_code] NVARCHAR(10) NOT NULL,
            [activity_kind] NVARCHAR(40) NULL,
            [source_schema] NVARCHAR(10) NOT NULL,
            [source_table] NVARCHAR(60) NOT NULL,
            [source_id] BIGINT NOT NULL,
            [employee_id] BIGINT NOT NULL,
            [customer_id] BIGINT NULL,
            [title] NVARCHAR(200) NULL,
            [target_latitude] DECIMAL(9,6) NULL,
            [target_longitude] DECIMAL(9,6) NULL,
            [geofence_radius_m] INT NULL,
            [client_uuid] UNIQUEIDENTIFIER NULL,
            [created_at] DATETIME2(0) NOT NULL CONSTRAINT [DF_trk_trackable_activity_created_at] DEFAULT (SYSUTCDATETIME()),
            [created_by_user_id] BIGINT NULL,
            [updated_at] DATETIME2(0) NULL,
            [updated_by_user_id] BIGINT NULL,
            [is_active] BIT NOT NULL CONSTRAINT [DF_trk_trackable_activity_is_active] DEFAULT (1),
            [row_version] ROWVERSION NOT NULL,
            CONSTRAINT [CK_trk_trackable_activity_module_code] CHECK ([module_code] IN (N'SVC', N'PRE')),
            CONSTRAINT [FK_trk_trackable_activity_employee_id] FOREIGN KEY ([employee_id]) REFERENCES [core].[employee] ([id]),
            CONSTRAINT [FK_trk_trackable_activity_customer_id] FOREIGN KEY ([customer_id]) REFERENCES [core].[customer] ([id])
        );
    """)
    op.execute("""
        CREATE UNIQUE NONCLUSTERED INDEX [UX_trk_trackable_activity_source]
            ON [trk].[trackable_activity] ([module_code], [source_table], [source_id]);
    """)
    op.execute("""
        CREATE UNIQUE NONCLUSTERED INDEX [UX_trk_trackable_activity_client_uuid]
            ON [trk].[trackable_activity] ([client_uuid]) WHERE [client_uuid] IS NOT NULL;
    """)
    op.execute("CREATE NONCLUSTERED INDEX [IX_trk_trackable_activity_employee_id] ON [trk].[trackable_activity] ([employee_id]);")

    op.execute("""
        CREATE TABLE [trk].[trip] (
            [id] BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT [PK_trk_trip] PRIMARY KEY,
            [trackable_activity_id] BIGINT NOT NULL,
            [employee_id] BIGINT NOT NULL,
            [user_device_id] BIGINT NULL,
            [client_uuid] UNIQUEIDENTIFIER NULL,
            [trip_type] NVARCHAR(30) NOT NULL,
            [start_at] DATETIME2(0) NOT NULL,
            [start_latitude] DECIMAL(9,6) NOT NULL,
            [start_longitude] DECIMAL(9,6) NOT NULL,
            [end_at] DATETIME2(0) NULL,
            [end_latitude] DECIMAL(9,6) NULL,
            [end_longitude] DECIMAL(9,6) NULL,
            [gps_distance_km] DECIMAL(8,2) NULL,
            [map_distance_km] DECIMAL(8,2) NULL,
            [duration_minutes] INT NULL,
            [vehicle_type] NVARCHAR(30) NULL,
            [status] NVARCHAR(30) NOT NULL,
            [route_polyline] NVARCHAR(MAX) NULL,
            [created_at] DATETIME2(0) NOT NULL CONSTRAINT [DF_trk_trip_created_at] DEFAULT (SYSUTCDATETIME()),
            [created_by_user_id] BIGINT NULL,
            [updated_at] DATETIME2(0) NULL,
            [updated_by_user_id] BIGINT NULL,
            [is_active] BIT NOT NULL CONSTRAINT [DF_trk_trip_is_active] DEFAULT (1),
            [row_version] ROWVERSION NOT NULL,
            CONSTRAINT [CK_trk_trip_trip_type] CHECK ([trip_type] IN (N'To site', N'Return', N'Site to site')),
            CONSTRAINT [CK_trk_trip_vehicle_type] CHECK ([vehicle_type] IN (N'Own bike', N'Own car', N'Company vehicle', N'Public transport')),
            CONSTRAINT [CK_trk_trip_status] CHECK ([status] IN (N'In progress', N'Completed', N'Auto closed')),
            CONSTRAINT [FK_trk_trip_trackable_activity_id] FOREIGN KEY ([trackable_activity_id]) REFERENCES [trk].[trackable_activity] ([id]),
            CONSTRAINT [FK_trk_trip_employee_id] FOREIGN KEY ([employee_id]) REFERENCES [core].[employee] ([id]),
            CONSTRAINT [FK_trk_trip_user_device_id] FOREIGN KEY ([user_device_id]) REFERENCES [core].[user_device] ([id])
        );
    """)
    op.execute("""
        CREATE UNIQUE NONCLUSTERED INDEX [UX_trk_trip_client_uuid]
            ON [trk].[trip] ([client_uuid]) WHERE [client_uuid] IS NOT NULL;
    """)
    op.execute("CREATE NONCLUSTERED INDEX [IX_trk_trip_trackable_activity_id] ON [trk].[trip] ([trackable_activity_id]);")
    op.execute("CREATE NONCLUSTERED INDEX [IX_trk_trip_employee_id] ON [trk].[trip] ([employee_id]);")
    # One active trip per employee at a time (enforced here as well as in the service layer).
    op.execute("""
        CREATE UNIQUE NONCLUSTERED INDEX [UX_trk_trip_one_active_per_employee]
            ON [trk].[trip] ([employee_id]) WHERE [status] = N'In progress' AND [is_active] = 1;
    """)

    op.execute("""
        CREATE TABLE [trk].[trip_gps_point] (
            [id] BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT [PK_trk_trip_gps_point] PRIMARY KEY,
            [trip_id] BIGINT NOT NULL,
            [recorded_at] DATETIME2(0) NOT NULL,
            [latitude] DECIMAL(9,6) NOT NULL,
            [longitude] DECIMAL(9,6) NOT NULL,
            [accuracy_m] DECIMAL(6,1) NULL,
            [speed_kmph] DECIMAL(5,1) NULL,
            [battery_pct] TINYINT NULL,
            [is_mock_location] BIT NOT NULL CONSTRAINT [DF_trk_trip_gps_point_is_mock_location] DEFAULT (0),
            [received_at] DATETIME2(0) NOT NULL CONSTRAINT [DF_trk_trip_gps_point_received_at] DEFAULT (SYSUTCDATETIME()),
            CONSTRAINT [FK_trk_trip_gps_point_trip_id] FOREIGN KEY ([trip_id]) REFERENCES [trk].[trip] ([id]) ON DELETE CASCADE
        );
    """)
    # Dedup: a retried upload of the same point (same trip + capture time) is ignored.
    op.execute("""
        CREATE UNIQUE NONCLUSTERED INDEX [UX_trk_trip_gps_point_dedup]
            ON [trk].[trip_gps_point] ([trip_id], [recorded_at]);
    """)

    # ---- migrate existing svc.trip data into trk (old tables kept, deprecated) ----
    op.execute("""
        INSERT INTO [trk].[trackable_activity]
            ([module_code], [activity_kind], [source_schema], [source_table], [source_id],
             [employee_id], [customer_id], [title], [target_latitude], [target_longitude], [created_by_user_id])
        SELECT DISTINCT N'SVC', N'Service visit', N'svc', N'service_visit', sv.[id],
               sv.[engineer_employee_id], sc.[customer_id], sc.[call_no], sv.[site_latitude], sv.[site_longitude],
               sv.[created_by_user_id]
        FROM [svc].[trip] t
        JOIN [svc].[service_visit] sv ON sv.[id] = t.[service_visit_id]
        JOIN [svc].[service_call] sc ON sc.[id] = sv.[service_call_id]
        WHERE NOT EXISTS (SELECT 1 FROM [trk].[trackable_activity] ta
                          WHERE ta.[module_code] = N'SVC' AND ta.[source_table] = N'service_visit'
                            AND ta.[source_id] = sv.[id]);
    """)
    op.execute("""
        CREATE TABLE #trip_map ([old_id] BIGINT, [new_id] BIGINT);
        MERGE INTO [trk].[trip] AS tgt
        USING (
            SELECT t.*, ta.[id] AS activity_id
            FROM [svc].[trip] t
            JOIN [trk].[trackable_activity] ta
              ON ta.[module_code] = N'SVC' AND ta.[source_table] = N'service_visit'
             AND ta.[source_id] = t.[service_visit_id]
        ) AS src
        ON 1 = 0
        WHEN NOT MATCHED THEN
          INSERT ([trackable_activity_id], [employee_id], [client_uuid], [trip_type], [start_at],
                  [start_latitude], [start_longitude], [end_at], [end_latitude], [end_longitude],
                  [gps_distance_km], [map_distance_km], [duration_minutes], [vehicle_type], [status],
                  [route_polyline], [created_at], [created_by_user_id], [updated_at], [updated_by_user_id], [is_active])
          VALUES (src.activity_id, src.[engineer_employee_id], src.[client_uuid], src.[trip_type], src.[start_at],
                  src.[start_latitude], src.[start_longitude], src.[end_at], src.[end_latitude], src.[end_longitude],
                  src.[gps_distance_km], src.[map_distance_km], src.[duration_minutes], src.[vehicle_type], src.[status],
                  src.[route_polyline], src.[created_at], src.[created_by_user_id], src.[updated_at],
                  src.[updated_by_user_id], src.[is_active])
          OUTPUT src.[id], inserted.[id] INTO #trip_map ([old_id], [new_id]);
        INSERT INTO [trk].[trip_gps_point]
            ([trip_id], [recorded_at], [latitude], [longitude], [accuracy_m], [speed_kmph], [battery_pct], [is_mock_location])
        SELECT m.[new_id], g.[recorded_at], g.[latitude], g.[longitude], g.[accuracy_m], g.[speed_kmph],
               g.[battery_pct], g.[is_mock_location]
        FROM [svc].[trip_gps_point] g
        JOIN #trip_map m ON m.[old_id] = g.[trip_id];
        DROP TABLE #trip_map;
    """)

    # ---- permissions ----
    op.execute("""
        IF NOT EXISTS (SELECT 1 FROM [core].[permission] WHERE [code] = N'trk.trip.manage')
            INSERT INTO [core].[permission] ([code], [module], [description])
            VALUES (N'trk.trip.manage', N'Tracking', N'Start, update and stop one''s own trips (mobile)');
        IF NOT EXISTS (SELECT 1 FROM [core].[permission] WHERE [code] = N'trk.trip.view.team')
            INSERT INTO [core].[permission] ([code], [module], [description])
            VALUES (N'trk.trip.view.team', N'Tracking', N'Review trips of the team / branch');
    """)
    op.execute("""
        INSERT INTO [core].[role_permission] ([role_id], [permission_id])
        SELECT r.[id], p.[id] FROM [core].[role] r
        JOIN [core].[permission] p ON p.[code] = N'trk.trip.manage'
        WHERE r.[code] IN (N'SERVICE_ENGINEER', N'SALESPERSON', N'ADMIN')
          AND NOT EXISTS (SELECT 1 FROM [core].[role_permission] rp
                          WHERE rp.[role_id] = r.[id] AND rp.[permission_id] = p.[id]);
        INSERT INTO [core].[role_permission] ([role_id], [permission_id])
        SELECT r.[id], p.[id] FROM [core].[role] r
        JOIN [core].[permission] p ON p.[code] = N'trk.trip.view.team'
        WHERE r.[code] IN (N'TEAM_LEAD', N'SALES_MANAGER', N'BACK_OFFICE', N'ADMIN', N'MANAGEMENT')
          AND NOT EXISTS (SELECT 1 FROM [core].[role_permission] rp
                          WHERE rp.[role_id] = r.[id] AND rp.[permission_id] = p.[id]);
    """)


def downgrade() -> None:
    op.execute("""
        DELETE rp FROM [core].[role_permission] rp
        JOIN [core].[permission] p ON p.[id] = rp.[permission_id]
        WHERE p.[code] IN (N'trk.trip.manage', N'trk.trip.view.team');
        DELETE FROM [core].[permission] WHERE [code] IN (N'trk.trip.manage', N'trk.trip.view.team');
    """)
    op.execute("DROP TABLE IF EXISTS [trk].[trip_gps_point];")
    op.execute("DROP TABLE IF EXISTS [trk].[trip];")
    op.execute("DROP TABLE IF EXISTS [trk].[trackable_activity];")
    op.execute("IF SCHEMA_ID(N'trk') IS NOT NULL EXEC(N'DROP SCHEMA [trk]');")
