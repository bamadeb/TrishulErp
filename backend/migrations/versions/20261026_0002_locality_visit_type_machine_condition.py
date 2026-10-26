"""Localities, visit type, machine condition; employee mobile optional.

Records changes first made directly on the TrishulDev database on 2026-10-26, so that a database
built from the repository matches it. Every step checks first, so on that database this is a no-op.

Revision ID: 0002
Revises: 0001
Created: 2026-10-26
"""

from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Village / town where machines work; used to route service engineers.
    op.execute("""
        IF OBJECT_ID(N'core.locality', N'U') IS NULL
        CREATE TABLE [core].[locality] (
            [id] BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT [PK_core_locality] PRIMARY KEY,
            [district_id] BIGINT NOT NULL,
            [name] NVARCHAR(120) NOT NULL,
            [pincode_id] BIGINT NULL,
            [latitude] DECIMAL(9,6) NULL,
            [longitude] DECIMAL(9,6) NULL,
            [created_at] DATETIME2(0) NOT NULL CONSTRAINT [DF_core_locality_created_at] DEFAULT (SYSUTCDATETIME()),
            [created_by_user_id] BIGINT NULL,
            [updated_at] DATETIME2(0) NULL,
            [updated_by_user_id] BIGINT NULL,
            [is_active] BIT NOT NULL CONSTRAINT [DF_core_locality_is_active] DEFAULT (1),
            [row_version] ROWVERSION NOT NULL,
            CONSTRAINT [FK_core_locality_district_id] FOREIGN KEY ([district_id]) REFERENCES [core].[district] ([id]),
            CONSTRAINT [FK_core_locality_pincode_id] FOREIGN KEY ([pincode_id]) REFERENCES [core].[pincode] ([id]),
            CONSTRAINT [FK_core_locality_created_by_user_id] FOREIGN KEY ([created_by_user_id])
                REFERENCES [core].[app_user] ([id]),
            CONSTRAINT [FK_core_locality_updated_by_user_id] FOREIGN KEY ([updated_by_user_id])
                REFERENCES [core].[app_user] ([id])
        );
    """)
    op.execute("""
        IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = N'UX_core_locality_k1'
                       AND object_id = OBJECT_ID(N'core.locality'))
            CREATE UNIQUE NONCLUSTERED INDEX [UX_core_locality_k1] ON [core].[locality] ([district_id], [name]);
        IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = N'IX_core_locality_pincode_id'
                       AND object_id = OBJECT_ID(N'core.locality'))
            CREATE NONCLUSTERED INDEX [IX_core_locality_pincode_id] ON [core].[locality] ([pincode_id]);
    """)

    # New columns: one batch each, so the foreign keys compile after their column exists.
    op.execute("""
        IF COL_LENGTH(N'core.customer_site', N'locality_id') IS NULL
            ALTER TABLE [core].[customer_site] ADD [locality_id] BIGINT NULL;
    """)
    op.execute("""
        IF OBJECT_ID(N'core.FK_core_customer_site_locality_id', N'F') IS NULL
            ALTER TABLE [core].[customer_site] ADD CONSTRAINT [FK_core_customer_site_locality_id]
                FOREIGN KEY ([locality_id]) REFERENCES [core].[locality] ([id]);
    """)
    op.execute("""
        IF COL_LENGTH(N'core.machine_unit', N'current_condition_lookup_id') IS NULL
            ALTER TABLE [core].[machine_unit] ADD [current_condition_lookup_id] BIGINT NULL;
    """)
    op.execute("""
        IF OBJECT_ID(N'core.FK_core_machine_unit_current_condition_lookup_id', N'F') IS NULL
            ALTER TABLE [core].[machine_unit] ADD CONSTRAINT [FK_core_machine_unit_current_condition_lookup_id]
                FOREIGN KEY ([current_condition_lookup_id]) REFERENCES [core].[lookup_value] ([id]);
    """)
    op.execute("""
        IF COL_LENGTH(N'svc.service_call', N'visit_type_lookup_id') IS NULL
            ALTER TABLE [svc].[service_call] ADD [visit_type_lookup_id] BIGINT NULL;
    """)
    op.execute("""
        IF OBJECT_ID(N'svc.FK_svc_service_call_visit_type_lookup_id', N'F') IS NULL
            ALTER TABLE [svc].[service_call] ADD CONSTRAINT [FK_svc_service_call_visit_type_lookup_id]
                FOREIGN KEY ([visit_type_lookup_id]) REFERENCES [core].[lookup_value] ([id]);
    """)

    op.execute("""
        IF EXISTS (SELECT 1 FROM sys.columns WHERE object_id = OBJECT_ID(N'core.employee')
                   AND name = N'mobile' AND is_nullable = 0)
            ALTER TABLE [core].[employee] ALTER COLUMN [mobile] NVARCHAR(15) NULL;
    """)

    # Descriptions (plain SQL, so scripts/generate_models.py can read them for docstrings).
    op.execute("""
        IF NOT EXISTS (SELECT 1 FROM sys.extended_properties WHERE name = N'MS_Description'
                       AND major_id = OBJECT_ID(N'core.locality') AND minor_id = 0)
            EXEC sys.sp_addextendedproperty N'MS_Description',
                N'Village / town where machines work; used to route service engineers.',
                N'SCHEMA', N'core', N'TABLE', N'locality';
    """)
    op.execute("""
        IF NOT EXISTS (SELECT 1 FROM sys.extended_properties WHERE name = N'MS_Description'
                       AND major_id = OBJECT_ID(N'core.machine_unit')
                       AND minor_id = COLUMNPROPERTY(OBJECT_ID(N'core.machine_unit'), N'current_condition_lookup_id',
                                                     'ColumnId'))
            EXEC sys.sp_addextendedproperty N'MS_Description', N'Present status of machine: Running / Breakdown (B/D)',
                N'SCHEMA', N'core', N'TABLE', N'machine_unit', N'COLUMN', N'current_condition_lookup_id';
    """)
    op.execute("""
        IF NOT EXISTS (SELECT 1 FROM sys.extended_properties WHERE name = N'MS_Description'
                       AND major_id = OBJECT_ID(N'core.customer_site')
                       AND minor_id = COLUMNPROPERTY(OBJECT_ID(N'core.customer_site'), N'locality_id', 'ColumnId'))
            EXEC sys.sp_addextendedproperty N'MS_Description', N'Village / town of the site',
                N'SCHEMA', N'core', N'TABLE', N'customer_site', N'COLUMN', N'locality_id';
    """)
    op.execute("""
        IF NOT EXISTS (SELECT 1 FROM sys.extended_properties WHERE name = N'MS_Description'
                       AND major_id = OBJECT_ID(N'svc.service_call')
                       AND minor_id = COLUMNPROPERTY(OBJECT_ID(N'svc.service_call'), N'visit_type_lookup_id',
                                                     'ColumnId'))
            EXEC sys.sp_addextendedproperty N'MS_Description', N'Type of visit: MSI, M/W, G/W, ASC, Paid...',
                N'SCHEMA', N'svc', N'TABLE', N'service_call', N'COLUMN', N'visit_type_lookup_id';
    """)


def downgrade() -> None:
    # Destructive: drops localities and the three new columns with their data.
    op.execute("""
        ALTER TABLE [svc].[service_call] DROP CONSTRAINT IF EXISTS [FK_svc_service_call_visit_type_lookup_id];
        ALTER TABLE [svc].[service_call] DROP COLUMN IF EXISTS [visit_type_lookup_id];
        ALTER TABLE [core].[machine_unit] DROP CONSTRAINT IF EXISTS [FK_core_machine_unit_current_condition_lookup_id];
        ALTER TABLE [core].[machine_unit] DROP COLUMN IF EXISTS [current_condition_lookup_id];
        ALTER TABLE [core].[customer_site] DROP CONSTRAINT IF EXISTS [FK_core_customer_site_locality_id];
        ALTER TABLE [core].[customer_site] DROP COLUMN IF EXISTS [locality_id];
        DROP TABLE IF EXISTS [core].[locality];
    """)
