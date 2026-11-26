"""Bulk item price import: batches, their rows, an add-only price change history, permissions and the limit.

Adds:
  * inv.price_import        one row per uploaded price file: file (+ SHA-256, to catch a repeated file),
                            the price list for selling prices, reason, status, counts, who uploaded /
                            confirmed / approved / rejected it and when.
                            Status: Pending, Pending approval, Processing, Completed, Partially Completed,
                            Failed, Rejected.
  * inv.price_import_line   one row per row of the file: the item, current and new selling / purchase
                            (standard cost) / MRP prices, the % change, whether it is over the limit, the
                            problems found and what the import did.
  * inv.item_price_history  add-only log of every price change of an item (from an import or by hand):
                            old / new selling price (with its price list), purchase price (standard cost)
                            and MRP, who, when, the import batch and the reason. The API never updates or
                            deletes it; UPDATE and DELETE are also denied to the app login when possible.
  * core.system_setting     INV_PRICE_MAX_CHANGE_PCT = 20: a bigger increase or decrease needs approval.
  * permissions
      inv.price.import        upload price files and confirm them; roles that have inv.item.manage.
      inv.price.import.view   see the price import history; the same roles plus MANAGEMENT.
      inv.price.approve       approve price changes over the limit and set the limit; ADMIN.

Revision ID: 0050_price_import
Revises: 0049_item_list_import
Created: 2026-11-26
"""

from alembic import op

revision = "0050_price_import"
down_revision = "0049_item_list_import"
branch_labels = None
depends_on = None

_PERMISSIONS = (
    ("inv.price.import", "Import item price files (Excel / CSV) and confirm the price changes"),
    ("inv.price.import.view", "See the history of item price imports and the old and new prices"),
    ("inv.price.approve", "Approve item price changes over the allowed limit, and set that limit"),
)


def _grant(code: str, where: str) -> None:
    op.execute(f"""
        INSERT INTO [core].[role_permission] ([role_id], [permission_id])
        SELECT r.[id], p.[id]
        FROM [core].[role] r
        JOIN [core].[permission] p ON p.[code] = N'{code}'
        WHERE ({where})
          AND NOT EXISTS (SELECT 1 FROM [core].[role_permission] rp
                          WHERE rp.[role_id] = r.[id] AND rp.[permission_id] = p.[id]);
    """)  # noqa: S608 - fixed text, no user input


