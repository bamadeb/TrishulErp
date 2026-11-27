"""Warehouse storage phase 2: optional item barcodes, a scan log and the barcode permissions.

Barcodes stay optional: an item without any is handled by its item code (which also prints as a barcode).

  * inv.item_barcode  + source (Manufacturer / Internal / Supplier), is_primary (at most one active primary per
                      item); barcode types also EAN8, UPCA and Other (manufacturer barcodes come in several kinds).
  * inv.scan_log      (new) every scan or typed code looked up: who, when, the value, what it resolved to.
  * permissions
      inv.barcode.manage  add, change and deactivate item barcodes, generate internal ones, print labels;
                          roles that have inv.item.manage.
      inv.barcode.link    link an unknown scanned barcode to an item from the scan screen;
                          roles that have inv.item.manage, plus WAREHOUSE.

Revision ID: 0052_barcodes_scan
Revises: 0051_storage_racks
Created: 2026-11-27
"""

from alembic import op

revision = "0052_barcodes_scan"
down_revision = "0051_storage_racks"
branch_labels = None
depends_on = None

_PERMISSIONS = (
    ("inv.barcode.manage", "Add, change and deactivate item barcodes, generate internal ones and print labels"),
    ("inv.barcode.link", "Link an unknown scanned barcode to an item from the scan screen"),
)
_HOLDS_ITEM_MANAGE = """r.[id] IN (SELECT rp2.[role_id] FROM [core].[role_permission] rp2
                       JOIN [core].[permission] p2 ON p2.[id] = rp2.[permission_id]
                       WHERE p2.[code] = N'inv.item.manage')"""


def _grant(code: str, where: str) -> None:
    op.execute(f"""
        INSERT INTO [core].[role_permission] ([role_id], [permission_id])
        SELECT r.[id], p.[id]
        FROM [core].[role] r
        JOIN [core].[permission] p ON p.[code] = N'{code}'
        WHERE ({where})
          AND NOT EXISTS (SELECT 1 FROM [core].[role_permission] rp
                          WHERE rp.[role_id] = r.[id] AND rp.[permission_id] = p.[id]);
    """)  # noqa: S608 - fixed text


def upgrade() -> None:
    op.execute("ALTER TABLE [inv].[item_barcode] DROP CONSTRAINT [CK_inv_item_barcode_barcode_type];")
    op.execute("""
        ALTER TABLE [inv].[item_barcode] ADD CONSTRAINT [CK_inv_item_barcode_barcode_type]
            CHECK ([barcode_type] IN (N'EAN13', N'EAN8', N'UPCA', N'Code128', N'QR', N'Other'));
    """)
    op.execute("""
        ALTER TABLE [inv].[item_barcode] ADD
            [source] NVARCHAR(20) NOT NULL CONSTRAINT [DF_inv_item_barcode_source] DEFAULT (N'Manufacturer'),
            [is_primary] BIT NOT NULL CONSTRAINT [DF_inv_item_barcode_is_primary] DEFAULT (0),
            CONSTRAINT [CK_inv_item_barcode_source] CHECK ([source] IN (N'Manufacturer', N'Internal', N'Supplier'));
    """)
    op.execute("""
        CREATE UNIQUE INDEX [UX_inv_item_barcode_primary] ON [inv].[item_barcode] ([item_id])
            WHERE [is_primary] = 1 AND [is_active] = 1;
    """)
    # inv.item_barcode already has IX_inv_item_barcode_item_id from the base schema.
    op.execute("""
        CREATE TABLE [inv].[scan_log] (
            [id] BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT [PK_inv_scan_log] PRIMARY KEY,
            [scanned_at] DATETIME2(0) NOT NULL CONSTRAINT [DF_inv_scan_log_scanned_at] DEFAULT (SYSUTCDATETIME()),
            [user_id] BIGINT NULL,
            [scanned_value] NVARCHAR(100) NOT NULL,
            [resolved_type] NVARCHAR(10) NOT NULL,
            [resolved_id] BIGINT NULL,
            [match_count] INT NOT NULL CONSTRAINT [DF_inv_scan_log_match_count] DEFAULT (0),
            [screen] NVARCHAR(40) NULL,
            CONSTRAINT [CK_inv_scan_log_resolved_type]
                CHECK ([resolved_type] IN (N'Item', N'Bin', N'Rack', N'Location', N'Many', N'Unknown')),
            CONSTRAINT [FK_inv_scan_log_user_id] FOREIGN KEY ([user_id]) REFERENCES [core].[app_user] ([id])
        );
    """)
    op.execute("CREATE INDEX [IX_inv_scan_log_scanned_at] ON [inv].[scan_log] ([scanned_at] DESC);")
    for code, description in _PERMISSIONS:
        op.execute(f"""
            IF NOT EXISTS (SELECT 1 FROM [core].[permission] WHERE [code] = N'{code}')
                INSERT INTO [core].[permission] ([code], [module], [description])
                VALUES (N'{code}', N'Inventory', N'{description}');
        """)  # noqa: S608 - fixed text
    _grant("inv.barcode.manage", _HOLDS_ITEM_MANAGE)
    _grant("inv.barcode.link", f"{_HOLDS_ITEM_MANAGE} OR r.[code] = N'WAREHOUSE'")


def downgrade() -> None:
    for code, _ in _PERMISSIONS:
        op.execute(f"""
            DELETE rp FROM [core].[role_permission] rp
            JOIN [core].[permission] p ON p.[id] = rp.[permission_id]
            WHERE p.[code] = N'{code}';
            DELETE FROM [core].[permission] WHERE [code] = N'{code}';
        """)  # noqa: S608 - fixed text
    op.execute("DROP TABLE [inv].[scan_log];")
    op.execute("DROP INDEX [UX_inv_item_barcode_primary] ON [inv].[item_barcode];")
    op.execute("""
        ALTER TABLE [inv].[item_barcode] DROP CONSTRAINT [CK_inv_item_barcode_source], [DF_inv_item_barcode_source],
            [DF_inv_item_barcode_is_primary];
        ALTER TABLE [inv].[item_barcode] DROP COLUMN [source], [is_primary];
    """)
    op.execute("ALTER TABLE [inv].[item_barcode] DROP CONSTRAINT [CK_inv_item_barcode_barcode_type];")
    op.execute("""
        ALTER TABLE [inv].[item_barcode] ADD CONSTRAINT [CK_inv_item_barcode_barcode_type]
            CHECK ([barcode_type] IN (N'EAN13', N'Code128', N'QR'));
    """)
