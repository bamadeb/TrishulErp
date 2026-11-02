"""Trip-tracking master data: module codes, trip types, vehicle types and trip statuses.

These four value lists were Python Literals plus CHECK constraints. They become tables in the trk
schema, and the trk columns get foreign keys to them. The master `code` IS the value already stored
(N'To site', N'Own bike', N'In progress', N'SVC', ...), so no trip row changes and the API wire values
stay the same.

  trk.trackable_activity_module  <- trk.trackable_activity.module_code
  trk.trip_type                  <- trk.trip.trip_type
  trk.trip_vehicle_type          <- trk.trip.vehicle_type
  trk.trip_status                <- trk.trip.status

Rows with is_system = 1 are used by application logic (In progress / Completed, SVC / PRE) and must
not be deactivated. Order: create, seed, add FKs, drop the CHECK constraints the FKs replace.
Old application code keeps working after this migration (it only writes values that are seeded).

Revision ID: 0012_trk_master_data
Revises: 0011_user_device_os
Created: 2026-11-02
"""

from alembic import op

revision = "0012_trk_master_data"
down_revision = "0011_user_device_os"
branch_labels = None
depends_on = None

_AUDIT_COLUMNS = """
            [is_system] BIT NOT NULL CONSTRAINT [DF_trk_{table}_is_system] DEFAULT (0),
            [created_at] DATETIME2(0) NOT NULL CONSTRAINT [DF_trk_{table}_created_at] DEFAULT (SYSUTCDATETIME()),
            [created_by_user_id] BIGINT NULL,
            [updated_at] DATETIME2(0) NULL,
            [updated_by_user_id] BIGINT NULL,
            [is_active] BIT NOT NULL CONSTRAINT [DF_trk_{table}_is_active] DEFAULT (1),
            [row_version] ROWVERSION NOT NULL"""


def _create(table: str, code_length: int, extra_columns: str = "") -> None:
    op.execute(f"""
        CREATE TABLE [trk].[{table}] (
            [id] BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT [PK_trk_{table}] PRIMARY KEY,
            [code] NVARCHAR({code_length}) NOT NULL,
            [name] NVARCHAR(60) NOT NULL,
            [description] NVARCHAR(200) NULL,
            [sort_order] INT NOT NULL CONSTRAINT [DF_trk_{table}_sort_order] DEFAULT (0),{extra_columns}
            {_AUDIT_COLUMNS.format(table=table).strip()},
            CONSTRAINT [UQ_trk_{table}_code] UNIQUE ([code])
        );
    """)


