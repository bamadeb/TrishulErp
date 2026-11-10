"""Item and inventory management: GRN batches (lots), batch-level stock per location and rack, unit
conversions, and the permissions, number series and links the screens need.

Inventory ageing is kept per GRN batch, not per item:

    inv.stock_lot      one row per batch received: a GRN line, an opening-stock line or an adjustment
                       that adds stock. grn_date is the day the age starts from and never changes;
                       unit_cost is the batch's actual cost (used to value the ageing buckets).
    inv.lot_balance    how much of a batch sits at a location (and rack). A transfer moves quantity from
                       one row to another of the same batch, so the GRN date travels with the stock.
    inv.uom_conversion 1 from-unit = factor to-units, for one item (item_id) or for every item (NULL).

Columns added:
    inv.stock_move.stock_lot_id                      the batch each ledger row moved
    inv.stock_transfer_line.from_bin_id / to_bin_id  rack to rack (a transfer may stay in one location)
    inv.stock_transfer.remarks
    inv.stock_adjustment.remarks / posted_at / posted_by_user_id   who authorised the adjustment, when
    inv.stock_adjustment_line.stock_lot_id           the batch increased or chosen to decrease
    pur.grn_line.entry_uom_id / entry_qty            the unit and quantity as received (converted to the
                                                     item's stock unit in qty_received)
    pur.grn.remarks
    inv.bin: rack codes are unique across all locations (UX_inv_bin_code).

Number series (per active branch, plus a company-wide fallback for branches added later):
    GRN               <BRANCH>/GRN/00001
    STOCK_TRANSFER    <BRANCH>/ST/00001
    STOCK_ADJUSTMENT  <BRANCH>/ADJ/00001

Permissions:
    inv.item.view       see items, categories, units and prices
    inv.item.manage     add and change items, categories, units, conversions, prices and costs
    inv.location.manage add and change stock locations and racks
    inv.stock.view      see stock by batch, movements and the ageing reports
    inv.grn.manage      receive goods (GRN), enter opening stock, maintain suppliers
    inv.transfer.manage transfer stock between branches, warehouses and racks
    inv.stock.adjust    already exists: post stock adjustments
Granted to ADMIN and INVENTORY (all); WAREHOUSE (view, receive, transfer); PURCHASE (view, receive);
MANAGEMENT (view).

Idempotent: every statement checks first. All the tables touched are empty on RDS (2026-11-10).
The DDL is written out in full (no f-strings): scripts/generate_models.py reads op.execute literals.

Revision ID: 0030_inventory_module
Revises: 0029_checklist_template_note
Created: 2026-11-10
"""

import sqlalchemy as sa
from alembic import op

revision = "0030_inventory_module"
down_revision = "0029_checklist_template_note"
branch_labels = None
depends_on = None

_PERMISSIONS = (
    ("inv.item.view", "See items, item categories, units of measure and prices"),
    ("inv.item.manage", "Add and change items, categories, units, conversions, prices and costs"),
    ("inv.location.manage", "Add and change stock locations and racks"),
    ("inv.stock.view", "See stock by GRN batch, stock movements and the inventory ageing reports"),
    ("inv.grn.manage", "Receive goods (GRN), enter opening stock and maintain suppliers"),
    ("inv.transfer.manage", "Transfer stock between branches, warehouses and racks"),
)

_ALL = [code for code, _ in _PERMISSIONS] + ["inv.stock.adjust"]
_GRANTS = {
    "ADMIN": _ALL,
    "INVENTORY": _ALL,
    "WAREHOUSE": ["inv.item.view", "inv.stock.view", "inv.grn.manage", "inv.transfer.manage"],
    "PURCHASE": ["inv.item.view", "inv.stock.view", "inv.grn.manage"],
    "MANAGEMENT": ["inv.item.view", "inv.stock.view"],
}

_SERIES = (("GRN", "/GRN/"), ("STOCK_TRANSFER", "/ST/"), ("STOCK_ADJUSTMENT", "/ADJ/"))

