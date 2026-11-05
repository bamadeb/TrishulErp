"""Tracking configuration the mobile app fetches instead of hard-coding.

trk.tracking_config holds one row per parameter. value is stored as text and typed by value_type;
a NULL value means "to be calibrated" (the app keeps using its own safe behaviour for it). min_value,
max_value and allowed_values are what the update API validates against, so an administrator cannot
save a value the phone cannot use.

Permission trk.config.manage (Admin) lets a user read the parameter list and change values; reading the
current configuration needs only a sign-in, like the other trip master data.

Idempotent: every statement checks first.

Revision ID: 0021_tracking_config
Revises: 0020_merge_asc_manual_travel
Created: 2026-11-05
"""

from alembic import op

revision = "0021_tracking_config"
down_revision = "0020_merge_asc_manual_travel"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        IF OBJECT_ID('trk.tracking_config', 'U') IS NULL
        CREATE TABLE [trk].[tracking_config] (
            [id] BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT [PK_trk_tracking_config] PRIMARY KEY,
            [code] NVARCHAR(60) NOT NULL,
            [name] NVARCHAR(100) NOT NULL,
            [description] NVARCHAR(300) NULL,
            [value_type] NVARCHAR(10) NOT NULL,
            [value] NVARCHAR(100) NULL,
            [default_value] NVARCHAR(100) NULL,
            [unit] NVARCHAR(10) NULL,
            [min_value] DECIMAL(18,4) NULL,
            [max_value] DECIMAL(18,4) NULL,
            [allowed_values] NVARCHAR(200) NULL,
            [sort_order] INT NOT NULL CONSTRAINT [DF_trk_tracking_config_sort_order] DEFAULT (0),
            [created_at] DATETIME2(0) NOT NULL CONSTRAINT [DF_trk_tracking_config_created_at] DEFAULT (SYSUTCDATETIME()),
            [created_by_user_id] BIGINT NULL,
            [updated_at] DATETIME2(0) NULL,
            [updated_by_user_id] BIGINT NULL,
            [is_active] BIT NOT NULL CONSTRAINT [DF_trk_tracking_config_is_active] DEFAULT (1),
            [row_version] ROWVERSION NOT NULL,
            CONSTRAINT [UQ_trk_tracking_config_code] UNIQUE ([code]),
            CONSTRAINT [CK_trk_tracking_config_value_type] CHECK ([value_type] IN (N'int', N'decimal', N'string'))
        );
    """)
    op.execute("""
        INSERT INTO [trk].[tracking_config]
            ([code], [name], [description], [value_type], [value], [default_value], [unit],
             [min_value], [max_value], [allowed_values], [sort_order])
        SELECT v.* FROM (VALUES
            (N'movingIntervalMs', N'Moving: location interval',
             N'How often the phone asks for a location while the engineer is moving.',
             N'int', N'3000', N'3000', N'ms', 500, 60000, NULL, 1),
            (N'movingPriority', N'Moving: location priority',
             N'Accuracy / battery trade-off used while moving (Android fused-location priority).',
             N'string', N'HIGH_ACCURACY', N'HIGH_ACCURACY', NULL, NULL, NULL,
             N'HIGH_ACCURACY,BALANCED_POWER_ACCURACY,LOW_POWER,PASSIVE', 2),
            (N'stationaryCandidateDurationMs', N'Stationary: candidate duration',
             N'How long the phone must stay inside the dwell radius before it counts as stationary.',
             N'int', N'180000', N'180000', N'ms', 10000, 3600000, NULL, 3),
            (N'stationaryDwellRadiusMeters', N'Stationary: dwell radius',
             N'Radius around the first point within which the phone is considered not to have moved.',
             N'decimal', N'35', N'35', N'm', 5, 500, NULL, 4),
            (N'movementRecoveryDisplacementMeters', N'Movement recovery: displacement',
             N'Distance from the stationary point after which the phone is considered moving again.',
             N'decimal', N'25', N'25', N'm', 5, 500, NULL, 5),
            (N'varianceThresholdMoving', N'Moving: variance threshold',
             N'Sensor variance above which the phone is considered moving. To be calibrated.',
             N'decimal', NULL, NULL, NULL, 0, NULL, NULL, 6),
            (N'varianceThresholdStationary', N'Stationary: variance threshold',
             N'Sensor variance below which the phone is considered stationary. To be calibrated.',
             N'decimal', NULL, NULL, NULL, 0, NULL, NULL, 7),
            (N'samplingPeriodUs', N'Sensor sampling period',
             N'Motion-sensor sampling period (Android samplingPeriodUs). To be calibrated.',
             N'int', NULL, NULL, N'us', 1000, 1000000, NULL, 8)
        ) v([code], [name], [description], [value_type], [value], [default_value], [unit],
            [min_value], [max_value], [allowed_values], [sort_order])
        WHERE NOT EXISTS (SELECT 1 FROM [trk].[tracking_config] x WHERE x.[code] = v.[code]);
    """)
    op.execute("""
        IF NOT EXISTS (SELECT 1 FROM [core].[permission] WHERE [code] = N'trk.config.manage')
            INSERT INTO [core].[permission] ([code], [module], [description])
            VALUES (N'trk.config.manage', N'Tracking', N'See and change the trip-tracking configuration the mobile app fetches');
    """)
    op.execute("""
        INSERT INTO [core].[role_permission] ([role_id], [permission_id])
        SELECT r.[id], p.[id]
        FROM [core].[role] r
        JOIN [core].[permission] p ON p.[code] = N'trk.config.manage'
        WHERE r.[code] = N'ADMIN'
          AND NOT EXISTS (
            SELECT 1 FROM [core].[role_permission] rp
            WHERE rp.[role_id] = r.[id] AND rp.[permission_id] = p.[id]);
    """)


def downgrade() -> None:
    op.execute("""
        DELETE rp FROM [core].[role_permission] rp
        JOIN [core].[permission] p ON p.[id] = rp.[permission_id]
        WHERE p.[code] = N'trk.config.manage';
        DELETE FROM [core].[permission] WHERE [code] = N'trk.config.manage';
    """)
    op.execute("DROP TABLE IF EXISTS [trk].[tracking_config];")
