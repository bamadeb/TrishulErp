"""Warehouse storage phase 1: racks with levels x positions, flexible bins and locations.

Every location stays flexible: stock may sit at the location only, on a loose bin / yard spot (a bin with no
rack), or in a bin of a rack. Nothing here makes a bin or a barcode mandatory.

  * core.location   location_type also Receiving and Open area (yards, outside racks); requires_bin flag
                    (default 0 = a bin is optional), for a store that later wants every movement in a bin.
  * inv.storage_rack (new)  a physical rack of a location: code (<location>-<rack>, e.g. BBSR-MAIN-R01),
                    type, levels x positions, max weight, blocked flag. Its bins are generated with codes
                    <rack code>-L<level>-B<position> (BBSR-MAIN-R01-L2-B05).
  * inv.bin         code widened to 30 characters; storage_rack_id (empty = loose bin or yard spot), level_no,
                    position_no, bin_type (Single item / Mixed / Shared / Area spot), max_qty, is_blocked,
                    blocked_reason. The existing rack / shelf text columns stay.

Revision ID: 0051_storage_racks
Revises: 0050_price_import
Created: 2026-11-27
"""

from alembic import op

revision = "0051_storage_racks"
down_revision = "0050_price_import"
branch_labels = None
depends_on = None

_TYPES_NEW = "N'Main store', N'Transit', N'Quarantine', N'Scrap', N'Receiving', N'Open area'"
_TYPES_OLD = "N'Main store', N'Transit', N'Quarantine', N'Scrap'"


def _drop_index(table: str, name: str) -> None:
    op.execute(f"""
        IF EXISTS (SELECT 1 FROM sys.indexes WHERE [name] = N'{name}' AND [object_id] = OBJECT_ID(N'{table}'))
            DROP INDEX [{name}] ON {table};
    """)  # noqa: S608 - fixed text