_GRANT = sa.text("""
    INSERT INTO [core].[role_permission] ([role_id], [permission_id])
    SELECT r.[id], p.[id]
    FROM [core].[role] r
    JOIN [core].[permission] p ON p.[code] = :permission
    WHERE r.[code] = :role
      AND NOT EXISTS (SELECT 1 FROM [core].[role_permission] rp
                      WHERE rp.[role_id] = r.[id] AND rp.[permission_id] = p.[id]);
""")

_PERMISSION = sa.text("""
    INSERT INTO [core].[permission] ([code], [module], [description])
    SELECT :code, N'Inventory', :description
    WHERE NOT EXISTS (SELECT 1 FROM [core].[permission] WHERE [code] = :code);
""")

_BRANCH_SERIES = sa.text("""
    INSERT INTO [core].[number_series]
        ([company_id], [document_type], [branch_id], [principal_id], [fiscal_year_id],
         [prefix], [next_number], [padding], [suffix])
    SELECT b.[company_id], :document_type, b.[id], NULL, NULL, b.[code] + :infix, 1, 5, NULL
    FROM [core].[branch] b
    WHERE b.[is_active] = 1
      AND NOT EXISTS (SELECT 1 FROM [core].[number_series] ns
                      WHERE ns.[document_type] = :document_type AND ns.[branch_id] = b.[id]
                        AND ns.[principal_id] IS NULL AND ns.[fiscal_year_id] IS NULL);
""")

_COMPANY_SERIES = sa.text("""
    INSERT INTO [core].[number_series]
        ([company_id], [document_type], [branch_id], [principal_id], [fiscal_year_id],
         [prefix], [next_number], [padding], [suffix])
    SELECT c.[id], :document_type, NULL, NULL, NULL, c.[code] + :infix, 1, 5, NULL
    FROM [core].[company] c
    WHERE NOT EXISTS (SELECT 1 FROM [core].[number_series] ns
                      WHERE ns.[document_type] = :document_type AND ns.[company_id] = c.[id]
                        AND ns.[branch_id] IS NULL AND ns.[principal_id] IS NULL
                        AND ns.[fiscal_year_id] IS NULL);
""")


