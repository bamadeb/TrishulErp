"""Warehouse regions: group branches region-wise and tie each region to the warehouse that supplies it.

Warehouses already live in core.branch (branch_type = 'Warehouse'); a branch points at its supplying
warehouse through parent_warehouse_id. This adds only what was missing:

    core.region            code, name, warehouse_id (the warehouse that supplies the region), audit columns
    core.branch.region_id  nullable: the region a branch belongs to

A warehouse can itself be a branch, so no warehouse rows are added here. No existing row is changed. Which
locations are warehouses and the branch -> region -> warehouse mapping are data, applied separately
(scripts/seed_warehouses.py).

Idempotent: every statement checks first.

Revision ID: 0023_warehouse_regions
Revises: 0022_document_permissions
Created: 2026-11-06
"""

from alembic import op

revision = "0023_warehouse_regions"
down_revision = "0022_document_permissions"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        IF OBJECT_ID(N'[core].[region]', N'U') IS NULL
        BEGIN
            CREATE TABLE [core].[region] (
                [id] BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT [PK_core_region] PRIMARY KEY,
                [code] NVARCHAR(10) NOT NULL,
                [name] NVARCHAR(80) NOT NULL,
                [warehouse_id] BIGINT NOT NULL,
                [created_at] DATETIME2(0) NOT NULL CONSTRAINT [DF_core_region_created_at] DEFAULT (SYSUTCDATETIME()),
                [created_by_user_id] BIGINT NULL,
                [updated_at] DATETIME2(0) NULL,
                [updated_by_user_id] BIGINT NULL,
                [is_active] BIT NOT NULL CONSTRAINT [DF_core_region_is_active] DEFAULT (1),
                [row_version] ROWVERSION NOT NULL,
                CONSTRAINT [FK_core_region_warehouse] FOREIGN KEY ([warehouse_id]) REFERENCES [core].[branch]([id]),
                CONSTRAINT [UQ_core_region_code] UNIQUE ([code])
            );
            CREATE INDEX [IX_core_region_warehouse] ON [core].[region]([warehouse_id]);
        END
    """)
    op.execute("""
        IF COL_LENGTH(N'core.branch', N'region_id') IS NULL
        BEGIN
            ALTER TABLE [core].[branch] ADD [region_id] BIGINT NULL;
            ALTER TABLE [core].[branch] ADD CONSTRAINT [FK_core_branch_region]
                FOREIGN KEY ([region_id]) REFERENCES [core].[region]([id]);
            CREATE INDEX [IX_core_branch_region] ON [core].[branch]([region_id]);
        END
    """)


def downgrade() -> None:
    op.execute("""
        IF COL_LENGTH(N'core.branch', N'region_id') IS NOT NULL
        BEGIN
            DROP INDEX [IX_core_branch_region] ON [core].[branch];
            ALTER TABLE [core].[branch] DROP CONSTRAINT [FK_core_branch_region];
            ALTER TABLE [core].[branch] DROP COLUMN [region_id];
        END
        IF OBJECT_ID(N'[core].[region]', N'U') IS NOT NULL DROP TABLE [core].[region];
    """)