def upgrade() -> None:
    # ---------------------------------------------------------------- locations
    op.execute("ALTER TABLE [core].[location] DROP CONSTRAINT [CK_core_location_location_type];")
    op.execute(f"""
        ALTER TABLE [core].[location] ADD CONSTRAINT [CK_core_location_location_type]
            CHECK ([location_type] IN ({_TYPES_NEW}));
    """)
    op.execute("""
        ALTER TABLE [core].[location] ADD [requires_bin] BIT NOT NULL
            CONSTRAINT [DF_core_location_requires_bin] DEFAULT (0);
    """)

    # ---------------------------------------------------------------- racks
    op.execute("""
        CREATE TABLE [inv].[storage_rack] (
            [id] BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT [PK_inv_storage_rack] PRIMARY KEY,
            [location_id] BIGINT NOT NULL,
            [code] NVARCHAR(20) NOT NULL,
            [short_code] NVARCHAR(8) NOT NULL,
            [name] NVARCHAR(80) NULL,
            [rack_type] NVARCHAR(20) NOT NULL CONSTRAINT [DF_inv_storage_rack_rack_type] DEFAULT (N'Rack'),
            [levels] SMALLINT NOT NULL,
            [positions] SMALLINT NOT NULL,
            [max_weight_kg] DECIMAL(10,2) NULL,
            [is_blocked] BIT NOT NULL CONSTRAINT [DF_inv_storage_rack_is_blocked] DEFAULT (0),
            [blocked_reason] NVARCHAR(200) NULL,
            [created_at] DATETIME2(0) NOT NULL CONSTRAINT [DF_inv_storage_rack_created_at] DEFAULT (SYSUTCDATETIME()),
            [created_by_user_id] BIGINT NULL,
            [updated_at] DATETIME2(0) NULL,
            [updated_by_user_id] BIGINT NULL,
            [is_active] BIT NOT NULL CONSTRAINT [DF_inv_storage_rack_is_active] DEFAULT (1),
            [row_version] ROWVERSION NOT NULL,
            CONSTRAINT [CK_inv_storage_rack_rack_type] CHECK ([rack_type] IN (N'Rack', N'Shelf', N'Bin cabinet', N'Floor')),
            CONSTRAINT [CK_inv_storage_rack_levels] CHECK ([levels] BETWEEN 1 AND 20),
            CONSTRAINT [CK_inv_storage_rack_positions] CHECK ([positions] BETWEEN 1 AND 99),
            CONSTRAINT [FK_inv_storage_rack_location_id] FOREIGN KEY ([location_id]) REFERENCES [core].[location] ([id])
        );
    """)
    op.execute("CREATE UNIQUE INDEX [UX_inv_storage_rack_code] ON [inv].[storage_rack] ([code]);")
    op.execute("CREATE UNIQUE INDEX [UX_inv_storage_rack_k1] ON [inv].[storage_rack] ([location_id], [short_code]);")

    # ---------------------------------------------------------------- bins
    _drop_index("[inv].[bin]", "UX_inv_bin_code")
    _drop_index("[inv].[bin]", "UX_inv_bin_k1")
    op.execute("ALTER TABLE [inv].[bin] ALTER COLUMN [code] NVARCHAR(30) NOT NULL;")
    op.execute("CREATE UNIQUE INDEX [UX_inv_bin_code] ON [inv].[bin] ([code]);")
    op.execute("CREATE UNIQUE INDEX [UX_inv_bin_k1] ON [inv].[bin] ([location_id], [code]);")
    op.execute("""
        ALTER TABLE [inv].[bin] ADD
            [storage_rack_id] BIGINT NULL,
            [level_no] SMALLINT NULL,
            [position_no] SMALLINT NULL,
            [bin_type] NVARCHAR(20) NOT NULL CONSTRAINT [DF_inv_bin_bin_type] DEFAULT (N'Mixed'),
            [max_qty] DECIMAL(18,3) NULL,
            [is_blocked] BIT NOT NULL CONSTRAINT [DF_inv_bin_is_blocked] DEFAULT (0),
            [blocked_reason] NVARCHAR(200) NULL,
            CONSTRAINT [CK_inv_bin_bin_type] CHECK ([bin_type] IN (N'Single item', N'Mixed', N'Shared', N'Area spot')),
            CONSTRAINT [FK_inv_bin_storage_rack_id] FOREIGN KEY ([storage_rack_id]) REFERENCES [inv].[storage_rack] ([id]);
    """)
    op.execute("""
        CREATE UNIQUE INDEX [UX_inv_bin_rack_slot] ON [inv].[bin] ([storage_rack_id], [level_no], [position_no])
            WHERE [storage_rack_id] IS NOT NULL;
    """)


def downgrade() -> None:
    _drop_index("[inv].[bin]", "UX_inv_bin_rack_slot")
    op.execute("""
        ALTER TABLE [inv].[bin] DROP CONSTRAINT [FK_inv_bin_storage_rack_id], [CK_inv_bin_bin_type],
            [DF_inv_bin_bin_type], [DF_inv_bin_is_blocked];
        ALTER TABLE [inv].[bin] DROP COLUMN [storage_rack_id], [level_no], [position_no], [bin_type], [max_qty],
            [is_blocked], [blocked_reason];
    """)
    _drop_index("[inv].[bin]", "UX_inv_bin_code")
    _drop_index("[inv].[bin]", "UX_inv_bin_k1")
    op.execute("ALTER TABLE [inv].[bin] ALTER COLUMN [code] NVARCHAR(20) NOT NULL;")
    op.execute("CREATE UNIQUE INDEX [UX_inv_bin_code] ON [inv].[bin] ([code]);")
    op.execute("CREATE UNIQUE INDEX [UX_inv_bin_k1] ON [inv].[bin] ([location_id], [code]);")
    op.execute("DROP TABLE [inv].[storage_rack];")
    op.execute("""
        ALTER TABLE [core].[location] DROP CONSTRAINT [DF_core_location_requires_bin];
        ALTER TABLE [core].[location] DROP COLUMN [requires_bin];
    """)
    op.execute("ALTER TABLE [core].[location] DROP CONSTRAINT [CK_core_location_location_type];")
    op.execute(f"""
        ALTER TABLE [core].[location] ADD CONSTRAINT [CK_core_location_location_type]
            CHECK ([location_type] IN ({_TYPES_OLD}));
    """)