def upgrade() -> None:
    op.execute("""
        IF OBJECT_ID(N'[inv].[uom_conversion]', N'U') IS NULL
        BEGIN
            CREATE TABLE [inv].[uom_conversion] (
                [id] BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT [PK_inv_uom_conversion] PRIMARY KEY,
                [item_id] BIGINT NULL,
                [from_uom_id] BIGINT NOT NULL,
                [to_uom_id] BIGINT NOT NULL,
                [factor] DECIMAL(18,6) NOT NULL,
                [created_at] DATETIME2(0) NOT NULL CONSTRAINT [DF_inv_uom_conversion_created_at] DEFAULT (SYSUTCDATETIME()),
                [created_by_user_id] BIGINT NULL,
                [updated_at] DATETIME2(0) NULL,
                [updated_by_user_id] BIGINT NULL,
                [is_active] BIT NOT NULL CONSTRAINT [DF_inv_uom_conversion_is_active] DEFAULT (1),
                [row_version] ROWVERSION NOT NULL,
                CONSTRAINT [FK_inv_uom_conversion_item_id] FOREIGN KEY ([item_id]) REFERENCES [core].[item]([id]),
                CONSTRAINT [FK_inv_uom_conversion_from_uom_id] FOREIGN KEY ([from_uom_id]) REFERENCES [core].[uom]([id]),
                CONSTRAINT [FK_inv_uom_conversion_to_uom_id] FOREIGN KEY ([to_uom_id]) REFERENCES [core].[uom]([id]),
                CONSTRAINT [CK_inv_uom_conversion_factor] CHECK ([factor] > 0)
            );
            CREATE UNIQUE NONCLUSTERED INDEX [UX_inv_uom_conversion_k1]
                ON [inv].[uom_conversion] ([item_id], [from_uom_id], [to_uom_id]);
        END
    """)
    op.execute("""
        IF OBJECT_ID(N'[inv].[stock_lot]', N'U') IS NULL
        BEGIN
            CREATE TABLE [inv].[stock_lot] (
                [id] BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT [PK_inv_stock_lot] PRIMARY KEY,
                [company_id] BIGINT NOT NULL,
                [item_id] BIGINT NOT NULL,
                [lot_no] NVARCHAR(40) NOT NULL,
                [source_type] NVARCHAR(30) NOT NULL,
                [grn_id] BIGINT NULL,
                [grn_line_id] BIGINT NULL,
                [stock_adjustment_id] BIGINT NULL,
                [grn_no] NVARCHAR(30) NOT NULL,
                [grn_date] DATE NOT NULL,
                [supplier_id] BIGINT NULL,
                [received_location_id] BIGINT NOT NULL,
                [unit_cost] DECIMAL(18,4) NOT NULL,
                [qty_received] DECIMAL(18,3) NOT NULL,
                [remarks] NVARCHAR(200) NULL,
                [created_at] DATETIME2(0) NOT NULL CONSTRAINT [DF_inv_stock_lot_created_at] DEFAULT (SYSUTCDATETIME()),
                [created_by_user_id] BIGINT NULL,
                [updated_at] DATETIME2(0) NULL,
                [updated_by_user_id] BIGINT NULL,
                [is_active] BIT NOT NULL CONSTRAINT [DF_inv_stock_lot_is_active] DEFAULT (1),
                [row_version] ROWVERSION NOT NULL,
                CONSTRAINT [FK_inv_stock_lot_company_id] FOREIGN KEY ([company_id]) REFERENCES [core].[company]([id]),
                CONSTRAINT [FK_inv_stock_lot_item_id] FOREIGN KEY ([item_id]) REFERENCES [core].[item]([id]),
                CONSTRAINT [FK_inv_stock_lot_grn_id] FOREIGN KEY ([grn_id]) REFERENCES [pur].[grn]([id]),
                CONSTRAINT [FK_inv_stock_lot_grn_line_id] FOREIGN KEY ([grn_line_id]) REFERENCES [pur].[grn_line]([id]),
                CONSTRAINT [FK_inv_stock_lot_stock_adjustment_id] FOREIGN KEY ([stock_adjustment_id])
                    REFERENCES [inv].[stock_adjustment]([id]),
                CONSTRAINT [FK_inv_stock_lot_supplier_id] FOREIGN KEY ([supplier_id]) REFERENCES [core].[supplier]([id]),
                CONSTRAINT [FK_inv_stock_lot_received_location_id] FOREIGN KEY ([received_location_id])
                    REFERENCES [core].[location]([id]),
                CONSTRAINT [CK_inv_stock_lot_source_type] CHECK ([source_type] IN (N'GRN', N'Opening', N'Adjustment')),
                CONSTRAINT [CK_inv_stock_lot_quantities] CHECK ([qty_received] > 0 AND [unit_cost] >= 0)
            );
            CREATE UNIQUE NONCLUSTERED INDEX [UX_inv_stock_lot_lot_no] ON [inv].[stock_lot] ([lot_no]);
            CREATE NONCLUSTERED INDEX [IX_inv_stock_lot_item_id] ON [inv].[stock_lot] ([item_id], [grn_date]);
            CREATE NONCLUSTERED INDEX [IX_inv_stock_lot_grn_id] ON [inv].[stock_lot] ([grn_id]);
            CREATE NONCLUSTERED INDEX [IX_inv_stock_lot_grn_date] ON [inv].[stock_lot] ([grn_date]);
        END
    """)
    op.execute("""
        IF OBJECT_ID(N'[inv].[lot_balance]', N'U') IS NULL
        BEGIN
            CREATE TABLE [inv].[lot_balance] (
                [id] BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT [PK_inv_lot_balance] PRIMARY KEY,
                [stock_lot_id] BIGINT NOT NULL,
                [item_id] BIGINT NOT NULL,
                [location_id] BIGINT NOT NULL,
                [bin_id] BIGINT NULL,
                [qty_on_hand] DECIMAL(18,3) NOT NULL CONSTRAINT [DF_inv_lot_balance_qty_on_hand] DEFAULT (0),
                [last_movement_at] DATETIME2(0) NULL,
                [created_at] DATETIME2(0) NOT NULL CONSTRAINT [DF_inv_lot_balance_created_at] DEFAULT (SYSUTCDATETIME()),
                [created_by_user_id] BIGINT NULL,
                [updated_at] DATETIME2(0) NULL,
                [updated_by_user_id] BIGINT NULL,
                [is_active] BIT NOT NULL CONSTRAINT [DF_inv_lot_balance_is_active] DEFAULT (1),
                [row_version] ROWVERSION NOT NULL,
                CONSTRAINT [FK_inv_lot_balance_stock_lot_id] FOREIGN KEY ([stock_lot_id]) REFERENCES [inv].[stock_lot]([id]),
                CONSTRAINT [FK_inv_lot_balance_item_id] FOREIGN KEY ([item_id]) REFERENCES [core].[item]([id]),
                CONSTRAINT [FK_inv_lot_balance_location_id] FOREIGN KEY ([location_id]) REFERENCES [core].[location]([id]),
                CONSTRAINT [FK_inv_lot_balance_bin_id] FOREIGN KEY ([bin_id]) REFERENCES [inv].[bin]([id]),
                CONSTRAINT [CK_inv_lot_balance_non_negative] CHECK ([qty_on_hand] >= 0)
            );
            CREATE UNIQUE NONCLUSTERED INDEX [UX_inv_lot_balance_k1]
                ON [inv].[lot_balance] ([stock_lot_id], [location_id], [bin_id]);
            CREATE NONCLUSTERED INDEX [IX_inv_lot_balance_item_location]
                ON [inv].[lot_balance] ([item_id], [location_id], [bin_id]) INCLUDE ([qty_on_hand]);
            CREATE NONCLUSTERED INDEX [IX_inv_lot_balance_location_id] ON [inv].[lot_balance] ([location_id]);
        END
    """)
    op.execute("""
        IF COL_LENGTH(N'inv.stock_move', N'stock_lot_id') IS NULL
        BEGIN
            ALTER TABLE [inv].[stock_move] ADD [stock_lot_id] BIGINT NULL;
            ALTER TABLE [inv].[stock_move] ADD CONSTRAINT [FK_inv_stock_move_stock_lot_id]
                FOREIGN KEY ([stock_lot_id]) REFERENCES [inv].[stock_lot]([id]);
            CREATE NONCLUSTERED INDEX [IX_inv_stock_move_stock_lot_id] ON [inv].[stock_move] ([stock_lot_id]);
            CREATE NONCLUSTERED INDEX [IX_inv_stock_move_source]
                ON [inv].[stock_move] ([source_document_type], [source_document_id]);
        END
    """)
    op.execute("""
        IF COL_LENGTH(N'inv.stock_transfer', N'remarks') IS NULL
            ALTER TABLE [inv].[stock_transfer] ADD [remarks] NVARCHAR(300) NULL;
    """)
    op.execute("""
        IF COL_LENGTH(N'inv.stock_transfer_line', N'from_bin_id') IS NULL
        BEGIN
            ALTER TABLE [inv].[stock_transfer_line] ADD [from_bin_id] BIGINT NULL;
            ALTER TABLE [inv].[stock_transfer_line] ADD [to_bin_id] BIGINT NULL;
            ALTER TABLE [inv].[stock_transfer_line] ADD CONSTRAINT [FK_inv_stock_transfer_line_from_bin_id]
                FOREIGN KEY ([from_bin_id]) REFERENCES [inv].[bin]([id]);
            ALTER TABLE [inv].[stock_transfer_line] ADD CONSTRAINT [FK_inv_stock_transfer_line_to_bin_id]
                FOREIGN KEY ([to_bin_id]) REFERENCES [inv].[bin]([id]);
        END
    """)
    op.execute("""
        IF COL_LENGTH(N'inv.stock_adjustment', N'posted_at') IS NULL
        BEGIN
            ALTER TABLE [inv].[stock_adjustment] ADD [remarks] NVARCHAR(300) NULL;
            ALTER TABLE [inv].[stock_adjustment] ADD [posted_at] DATETIME2(0) NULL;
            ALTER TABLE [inv].[stock_adjustment] ADD [posted_by_user_id] BIGINT NULL;
            ALTER TABLE [inv].[stock_adjustment] ADD CONSTRAINT [FK_inv_stock_adjustment_posted_by_user_id]
                FOREIGN KEY ([posted_by_user_id]) REFERENCES [core].[app_user]([id]);
        END
    """)
    op.execute("""
        IF COL_LENGTH(N'inv.stock_adjustment_line', N'stock_lot_id') IS NULL
        BEGIN
            ALTER TABLE [inv].[stock_adjustment_line] ADD [stock_lot_id] BIGINT NULL;
            ALTER TABLE [inv].[stock_adjustment_line] ADD CONSTRAINT [FK_inv_stock_adjustment_line_stock_lot_id]
                FOREIGN KEY ([stock_lot_id]) REFERENCES [inv].[stock_lot]([id]);
        END
    """)
    op.execute("""
        IF COL_LENGTH(N'pur.grn', N'remarks') IS NULL
            ALTER TABLE [pur].[grn] ADD [remarks] NVARCHAR(300) NULL;
    """)
    op.execute("""
        IF COL_LENGTH(N'pur.grn_line', N'entry_uom_id') IS NULL
        BEGIN
            ALTER TABLE [pur].[grn_line] ADD [entry_uom_id] BIGINT NULL;
            ALTER TABLE [pur].[grn_line] ADD [entry_qty] DECIMAL(18,3) NULL;
            ALTER TABLE [pur].[grn_line] ADD CONSTRAINT [FK_pur_grn_line_entry_uom_id]
                FOREIGN KEY ([entry_uom_id]) REFERENCES [core].[uom]([id]);
        END
    """)
    op.execute("""
        IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE [name] = N'UX_inv_bin_code'
                       AND [object_id] = OBJECT_ID(N'[inv].[bin]'))
            CREATE UNIQUE NONCLUSTERED INDEX [UX_inv_bin_code] ON [inv].[bin] ([code]);
    """)

    bind = op.get_bind()
    for document_type, infix in _SERIES:
        bind.execute(_BRANCH_SERIES, {"document_type": document_type, "infix": infix})
        bind.execute(_COMPANY_SERIES, {"document_type": document_type, "infix": infix})
    for code, description in _PERMISSIONS:
        bind.execute(_PERMISSION, {"code": code, "description": description})
    for role, permissions in _GRANTS.items():
        for permission in permissions:
            bind.execute(_GRANT, {"role": role, "permission": permission})


