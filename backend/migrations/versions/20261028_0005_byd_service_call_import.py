"""BYD service-call import: a batch log, unlinked-row tracking on the call, and the import permission.

Adds:
  * svc.byd_call_import         one row per uploaded file (counts + who/when).
  * svc.service_call columns     import_batch_id, external_account_name, external_product_id,
                                 needs_master_linking - so a row whose customer or machine isn't
                                 in our masters yet is still imported and can be linked later.
  * permission svc.call.import   granted to ADMIN and BACK_OFFICE.

Revision ID: 0005
Revises: 0004
Created: 2026-10-28
"""

from alembic import op

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE [svc].[byd_call_import] (
            [id] BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT [PK_svc_byd_call_import] PRIMARY KEY,
            [company_id] BIGINT NOT NULL,
            [branch_id] BIGINT NOT NULL,
            [principal_id] BIGINT NOT NULL,
            [file_name] NVARCHAR(260) NOT NULL,
            [source_kind] NVARCHAR(30) NOT NULL,
            [total_rows] INT NOT NULL CONSTRAINT [DF_svc_byd_call_import_total_rows] DEFAULT (0),
            [inserted_count] INT NOT NULL CONSTRAINT [DF_svc_byd_call_import_inserted_count] DEFAULT (0),
            [updated_count] INT NOT NULL CONSTRAINT [DF_svc_byd_call_import_updated_count] DEFAULT (0),
            [unlinked_count] INT NOT NULL CONSTRAINT [DF_svc_byd_call_import_unlinked_count] DEFAULT (0),
            [failed_count] INT NOT NULL CONSTRAINT [DF_svc_byd_call_import_failed_count] DEFAULT (0),
            [imported_by_user_id] BIGINT NULL,
            [imported_at] DATETIME2(0) NOT NULL
                CONSTRAINT [DF_svc_byd_call_import_imported_at] DEFAULT (SYSUTCDATETIME()),
            CONSTRAINT [CK_svc_byd_call_import_source_kind]
                CHECK ([source_kind] IN (N'Service requests', N'Service orders')),
            CONSTRAINT [FK_svc_byd_call_import_company_id]
                FOREIGN KEY ([company_id]) REFERENCES [core].[company] ([id]),
            CONSTRAINT [FK_svc_byd_call_import_branch_id]
                FOREIGN KEY ([branch_id]) REFERENCES [core].[branch] ([id]),
            CONSTRAINT [FK_svc_byd_call_import_principal_id]
                FOREIGN KEY ([principal_id]) REFERENCES [core].[principal] ([id]),
            CONSTRAINT [FK_svc_byd_call_import_imported_by_user_id]
                FOREIGN KEY ([imported_by_user_id]) REFERENCES [core].[app_user] ([id])
        );
    """)
    op.execute("""
        ALTER TABLE [svc].[service_call] ADD
            [import_batch_id] BIGINT NULL,
            [external_account_name] NVARCHAR(200) NULL,
            [external_product_id] NVARCHAR(40) NULL,
            [needs_master_linking] BIT NOT NULL
                CONSTRAINT [DF_svc_service_call_needs_master_linking] DEFAULT (0),
            CONSTRAINT [FK_svc_service_call_import_batch_id]
                FOREIGN KEY ([import_batch_id]) REFERENCES [svc].[byd_call_import] ([id]);
    """)
    op.execute("""
        IF NOT EXISTS (SELECT 1 FROM [core].[permission] WHERE [code] = N'svc.call.import')
            INSERT INTO [core].[permission] ([code], [module], [description])
            VALUES (N'svc.call.import', N'Service', N'Import service calls from an OEM / BYD export');
    """)
    op.execute("""
        INSERT INTO [core].[role_permission] ([role_id], [permission_id])
        SELECT r.[id], p.[id]
        FROM [core].[role] r
        JOIN [core].[permission] p ON p.[code] = N'svc.call.import'
        WHERE r.[code] IN (N'ADMIN', N'BACK_OFFICE')
          AND NOT EXISTS (SELECT 1 FROM [core].[role_permission] rp
                          WHERE rp.[role_id] = r.[id] AND rp.[permission_id] = p.[id]);
    """)


def downgrade() -> None:
    op.execute("""
        DELETE rp FROM [core].[role_permission] rp
        JOIN [core].[permission] p ON p.[id] = rp.[permission_id]
        WHERE p.[code] = N'svc.call.import';
        DELETE FROM [core].[permission] WHERE [code] = N'svc.call.import';
    """)
    op.execute("""
        ALTER TABLE [svc].[service_call] DROP CONSTRAINT [FK_svc_service_call_import_batch_id];
        ALTER TABLE [svc].[service_call] DROP CONSTRAINT [DF_svc_service_call_needs_master_linking];
        ALTER TABLE [svc].[service_call] DROP COLUMN [import_batch_id], [external_account_name],
            [external_product_id], [needs_master_linking];
    """)
    op.execute("DROP TABLE [svc].[byd_call_import];")
