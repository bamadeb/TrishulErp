"""Item list import: a batch log per uploaded file, one line per row, and who may import.

Adds:
  * inv.item_import        one row per uploaded item list: file, who/when, duplicate mode, status and counts.
                           Status: Pending (checked, waiting for confirmation), Processing, Completed,
                           Partially Completed, Failed.
  * inv.item_import_line   one row per row of the file: what the check planned (Create / Update / Skip /
                           Error), what the import did (Created / Updated / Skipped / Failed), the item, the
                           problems found (JSON), the fields an update changed (JSON) and the row as read.
  * permissions
      inv.item.import            upload and import item lists; granted to every role that has inv.item.manage.
      inv.item.import.view       see the item import history; the same roles plus MANAGEMENT.
      inv.item.import.overwrite  update existing items from an item list; ADMIN only.

The items themselves are audited by core.audit_log as usual (the import writes through the ORM).

Revision ID: 0049_item_list_import
Revises: 0048_complaints
Created: 2026-11-26
"""

from alembic import op

revision = "0049_item_list_import"
down_revision = "0048_complaints"
branch_labels = None
depends_on = None

_PERMISSIONS = (
    ("inv.item.import", "Import item lists (Excel / CSV) into the item master"),
    ("inv.item.import.view", "See the history of item list imports and the outcome of each row"),
    ("inv.item.import.overwrite", "Update existing items from an item list import"),
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
    """)


def upgrade() -> None:
    op.execute("""
        CREATE TABLE [inv].[item_import] (
            [id] BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT [PK_inv_item_import] PRIMARY KEY,
            [batch_no] NVARCHAR(20) NULL,
            [company_id] BIGINT NOT NULL,
            [file_name] NVARCHAR(260) NOT NULL,
            [file_key] NVARCHAR(400) NULL,
            [file_size] INT NOT NULL CONSTRAINT [DF_inv_item_import_file_size] DEFAULT (0),
            [duplicate_mode] NVARCHAR(10) NOT NULL CONSTRAINT [DF_inv_item_import_duplicate_mode] DEFAULT (N'Skip'),
            [status] NVARCHAR(20) NOT NULL CONSTRAINT [DF_inv_item_import_status] DEFAULT (N'Pending'),
            [total_rows] INT NOT NULL CONSTRAINT [DF_inv_item_import_total_rows] DEFAULT (0),
            [valid_count] INT NOT NULL CONSTRAINT [DF_inv_item_import_valid_count] DEFAULT (0),
            [created_count] INT NOT NULL CONSTRAINT [DF_inv_item_import_created_count] DEFAULT (0),
            [updated_count] INT NOT NULL CONSTRAINT [DF_inv_item_import_updated_count] DEFAULT (0),
            [failed_count] INT NOT NULL CONSTRAINT [DF_inv_item_import_failed_count] DEFAULT (0),
            [skipped_count] INT NOT NULL CONSTRAINT [DF_inv_item_import_skipped_count] DEFAULT (0),
            [error_message] NVARCHAR(1000) NULL,
            [uploaded_by_user_id] BIGINT NULL,
            [uploaded_at] DATETIME2(0) NOT NULL CONSTRAINT [DF_inv_item_import_uploaded_at] DEFAULT (SYSUTCDATETIME()),
            [confirmed_by_user_id] BIGINT NULL,
            [completed_at] DATETIME2(0) NULL,
            CONSTRAINT [CK_inv_item_import_duplicate_mode] CHECK ([duplicate_mode] IN (N'Skip', N'Update')),
            CONSTRAINT [CK_inv_item_import_status] CHECK ([status] IN
                (N'Pending', N'Processing', N'Completed', N'Partially Completed', N'Failed')),
            CONSTRAINT [FK_inv_item_import_company_id] FOREIGN KEY ([company_id]) REFERENCES [core].[company] ([id]),
            CONSTRAINT [FK_inv_item_import_uploaded_by_user_id]
                FOREIGN KEY ([uploaded_by_user_id]) REFERENCES [core].[app_user] ([id]),
            CONSTRAINT [FK_inv_item_import_confirmed_by_user_id]
                FOREIGN KEY ([confirmed_by_user_id]) REFERENCES [core].[app_user] ([id])
        );
    """)
    op.execute("CREATE INDEX [IX_inv_item_import_uploaded_at] ON [inv].[item_import] ([uploaded_at] DESC);")
    op.execute("""
        CREATE TABLE [inv].[item_import_line] (
            [id] BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT [PK_inv_item_import_line] PRIMARY KEY,
            [import_id] BIGINT NOT NULL,
            [row_number] INT NOT NULL,
            [item_code] NVARCHAR(60) NULL,
            [description] NVARCHAR(200) NULL,
            [action] NVARCHAR(10) NOT NULL,
            [outcome] NVARCHAR(10) NULL,
            [item_id] BIGINT NULL,
            [messages] NVARCHAR(MAX) NULL,
            [changes] NVARCHAR(MAX) NULL,
            [source_data] NVARCHAR(MAX) NULL,
            CONSTRAINT [CK_inv_item_import_line_action] CHECK ([action] IN (N'Create', N'Update', N'Skip', N'Error')),
            CONSTRAINT [CK_inv_item_import_line_outcome] CHECK ([outcome] IN
                (N'Created', N'Updated', N'Skipped', N'Failed')),
            CONSTRAINT [FK_inv_item_import_line_import_id]
                FOREIGN KEY ([import_id]) REFERENCES [inv].[item_import] ([id]),
            CONSTRAINT [FK_inv_item_import_line_item_id] FOREIGN KEY ([item_id]) REFERENCES [core].[item] ([id])
        );
    """)
    op.execute("""
        CREATE INDEX [IX_inv_item_import_line_import_id]
            ON [inv].[item_import_line] ([import_id], [row_number]);
    """)
    for code, description in _PERMISSIONS:
        op.execute(f"""
            IF NOT EXISTS (SELECT 1 FROM [core].[permission] WHERE [code] = N'{code}')
                INSERT INTO [core].[permission] ([code], [module], [description])
                VALUES (N'{code}', N'Inventory', N'{description}');
        """)
    holds_item_manage = """r.[id] IN (SELECT rp2.[role_id] FROM [core].[role_permission] rp2
                          JOIN [core].[permission] p2 ON p2.[id] = rp2.[permission_id]
                          WHERE p2.[code] = N'inv.item.manage')"""
    _grant("inv.item.import", holds_item_manage)
    _grant("inv.item.import.view", f"{holds_item_manage} OR r.[code] = N'MANAGEMENT'")
    _grant("inv.item.import.overwrite", "r.[code] = N'ADMIN'")


def downgrade() -> None:
    for code, _ in _PERMISSIONS:
        op.execute(f"""
            DELETE rp FROM [core].[role_permission] rp
            JOIN [core].[permission] p ON p.[id] = rp.[permission_id]
            WHERE p.[code] = N'{code}';
            DELETE FROM [core].[permission] WHERE [code] = N'{code}';
        """)
    op.execute("DROP TABLE [inv].[item_import_line];")
    op.execute("DROP TABLE [inv].[item_import];")