def downgrade() -> None:
    codes = {"codes": [code for code, _ in _PERMISSIONS]}
    expanding: sa.BindParameter[list[str]] = sa.bindparam("codes", expanding=True)
    bind = op.get_bind()
    bind.execute(
        sa.text("""
            DELETE rp FROM [core].[role_permission] rp
            JOIN [core].[permission] p ON p.[id] = rp.[permission_id]
            WHERE p.[code] IN :codes
        """).bindparams(expanding),
        codes,
    )
    bind.execute(sa.text("DELETE FROM [core].[permission] WHERE [code] IN :codes").bindparams(expanding), codes)
    op.execute("""
        DELETE FROM [core].[number_series]
        WHERE [document_type] IN (N'GRN', N'STOCK_TRANSFER', N'STOCK_ADJUSTMENT') AND [next_number] = 1;
    """)
    op.execute("""
        IF EXISTS (SELECT 1 FROM sys.indexes WHERE [name] = N'UX_inv_bin_code')
            DROP INDEX [UX_inv_bin_code] ON [inv].[bin];
        IF OBJECT_ID(N'[pur].[FK_pur_grn_line_entry_uom_id]', N'F') IS NOT NULL
            ALTER TABLE [pur].[grn_line] DROP CONSTRAINT [FK_pur_grn_line_entry_uom_id];
        IF COL_LENGTH(N'pur.grn_line', N'entry_qty') IS NOT NULL ALTER TABLE [pur].[grn_line] DROP COLUMN [entry_qty];
        IF COL_LENGTH(N'pur.grn_line', N'entry_uom_id') IS NOT NULL
            ALTER TABLE [pur].[grn_line] DROP COLUMN [entry_uom_id];
        IF COL_LENGTH(N'pur.grn', N'remarks') IS NOT NULL ALTER TABLE [pur].[grn] DROP COLUMN [remarks];
        IF OBJECT_ID(N'[inv].[FK_inv_stock_adjustment_line_stock_lot_id]', N'F') IS NOT NULL
            ALTER TABLE [inv].[stock_adjustment_line] DROP CONSTRAINT [FK_inv_stock_adjustment_line_stock_lot_id];
        IF COL_LENGTH(N'inv.stock_adjustment_line', N'stock_lot_id') IS NOT NULL
            ALTER TABLE [inv].[stock_adjustment_line] DROP COLUMN [stock_lot_id];
        IF OBJECT_ID(N'[inv].[FK_inv_stock_adjustment_posted_by_user_id]', N'F') IS NOT NULL
            ALTER TABLE [inv].[stock_adjustment] DROP CONSTRAINT [FK_inv_stock_adjustment_posted_by_user_id];
        IF COL_LENGTH(N'inv.stock_adjustment', N'posted_by_user_id') IS NOT NULL
            ALTER TABLE [inv].[stock_adjustment] DROP COLUMN [posted_by_user_id];
        IF COL_LENGTH(N'inv.stock_adjustment', N'posted_at') IS NOT NULL
            ALTER TABLE [inv].[stock_adjustment] DROP COLUMN [posted_at];
        IF COL_LENGTH(N'inv.stock_adjustment', N'remarks') IS NOT NULL
            ALTER TABLE [inv].[stock_adjustment] DROP COLUMN [remarks];
        IF OBJECT_ID(N'[inv].[FK_inv_stock_transfer_line_to_bin_id]', N'F') IS NOT NULL
            ALTER TABLE [inv].[stock_transfer_line] DROP CONSTRAINT [FK_inv_stock_transfer_line_to_bin_id];
        IF OBJECT_ID(N'[inv].[FK_inv_stock_transfer_line_from_bin_id]', N'F') IS NOT NULL
            ALTER TABLE [inv].[stock_transfer_line] DROP CONSTRAINT [FK_inv_stock_transfer_line_from_bin_id];
        IF COL_LENGTH(N'inv.stock_transfer_line', N'to_bin_id') IS NOT NULL
            ALTER TABLE [inv].[stock_transfer_line] DROP COLUMN [to_bin_id];
        IF COL_LENGTH(N'inv.stock_transfer_line', N'from_bin_id') IS NOT NULL
            ALTER TABLE [inv].[stock_transfer_line] DROP COLUMN [from_bin_id];
        IF COL_LENGTH(N'inv.stock_transfer', N'remarks') IS NOT NULL
            ALTER TABLE [inv].[stock_transfer] DROP COLUMN [remarks];
        IF EXISTS (SELECT 1 FROM sys.indexes WHERE [name] = N'IX_inv_stock_move_source')
            DROP INDEX [IX_inv_stock_move_source] ON [inv].[stock_move];
        IF EXISTS (SELECT 1 FROM sys.indexes WHERE [name] = N'IX_inv_stock_move_stock_lot_id')
            DROP INDEX [IX_inv_stock_move_stock_lot_id] ON [inv].[stock_move];
        IF OBJECT_ID(N'[inv].[FK_inv_stock_move_stock_lot_id]', N'F') IS NOT NULL
            ALTER TABLE [inv].[stock_move] DROP CONSTRAINT [FK_inv_stock_move_stock_lot_id];
        IF COL_LENGTH(N'inv.stock_move', N'stock_lot_id') IS NOT NULL
            ALTER TABLE [inv].[stock_move] DROP COLUMN [stock_lot_id];
        IF OBJECT_ID(N'[inv].[lot_balance]', N'U') IS NOT NULL DROP TABLE [inv].[lot_balance];
        IF OBJECT_ID(N'[inv].[stock_lot]', N'U') IS NOT NULL DROP TABLE [inv].[stock_lot];
        IF OBJECT_ID(N'[inv].[uom_conversion]', N'U') IS NOT NULL DROP TABLE [inv].[uom_conversion];
    """)
