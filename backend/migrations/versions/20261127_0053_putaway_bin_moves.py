"""Warehouse storage phase 3: receiving bins, put-away and bin moves, item storage rules.

  * inv.bin                 + is_receiving: where a GRN puts stock before it is put away (optional per location).
  * core.item               + storage_type: Individual (large items, a bin each) or Grouped (small parts sharing
                            bins); empty = not set.
  * inv.item_storage_rule   (new) an item's home bin in a location, with optional min / max quantity; put-away
                            suggests it first.
  * inv.bin_move, inv.bin_move_line  (new) a move of stock between bins of one location (put-away, rack to rack),
                            posted at once through the stock ledger as BIN_OUT / BIN_IN movements, keeping the GRN
                            batch (and so FIFO and ageing).
  * inv.movement_type       + BIN_OUT, BIN_IN (no effect on cost).
  * permission inv.binmove.manage  put away and move stock between bins; roles that have inv.transfer.manage.

Revision ID: 0053_putaway_bin_moves
Revises: 0052_barcodes_scan
Created: 2026-11-27
"""

from alembic import op

revision = "0053_putaway_bin_moves"
down_revision = "0052_barcodes_scan"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        ALTER TABLE [inv].[bin] ADD [is_receiving] BIT NOT NULL
            CONSTRAINT [DF_inv_bin_is_receiving] DEFAULT (0);
    """)
    op.execute("""
        ALTER TABLE [core].[item] ADD [storage_type] NVARCHAR(12) NULL
            CONSTRAINT [CK_core_item_storage_type] CHECK ([storage_type] IN (N'Individual', N'Grouped'));
    """)
    op.execute("""
        CREATE TABLE [inv].[item_storage_rule] (
            [id] BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT [PK_inv_item_storage_rule] PRIMARY KEY,
            [item_id] BIGINT NOT NULL,
            [location_id] BIGINT NOT NULL,
            [bin_id] BIGINT NOT NULL,
            [min_qty] DECIMAL(18,3) NULL,
            [max_qty] DECIMAL(18,3) NULL,
            [created_at] DATETIME2(0) NOT NULL CONSTRAINT [DF_inv_item_storage_rule_created_at] DEFAULT (SYSUTCDATETIME()),
            [created_by_user_id] BIGINT NULL,
            [updated_at] DATETIME2(0) NULL,
            [updated_by_user_id] BIGINT NULL,
            [is_active] BIT NOT NULL CONSTRAINT [DF_inv_item_storage_rule_is_active] DEFAULT (1),
            [row_version] ROWVERSION NOT NULL,
            CONSTRAINT [FK_inv_item_storage_rule_item_id] FOREIGN KEY ([item_id]) REFERENCES [core].[item] ([id]),
            CONSTRAINT [FK_inv_item_storage_rule_location_id]
                FOREIGN KEY ([location_id]) REFERENCES [core].[location] ([id]),
            CONSTRAINT [FK_inv_item_storage_rule_bin_id] FOREIGN KEY ([bin_id]) REFERENCES [inv].[bin] ([id])
        );
    """)
    op.execute("CREATE UNIQUE INDEX [UX_inv_item_storage_rule_k1] ON [inv].[item_storage_rule] ([item_id], [bin_id]);")
    op.execute("CREATE INDEX [IX_inv_item_storage_rule_bin_id] ON [inv].[item_storage_rule] ([bin_id]);")
    op.execute("""
        CREATE TABLE [inv].[bin_move] (
            [id] BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT [PK_inv_bin_move] PRIMARY KEY,
            [move_no] NVARCHAR(20) NULL,
            [location_id] BIGINT NOT NULL,
            [move_type] NVARCHAR(12) NOT NULL,
            [note] NVARCHAR(200) NULL,
            [moved_by_user_id] BIGINT NULL,
            [moved_at] DATETIME2(0) NOT NULL CONSTRAINT [DF_inv_bin_move_moved_at] DEFAULT (SYSUTCDATETIME()),
            CONSTRAINT [CK_inv_bin_move_move_type] CHECK ([move_type] IN (N'Put-away', N'Bin move')),
            CONSTRAINT [FK_inv_bin_move_location_id] FOREIGN KEY ([location_id]) REFERENCES [core].[location] ([id]),
            CONSTRAINT [FK_inv_bin_move_moved_by_user_id]
                FOREIGN KEY ([moved_by_user_id]) REFERENCES [core].[app_user] ([id])
        );
    """)
    op.execute("CREATE INDEX [IX_inv_bin_move_moved_at] ON [inv].[bin_move] ([moved_at] DESC);")
    op.execute("""
        CREATE TABLE [inv].[bin_move_line] (
            [id] BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT [PK_inv_bin_move_line] PRIMARY KEY,
            [bin_move_id] BIGINT NOT NULL,
            [item_id] BIGINT NOT NULL,
            [stock_lot_id] BIGINT NULL,
            [from_bin_id] BIGINT NULL,
            [to_bin_id] BIGINT NOT NULL,
            [quantity] DECIMAL(18,3) NOT NULL,
            CONSTRAINT [CK_inv_bin_move_line_quantity] CHECK ([quantity] > 0),
            CONSTRAINT [FK_inv_bin_move_line_bin_move_id] FOREIGN KEY ([bin_move_id]) REFERENCES [inv].[bin_move] ([id]),
            CONSTRAINT [FK_inv_bin_move_line_item_id] FOREIGN KEY ([item_id]) REFERENCES [core].[item] ([id]),
            CONSTRAINT [FK_inv_bin_move_line_stock_lot_id]
                FOREIGN KEY ([stock_lot_id]) REFERENCES [inv].[stock_lot] ([id]),
            CONSTRAINT [FK_inv_bin_move_line_from_bin_id] FOREIGN KEY ([from_bin_id]) REFERENCES [inv].[bin] ([id]),
            CONSTRAINT [FK_inv_bin_move_line_to_bin_id] FOREIGN KEY ([to_bin_id]) REFERENCES [inv].[bin] ([id])
        );
    """)
    op.execute("CREATE INDEX [IX_inv_bin_move_line_bin_move_id] ON [inv].[bin_move_line] ([bin_move_id]);")
    for code, name, direction in (("BIN_OUT", "Bin move out", "Out"), ("BIN_IN", "Bin move in", "In")):
        op.execute(f"""
            IF NOT EXISTS (SELECT 1 FROM [inv].[movement_type] WHERE [code] = N'{code}')
                INSERT INTO [inv].[movement_type] ([code], [name], [direction], [affects_cost])
                VALUES (N'{code}', N'{name}', N'{direction}', 0);
        """)  # noqa: S608 - fixed text
    op.execute("""
        IF NOT EXISTS (SELECT 1 FROM [core].[permission] WHERE [code] = N'inv.binmove.manage')
            INSERT INTO [core].[permission] ([code], [module], [description])
            VALUES (N'inv.binmove.manage', N'Inventory', N'Put away received stock and move stock between bins');
    """)
    op.execute("""
        INSERT INTO [core].[role_permission] ([role_id], [permission_id])
        SELECT r.[id], p.[id]
        FROM [core].[role] r
        JOIN [core].[permission] p ON p.[code] = N'inv.binmove.manage'
        WHERE r.[id] IN (SELECT rp2.[role_id] FROM [core].[role_permission] rp2
                         JOIN [core].[permission] p2 ON p2.[id] = rp2.[permission_id]
                         WHERE p2.[code] = N'inv.transfer.manage')
          AND NOT EXISTS (SELECT 1 FROM [core].[role_permission] rp
                          WHERE rp.[role_id] = r.[id] AND rp.[permission_id] = p.[id]);
    """)


def downgrade() -> None:
    op.execute("""
        DELETE rp FROM [core].[role_permission] rp
        JOIN [core].[permission] p ON p.[id] = rp.[permission_id]
        WHERE p.[code] = N'inv.binmove.manage';
        DELETE FROM [core].[permission] WHERE [code] = N'inv.binmove.manage';
    """)
    op.execute("""
        DELETE FROM [inv].[movement_type] WHERE [code] IN (N'BIN_OUT', N'BIN_IN')
            AND NOT EXISTS (SELECT 1 FROM [inv].[stock_move] m WHERE m.[movement_type_id] = [inv].[movement_type].[id]);
    """)
    op.execute("DROP TABLE [inv].[bin_move_line];")
    op.execute("DROP TABLE [inv].[bin_move];")
    op.execute("DROP TABLE [inv].[item_storage_rule];")
    op.execute("ALTER TABLE [core].[item] DROP CONSTRAINT [CK_core_item_storage_type];")
    op.execute("ALTER TABLE [core].[item] DROP COLUMN [storage_type];")
    op.execute("ALTER TABLE [inv].[bin] DROP CONSTRAINT [DF_inv_bin_is_receiving];")
    op.execute("ALTER TABLE [inv].[bin] DROP COLUMN [is_receiving];")