def upgrade() -> None:
    op.execute("""
        CREATE TABLE [inv].[price_import] (
            [id] BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT [PK_inv_price_import] PRIMARY KEY,
            [batch_no] NVARCHAR(20) NULL,
            [company_id] BIGINT NOT NULL,
            [file_name] NVARCHAR(260) NOT NULL,
            [file_key] NVARCHAR(400) NULL,
            [file_size] INT NOT NULL CONSTRAINT [DF_inv_price_import_file_size] DEFAULT (0),
            [file_hash] CHAR(64) NOT NULL,
            [file_layout] NVARCHAR(10) NOT NULL CONSTRAINT [DF_inv_price_import_file_layout] DEFAULT (N'Template'),
            [price_list_id] BIGINT NULL,
            [principal_id] BIGINT NULL,
            [sap_price_field] NVARCHAR(10) NULL,
            [reason] NVARCHAR(300) NOT NULL,
            [status] NVARCHAR(20) NOT NULL CONSTRAINT [DF_inv_price_import_status] DEFAULT (N'Pending'),
            [max_change_pct] DECIMAL(9,2) NULL,
            [total_rows] INT NOT NULL CONSTRAINT [DF_inv_price_import_total_rows] DEFAULT (0),
            [valid_count] INT NOT NULL CONSTRAINT [DF_inv_price_import_valid_count] DEFAULT (0),
            [invalid_count] INT NOT NULL CONSTRAINT [DF_inv_price_import_invalid_count] DEFAULT (0),
            [duplicate_count] INT NOT NULL CONSTRAINT [DF_inv_price_import_duplicate_count] DEFAULT (0),
            [changed_count] INT NOT NULL CONSTRAINT [DF_inv_price_import_changed_count] DEFAULT (0),
            [unchanged_count] INT NOT NULL CONSTRAINT [DF_inv_price_import_unchanged_count] DEFAULT (0),
            [over_limit_count] INT NOT NULL CONSTRAINT [DF_inv_price_import_over_limit_count] DEFAULT (0),
            [updated_count] INT NOT NULL CONSTRAINT [DF_inv_price_import_updated_count] DEFAULT (0),
            [failed_count] INT NOT NULL CONSTRAINT [DF_inv_price_import_failed_count] DEFAULT (0),
            [skipped_count] INT NOT NULL CONSTRAINT [DF_inv_price_import_skipped_count] DEFAULT (0),
            [error_message] NVARCHAR(1000) NULL,
            [uploaded_by_user_id] BIGINT NULL,
            [uploaded_at] DATETIME2(0) NOT NULL CONSTRAINT [DF_inv_price_import_uploaded_at] DEFAULT (SYSUTCDATETIME()),
            [confirmed_by_user_id] BIGINT NULL,
            [confirmed_at] DATETIME2(0) NULL,
            [approved_by_user_id] BIGINT NULL,
            [approved_at] DATETIME2(0) NULL,
            [rejected_by_user_id] BIGINT NULL,
            [rejected_at] DATETIME2(0) NULL,
            [decision_note] NVARCHAR(500) NULL,
            [completed_at] DATETIME2(0) NULL,
            CONSTRAINT [CK_inv_price_import_status] CHECK ([status] IN (N'Pending', N'Pending approval',
                N'Processing', N'Completed', N'Partially Completed', N'Failed', N'Rejected')),
            CONSTRAINT [CK_inv_price_import_file_layout] CHECK ([file_layout] IN (N'Template', N'SAP')),
            CONSTRAINT [CK_inv_price_import_sap_price_field]
                CHECK ([sap_price_field] IS NULL OR [sap_price_field] IN (N'Selling', N'Purchase', N'MRP')),
            CONSTRAINT [FK_inv_price_import_company_id] FOREIGN KEY ([company_id]) REFERENCES [core].[company] ([id]),
            CONSTRAINT [FK_inv_price_import_price_list_id]
                FOREIGN KEY ([price_list_id]) REFERENCES [sal].[price_list] ([id]),
            CONSTRAINT [FK_inv_price_import_principal_id]
                FOREIGN KEY ([principal_id]) REFERENCES [core].[principal] ([id]),
            CONSTRAINT [FK_inv_price_import_uploaded_by_user_id]
                FOREIGN KEY ([uploaded_by_user_id]) REFERENCES [core].[app_user] ([id]),
            CONSTRAINT [FK_inv_price_import_confirmed_by_user_id]
                FOREIGN KEY ([confirmed_by_user_id]) REFERENCES [core].[app_user] ([id]),
            CONSTRAINT [FK_inv_price_import_approved_by_user_id]
                FOREIGN KEY ([approved_by_user_id]) REFERENCES [core].[app_user] ([id]),
            CONSTRAINT [FK_inv_price_import_rejected_by_user_id]
                FOREIGN KEY ([rejected_by_user_id]) REFERENCES [core].[app_user] ([id])
        );
    """)
    op.execute("CREATE INDEX [IX_inv_price_import_uploaded_at] ON [inv].[price_import] ([uploaded_at] DESC);")
    op.execute("CREATE INDEX [IX_inv_price_import_file_hash] ON [inv].[price_import] ([file_hash]);")
    op.execute("""
        CREATE TABLE [inv].[price_import_line] (
            [id] BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT [PK_inv_price_import_line] PRIMARY KEY,
            [import_id] BIGINT NOT NULL,
            [row_number] INT NOT NULL,
            [item_code] NVARCHAR(60) NULL,
            [item_id] BIGINT NULL,
            [item_name] NVARCHAR(200) NULL,
            [action] NVARCHAR(10) NOT NULL,
            [outcome] NVARCHAR(10) NULL,
            [old_selling] DECIMAL(18,4) NULL,
            [new_selling] DECIMAL(18,4) NULL,
            [old_purchase] DECIMAL(18,4) NULL,
            [new_purchase] DECIMAL(18,4) NULL,
            [old_mrp] DECIMAL(18,2) NULL,
            [new_mrp] DECIMAL(18,2) NULL,
            [max_change_pct] DECIMAL(9,2) NULL,
            [over_limit] BIT NOT NULL CONSTRAINT [DF_inv_price_import_line_over_limit] DEFAULT (0),
            [reason] NVARCHAR(300) NULL,
            [messages] NVARCHAR(MAX) NULL,
            [source_data] NVARCHAR(MAX) NULL,
            CONSTRAINT [CK_inv_price_import_line_action]
                CHECK ([action] IN (N'Change', N'Unchanged', N'Duplicate', N'Error')),
            CONSTRAINT [CK_inv_price_import_line_outcome]
                CHECK ([outcome] IN (N'Updated', N'Unchanged', N'Skipped', N'Failed')),
            CONSTRAINT [FK_inv_price_import_line_import_id]
                FOREIGN KEY ([import_id]) REFERENCES [inv].[price_import] ([id]),
            CONSTRAINT [FK_inv_price_import_line_item_id] FOREIGN KEY ([item_id]) REFERENCES [core].[item] ([id])
        );
    """)
    op.execute("""
        CREATE INDEX [IX_inv_price_import_line_import_id]
            ON [inv].[price_import_line] ([import_id], [row_number]);
    """)
    op.execute("""
        CREATE TABLE [inv].[item_price_history] (
            [id] BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT [PK_inv_item_price_history] PRIMARY KEY,
            [item_id] BIGINT NOT NULL,
            [item_code] NVARCHAR(40) NOT NULL,
            [price_list_id] BIGINT NULL,
            [min_qty] DECIMAL(18,3) NULL,
            [old_selling] DECIMAL(18,4) NULL,
            [new_selling] DECIMAL(18,4) NULL,
            [old_purchase] DECIMAL(18,4) NULL,
            [new_purchase] DECIMAL(18,4) NULL,
            [old_mrp] DECIMAL(18,2) NULL,
            [new_mrp] DECIMAL(18,2) NULL,
            [source] NVARCHAR(10) NOT NULL,
            [import_id] BIGINT NULL,
            [reason] NVARCHAR(300) NULL,
            [changed_by_user_id] BIGINT NULL,
            [changed_at] DATETIME2(0) NOT NULL CONSTRAINT [DF_inv_item_price_history_changed_at] DEFAULT (SYSUTCDATETIME()),
            CONSTRAINT [CK_inv_item_price_history_source] CHECK ([source] IN (N'Import', N'Manual')),
            CONSTRAINT [FK_inv_item_price_history_item_id] FOREIGN KEY ([item_id]) REFERENCES [core].[item] ([id]),
            CONSTRAINT [FK_inv_item_price_history_price_list_id]
                FOREIGN KEY ([price_list_id]) REFERENCES [sal].[price_list] ([id]),
            CONSTRAINT [FK_inv_item_price_history_import_id]
                FOREIGN KEY ([import_id]) REFERENCES [inv].[price_import] ([id]),
            CONSTRAINT [FK_inv_item_price_history_changed_by_user_id]
                FOREIGN KEY ([changed_by_user_id]) REFERENCES [core].[app_user] ([id])
        );
    """)
    op.execute("""
        CREATE INDEX [IX_inv_item_price_history_item_id]
            ON [inv].[item_price_history] ([item_id], [changed_at] DESC);
    """)
    # History is add-only: take UPDATE and DELETE away from the application login. The migration login may
    # not be allowed to change permissions; then the API alone keeps the rule (it never updates or deletes).
    op.execute("""
        IF DATABASE_PRINCIPAL_ID(N'trishul_app') IS NOT NULL
        BEGIN TRY
            DENY UPDATE, DELETE ON [inv].[item_price_history] TO [trishul_app];
        END TRY
        BEGIN CATCH
            PRINT N'Could not deny UPDATE/DELETE on inv.item_price_history: ' + ERROR_MESSAGE();
        END CATCH
    """)
    op.execute("""
        IF NOT EXISTS (SELECT 1 FROM [core].[system_setting]
                       WHERE [setting_key] = N'INV_PRICE_MAX_CHANGE_PCT' AND [company_id] IS NULL)
            INSERT INTO [core].[system_setting] ([company_id], [setting_key], [setting_value], [data_type], [description])
            VALUES (NULL, N'INV_PRICE_MAX_CHANGE_PCT', N'20', N'Number',
                    N'A price import changing a price by more than this percent needs approval');
    """)
    for code, description in _PERMISSIONS:
        op.execute(f"""
            IF NOT EXISTS (SELECT 1 FROM [core].[permission] WHERE [code] = N'{code}')
                INSERT INTO [core].[permission] ([code], [module], [description])
                VALUES (N'{code}', N'Inventory', N'{description}');
        """)  # noqa: S608 - fixed text, no user input
    holds_item_manage = """r.[id] IN (SELECT rp2.[role_id] FROM [core].[role_permission] rp2
                          JOIN [core].[permission] p2 ON p2.[id] = rp2.[permission_id]
                          WHERE p2.[code] = N'inv.item.manage')"""
    _grant("inv.price.import", holds_item_manage)
    _grant("inv.price.import.view", f"{holds_item_manage} OR r.[code] = N'MANAGEMENT'")
    _grant("inv.price.approve", "r.[code] = N'ADMIN'")


def downgrade() -> None:
    for code, _ in _PERMISSIONS:
        op.execute(f"""
            DELETE rp FROM [core].[role_permission] rp
            JOIN [core].[permission] p ON p.[id] = rp.[permission_id]
            WHERE p.[code] = N'{code}';
            DELETE FROM [core].[permission] WHERE [code] = N'{code}';
        """)  # noqa: S608 - fixed text, no user input
    op.execute("DELETE FROM [core].[system_setting] WHERE [setting_key] = N'INV_PRICE_MAX_CHANGE_PCT';")
    op.execute("DROP TABLE [inv].[item_price_history];")
    op.execute("DROP TABLE [inv].[price_import_line];")
    op.execute("DROP TABLE [inv].[price_import];")
