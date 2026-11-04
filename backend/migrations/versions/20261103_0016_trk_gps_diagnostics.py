"""GPS diagnostic events of a trip: why the GPS trail has gaps, and whether tracking recovered.

trk.trip_gps_point says WHERE the engineer was; it cannot say why two fixes are minutes apart. The
mobile app records diagnostic events while tracking (callback silence, recovery attempted / succeeded,
GPS or permission toggled, process restarted, power-save on, ...) together with the device state, and
uploads them in batches, possibly after the trip ended. Stored centrally they let tracking reliability be
analysed across engineers, devices, manufacturers and Android versions.

  * trk.gps_diagnostic_event_type   master list of event types (new types need no deploy).
  * trk.trip_gps_diagnostic         one row per event. The client-generated event_id is unique per trip,
                                    so a retried batch is deduplicated. Device-state flags are nullable:
                                    NULL means the device could not tell, which is not the same as false.

Additive and reversible: two new tables.

Revision ID: 0016_trk_gps_diagnostics
Revises: 0015_byd_import_log
Created: 2026-11-03
"""

from alembic import op

revision = "0016_trk_gps_diagnostics"
down_revision = "0015_byd_import_log"
branch_labels = None
depends_on = None

_EVENT_TYPES = [
    (
        "LOCATION_CALLBACK_SILENCE",
        "Location callback silence",
        "No location callback for longer than the watchdog limit",
    ),
    ("LOCATION_RECOVERY_ATTEMPTED", "Location recovery attempted", "Location updates were re-registered"),
    ("LOCATION_RECOVERY_SUCCEEDED", "Location recovery succeeded", "Location callbacks resumed after recovery"),
    ("GPS_DISABLED", "GPS disabled", "Location services were switched off"),
    ("GPS_ENABLED", "GPS enabled", "Location services were switched on"),
    ("LOCATION_PERMISSION_DENIED", "Location permission denied", "Location permission was revoked"),
    ("LOCATION_PERMISSION_GRANTED", "Location permission granted", "Location permission was granted"),
    ("PROCESS_RESTARTED", "Process restarted", "The app process was restarted while tracking"),
    ("NETWORK_DISABLED", "Network disabled", "Network connectivity was lost"),
    ("NETWORK_ENABLED", "Network enabled", "Network connectivity was restored"),
    ("POWER_SAVE_ENABLED", "Power save enabled", "Battery saver was switched on"),
    ("POWER_SAVE_DISABLED", "Power save disabled", "Battery saver was switched off"),
    ("STATIONARY_CONFIRMED", "Stationary confirmed", "The device was confirmed to be standing still"),
    ("MOVEMENT_RESUMED", "Movement resumed", "The device started moving again"),
]


def upgrade() -> None:
    op.execute("""
        CREATE TABLE [trk].[gps_diagnostic_event_type] (
            [id] BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT [PK_trk_gps_diagnostic_event_type] PRIMARY KEY,
            [code] NVARCHAR(40) NOT NULL,
            [name] NVARCHAR(60) NOT NULL,
            [description] NVARCHAR(200) NULL,
            [sort_order] INT NOT NULL CONSTRAINT [DF_trk_gps_diagnostic_event_type_sort_order] DEFAULT (0),
            [is_system] BIT NOT NULL CONSTRAINT [DF_trk_gps_diagnostic_event_type_is_system] DEFAULT (0),
            [created_at] DATETIME2(0) NOT NULL
                CONSTRAINT [DF_trk_gps_diagnostic_event_type_created_at] DEFAULT (SYSUTCDATETIME()),
            [created_by_user_id] BIGINT NULL,
            [updated_at] DATETIME2(0) NULL,
            [updated_by_user_id] BIGINT NULL,
            [is_active] BIT NOT NULL CONSTRAINT [DF_trk_gps_diagnostic_event_type_is_active] DEFAULT (1),
            [row_version] ROWVERSION NOT NULL,
            CONSTRAINT [UQ_trk_gps_diagnostic_event_type_code] UNIQUE ([code])
        );
    """)
    for order, (code, name, description) in enumerate(_EVENT_TYPES, start=1):
        op.execute(
            f"""
            INSERT INTO [trk].[gps_diagnostic_event_type] ([code], [name], [description], [sort_order])
            SELECT N'{code}', N'{name}', N'{description}', {order}
            WHERE NOT EXISTS (SELECT 1 FROM [trk].[gps_diagnostic_event_type] WHERE [code] = N'{code}');
        """  # noqa: S608 - module constants, not user input
        )

    op.execute("""
        CREATE TABLE [trk].[trip_gps_diagnostic] (
            [id] BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT [PK_trk_trip_gps_diagnostic] PRIMARY KEY,
            [trip_id] BIGINT NOT NULL,
            [event_id] UNIQUEIDENTIFIER NOT NULL,
            [event_type] NVARCHAR(40) NOT NULL,
            [recorded_at] DATETIME2(3) NOT NULL,
            [duration_seconds] DECIMAL(9,1) NULL,
            [gps_enabled] BIT NULL,
            [permission_granted] BIT NULL,
            [battery_exempted] BIT NULL,
            [power_save_mode] BIT NULL,
            [device_idle_mode] BIT NULL,
            [network_connected] BIT NULL,
            [call_state] NVARCHAR(20) NULL,
            [manufacturer] NVARCHAR(60) NULL,
            [model] NVARCHAR(100) NULL,
            [os_name] NVARCHAR(20) NULL,
            [os_version] NVARCHAR(30) NULL,
            [details] NVARCHAR(500) NULL,
            [latitude] DECIMAL(9,6) NULL,
            [longitude] DECIMAL(9,6) NULL,
            [accuracy_m] DECIMAL(6,1) NULL,
            [received_at] DATETIME2(0) NOT NULL
                CONSTRAINT [DF_trk_trip_gps_diagnostic_received_at] DEFAULT (SYSUTCDATETIME()),
            CONSTRAINT [FK_trk_trip_gps_diagnostic_trip_id]
                FOREIGN KEY ([trip_id]) REFERENCES [trk].[trip] ([id]) ON DELETE CASCADE,
            CONSTRAINT [FK_trk_trip_gps_diagnostic_event_type]
                FOREIGN KEY ([event_type]) REFERENCES [trk].[gps_diagnostic_event_type] ([code]),
            CONSTRAINT [CK_trk_trip_gps_diagnostic_duration_seconds]
                CHECK ([duration_seconds] IS NULL OR [duration_seconds] >= 0)
        );
    """)
    # Dedup: a retried batch repeats the same client-generated event ids.
    op.execute("""
        CREATE UNIQUE NONCLUSTERED INDEX [UX_trk_trip_gps_diagnostic_event_id]
            ON [trk].[trip_gps_diagnostic] ([trip_id], [event_id]);
    """)
    op.execute("""
        CREATE NONCLUSTERED INDEX [IX_trk_trip_gps_diagnostic_trip_recorded]
            ON [trk].[trip_gps_diagnostic] ([trip_id], [recorded_at]);
    """)
    # Fleet analysis: how often does an event type occur, per manufacturer, over time.
    op.execute("""
        CREATE NONCLUSTERED INDEX [IX_trk_trip_gps_diagnostic_type_recorded]
            ON [trk].[trip_gps_diagnostic] ([event_type], [recorded_at]) INCLUDE ([manufacturer], [os_version]);
    """)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS [trk].[trip_gps_diagnostic];")
    op.execute("DROP TABLE IF EXISTS [trk].[gps_diagnostic_event_type];")