def upgrade() -> None:
    # ---- tables ----
    _create(
        "trackable_activity_module",
        10,
        """
            [source_schema] NVARCHAR(10) NOT NULL,
            [source_table] NVARCHAR(60) NOT NULL,""",
    )
    _create(
        "trip_type",
        30,
        """
            [is_default] BIT NOT NULL CONSTRAINT [DF_trk_trip_type_is_default] DEFAULT (0),""",
    )
    _create("trip_vehicle_type", 30)
    _create(
        "trip_status",
        30,
        """
            [is_initial] BIT NOT NULL CONSTRAINT [DF_trk_trip_status_is_initial] DEFAULT (0),
            [is_final] BIT NOT NULL CONSTRAINT [DF_trk_trip_status_is_final] DEFAULT (0),""",
    )
    # At most one default trip type.
    op.execute("""
        CREATE UNIQUE NONCLUSTERED INDEX [UX_trk_trip_type_is_default]
            ON [trk].[trip_type] ([is_default]) WHERE [is_default] = 1;
    """)

    # ---- seed (idempotent) ----
    op.execute("""
        INSERT INTO [trk].[trackable_activity_module]
            ([code], [name], [description], [sort_order], [source_schema], [source_table], [is_system])
        SELECT v.* FROM (VALUES
            (N'SVC', N'Service Call', N'Trip to a service call (service visit)', 1, N'svc', N'service_visit', 1),
            (N'PRE', N'Pre-sales Activity', N'Trip to a pre-sales activity', 2, N'pre', N'sales_activity', 1)
        ) v([code], [name], [description], [sort_order], [source_schema], [source_table], [is_system])
        WHERE NOT EXISTS (SELECT 1 FROM [trk].[trackable_activity_module] x WHERE x.[code] = v.[code]);
    """)
    op.execute("""
        INSERT INTO [trk].[trip_type] ([code], [name], [sort_order], [is_default])
        SELECT v.* FROM (VALUES
            (N'To site', N'To site', 1, 1),
            (N'Return', N'Return', 2, 0),
            (N'Site to site', N'Site to site', 3, 0)
        ) v([code], [name], [sort_order], [is_default])
        WHERE NOT EXISTS (SELECT 1 FROM [trk].[trip_type] x WHERE x.[code] = v.[code]);
    """)
    op.execute("""
        INSERT INTO [trk].[trip_vehicle_type] ([code], [name], [sort_order])
        SELECT v.* FROM (VALUES
            (N'Own bike', N'Own bike', 1),
            (N'Own car', N'Own car', 2),
            (N'Company vehicle', N'Company vehicle', 3),
            (N'Public transport', N'Public transport', 4)
        ) v([code], [name], [sort_order])
        WHERE NOT EXISTS (SELECT 1 FROM [trk].[trip_vehicle_type] x WHERE x.[code] = v.[code]);
    """)
    op.execute("""
        INSERT INTO [trk].[trip_status] ([code], [name], [sort_order], [is_initial], [is_final], [is_system])
        SELECT v.* FROM (VALUES
            (N'In progress', N'In progress', 1, 1, 0, 1),
            (N'Completed', N'Completed', 2, 0, 1, 1),
            (N'Auto closed', N'Auto closed', 3, 0, 1, 1)
        ) v([code], [name], [sort_order], [is_initial], [is_final], [is_system])
        WHERE NOT EXISTS (SELECT 1 FROM [trk].[trip_status] x WHERE x.[code] = v.[code]);
    """)

    # ---- foreign keys (existing rows already hold seeded values) ----
    op.execute("""
        ALTER TABLE [trk].[trackable_activity] ADD CONSTRAINT [FK_trk_trackable_activity_module_code]
            FOREIGN KEY ([module_code]) REFERENCES [trk].[trackable_activity_module] ([code]);
        ALTER TABLE [trk].[trip] ADD CONSTRAINT [FK_trk_trip_trip_type]
            FOREIGN KEY ([trip_type]) REFERENCES [trk].[trip_type] ([code]);
        ALTER TABLE [trk].[trip] ADD CONSTRAINT [FK_trk_trip_vehicle_type]
            FOREIGN KEY ([vehicle_type]) REFERENCES [trk].[trip_vehicle_type] ([code]);
        ALTER TABLE [trk].[trip] ADD CONSTRAINT [FK_trk_trip_status]
            FOREIGN KEY ([status]) REFERENCES [trk].[trip_status] ([code]);
    """)

    # ---- the CHECK constraints the foreign keys replace ----
    op.execute("""
        ALTER TABLE [trk].[trackable_activity] DROP CONSTRAINT [CK_trk_trackable_activity_module_code];
        ALTER TABLE [trk].[trip] DROP CONSTRAINT [CK_trk_trip_trip_type];
        ALTER TABLE [trk].[trip] DROP CONSTRAINT [CK_trk_trip_vehicle_type];
        ALTER TABLE [trk].[trip] DROP CONSTRAINT [CK_trk_trip_status];
    """)


def downgrade() -> None:
    # Fails if an administrator has since added master rows that trips already use: those trips must be
    # moved to one of the original values first.
    op.execute("""
        ALTER TABLE [trk].[trip] DROP CONSTRAINT [FK_trk_trip_status];
        ALTER TABLE [trk].[trip] DROP CONSTRAINT [FK_trk_trip_vehicle_type];
        ALTER TABLE [trk].[trip] DROP CONSTRAINT [FK_trk_trip_trip_type];
        ALTER TABLE [trk].[trackable_activity] DROP CONSTRAINT [FK_trk_trackable_activity_module_code];
    """)
    op.execute("""
        ALTER TABLE [trk].[trackable_activity] ADD CONSTRAINT [CK_trk_trackable_activity_module_code]
            CHECK ([module_code] IN (N'SVC', N'PRE'));
        ALTER TABLE [trk].[trip] ADD CONSTRAINT [CK_trk_trip_trip_type]
            CHECK ([trip_type] IN (N'To site', N'Return', N'Site to site'));
        ALTER TABLE [trk].[trip] ADD CONSTRAINT [CK_trk_trip_vehicle_type]
            CHECK ([vehicle_type] IN (N'Own bike', N'Own car', N'Company vehicle', N'Public transport'));
        ALTER TABLE [trk].[trip] ADD CONSTRAINT [CK_trk_trip_status]
            CHECK ([status] IN (N'In progress', N'Completed', N'Auto closed'));
    """)
    for table in ("trip_status", "trip_vehicle_type", "trip_type", "trackable_activity_module"):
        op.execute(f"DROP TABLE IF EXISTS [trk].[{table}];")
