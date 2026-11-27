"""Warehouse storage phase 5: physical stock counts on the existing inv.stock_count tables.

  * inv.stock_count        + scope (Location / Rack / Bins), storage_rack_id, is_blind, remarks,
                           closed_at / closed_by (counting finished), posted_at / posted_by (adjustment posted).
                           The adjustment posted for a count is found by inv.stock_adjustment.stock_count_id.
  * inv.stock_count_bin    (new) the bins of a count whose scope is a list of bins.
  * inv.stock_count_line   + counted_at, is_expected (0 = found during the count, not in the system at the start),
                           remarks; one line per item and bin of a count.
  * permissions            inv.count.manage   create count sheets and enter counts: roles with inv.transfer.manage;
                           inv.count.approve  review differences and post the count adjustment: ADMIN, INVENTORY.

Revision ID: 0054_stock_counts
Revises: 0053_putaway_bin_moves
Created: 2026-11-27
"""

from alembic import op

revision = "0054_stock_counts"
down_revision = "0053_putaway_bin_moves"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        ALTER TABLE [inv].[stock_count] ADD
            [scope] NVARCHAR(10) NOT NULL CONSTRAINT [DF_inv_stock_count_scope] DEFAULT (N'Location'),
            [storage_rack_id] BIGINT NULL,
            [is_blind] BIT NOT NULL CONSTRAINT [DF_inv_stock_count_is_blind] DEFAULT (1),
            [remarks] NVARCHAR(300) NULL,
            [closed_at] DATETIME2(0) NULL,
            [closed_by_user_id] BIGINT NULL,
            [posted_at] DATETIME2(0) NULL,
            [posted_by_user_id] BIGINT NULL;
    """)
    op.execute("""
        ALTER TABLE [inv].[stock_count] ADD
            CONSTRAINT [CK_inv_stock_count_scope] CHECK ([scope] IN (N'Location', N'Rack', N'Bins')),
            CONSTRAINT [FK_inv_stock_count_storage_rack_id]
                FOREIGN KEY ([storage_rack_id]) REFERENCES [inv].[storage_rack] ([id]),
            CONSTRAINT [FK_inv_stock_count_closed_by_user_id]
                FOREIGN KEY ([closed_by_user_id]) REFERENCES [core].[app_user] ([id]),
            CONSTRAINT [FK_inv_stock_count_posted_by_user_id]
                FOREIGN KEY ([posted_by_user_id]) REFERENCES [core].[app_user] ([id]);
    """)
    op.execute("""
        CREATE TABLE [inv].[stock_count_bin] (
            [id] BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT [PK_inv_stock_count_bin] PRIMARY KEY,
            [stock_count_id] BIGINT NOT NULL,
            [bin_id] BIGINT NOT NULL,
            CONSTRAINT [FK_inv_stock_count_bin_stock_count_id]
                FOREIGN KEY ([stock_count_id]) REFERENCES [inv].[stock_count] ([id]),
            CONSTRAINT [FK_inv_stock_count_bin_bin_id] FOREIGN KEY ([bin_id]) REFERENCES [inv].[bin] ([id])
        );
    """)
    op.execute(
        "CREATE UNIQUE INDEX [UX_inv_stock_count_bin_k1] ON [inv].[stock_count_bin] ([stock_count_id], [bin_id]);"
    )
    op.execute("""
        ALTER TABLE [inv].[stock_count_line] ADD
            [counted_at] DATETIME2(0) NULL,
            [is_expected] BIT NOT NULL CONSTRAINT [DF_inv_stock_count_line_is_expected] DEFAULT (1),
            [remarks] NVARCHAR(200) NULL;
    """)
    # One line per item and bin (one per item for stock kept without a bin: unique indexes treat NULLs as equal).
    op.execute("""
        CREATE UNIQUE INDEX [UX_inv_stock_count_line_k1]
            ON [inv].[stock_count_line] ([stock_count_id], [item_id], [bin_id]);
    """)
    for code, description in (
        ("inv.count.manage", "Create stock count sheets and enter counted quantities"),
        ("inv.count.approve", "Review stock count differences and post the count adjustment"),
    ):
        op.execute(f"""
            IF NOT EXISTS (SELECT 1 FROM [core].[permission] WHERE [code] = N'{code}')
                INSERT INTO [core].[permission] ([code], [module], [description])
                VALUES (N'{code}', N'Inventory', N'{description}');
        """)  # noqa: S608 - fixed text
    op.execute("""
        INSERT INTO [core].[role_permission] ([role_id], [permission_id])
        SELECT r.[id], p.[id]
        FROM [core].[role] r
        JOIN [core].[permission] p ON p.[code] = N'inv.count.manage'
        WHERE r.[id] IN (SELECT rp2.[role_id] FROM [core].[role_permission] rp2
                         JOIN [core].[permission] p2 ON p2.[id] = rp2.[permission_id]
                         WHERE p2.[code] = N'inv.transfer.manage')
          AND NOT EXISTS (SELECT 1 FROM [core].[role_permission] rp
                          WHERE rp.[role_id] = r.[id] AND rp.[permission_id] = p.[id]);
    """)
    op.execute("""
        INSERT INTO [core].[role_permission] ([role_id], [permission_id])
        SELECT r.[id], p.[id]
        FROM [core].[role] r
        JOIN [core].[permission] p ON p.[code] = N'inv.count.approve'
        WHERE r.[code] IN (N'ADMIN', N'INVENTORY')
          AND NOT EXISTS (SELECT 1 FROM [core].[role_permission] rp
                          WHERE rp.[role_id] = r.[id] AND rp.[permission_id] = p.[id]);
    """)


def downgrade() -> None:
    op.execute("""
        DELETE rp FROM [core].[role_permission] rp
        JOIN [core].[permission] p ON p.[id] = rp.[permission_id]
        WHERE p.[code] IN (N'inv.count.manage', N'inv.count.approve');
        DELETE FROM [core].[permission] WHERE [code] IN (N'inv.count.manage', N'inv.count.approve');
    """)
    op.execute("DROP INDEX [UX_inv_stock_count_line_k1] ON [inv].[stock_count_line];")
    op.execute("ALTER TABLE [inv].[stock_count_line] DROP CONSTRAINT [DF_inv_stock_count_line_is_expected];")
    op.execute("ALTER TABLE [inv].[stock_count_line] DROP COLUMN [counted_at], [is_expected], [remarks];")
    op.execute("DROP TABLE [inv].[stock_count_bin];")
    op.execute("""
        ALTER TABLE [inv].[stock_count] DROP CONSTRAINT
            [CK_inv_stock_count_scope], [FK_inv_stock_count_storage_rack_id],
            [FK_inv_stock_count_closed_by_user_id], [FK_inv_stock_count_posted_by_user_id],
            [DF_inv_stock_count_scope], [DF_inv_stock_count_is_blind];
    """)
    op.execute("""
        ALTER TABLE [inv].[stock_count] DROP COLUMN
            [scope], [storage_rack_id], [is_blind], [remarks], [closed_at], [closed_by_user_id], [posted_at],
            [posted_by_user_id];
    """)
