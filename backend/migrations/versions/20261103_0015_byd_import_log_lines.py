"""BYD import log: one row per line of each uploaded file, and who may read the log.

svc.byd_call_import (migration 0005) holds one row per upload with its counts. This adds what happened to
each row of the file:

  * svc.byd_call_import_line   the row's ticket, what the import did (insert / update / skip), the call
                               it created or updated, match results, messages, and for an update the
                               fields it changed (JSON: [{"field", "from", "to"}]).
  * permission svc.call.import.view   read the import log; granted with svc.call.import (ADMIN,
                               BACK_OFFICE) and to MANAGEMENT. Importing also lets a user read it.

Revision ID: 0015_byd_import_log
Revises: 0014_team_call_visibility
Created: 2026-11-03
"""

from alembic import op

revision = "0015_byd_import_log"
down_revision = "0014_team_call_visibility"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE [svc].[byd_call_import_line] (
            [id] BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT [PK_svc_byd_call_import_line] PRIMARY KEY,
            [import_id] BIGINT NOT NULL,
            [row_number] INT NOT NULL,
            [c4c_ticket_id] NVARCHAR(40) NULL,
            [external_reference] NVARCHAR(150) NULL,
            [subject] NVARCHAR(500) NULL,
            [account] NVARCHAR(200) NULL,
            [action] NVARCHAR(10) NOT NULL,
            [service_call_id] BIGINT NULL,
            [call_no] NVARCHAR(40) NULL,
            [customer_matched] BIT NOT NULL CONSTRAINT [DF_svc_byd_call_import_line_customer_matched] DEFAULT (0),
            [machine_matched] BIT NOT NULL CONSTRAINT [DF_svc_byd_call_import_line_machine_matched] DEFAULT (0),
            [engineer_matched] BIT NOT NULL CONSTRAINT [DF_svc_byd_call_import_line_engineer_matched] DEFAULT (0),
            [needs_linking] BIT NOT NULL CONSTRAINT [DF_svc_byd_call_import_line_needs_linking] DEFAULT (0),
            [messages] NVARCHAR(MAX) NULL,
            [changes] NVARCHAR(MAX) NULL,
            CONSTRAINT [CK_svc_byd_call_import_line_action] CHECK ([action] IN (N'insert', N'update', N'skip')),
            CONSTRAINT [FK_svc_byd_call_import_line_import_id]
                FOREIGN KEY ([import_id]) REFERENCES [svc].[byd_call_import] ([id]),
            CONSTRAINT [FK_svc_byd_call_import_line_service_call_id]
                FOREIGN KEY ([service_call_id]) REFERENCES [svc].[service_call] ([id])
        );
    """)
    op.execute("""
        CREATE INDEX [IX_svc_byd_call_import_line_import_id]
            ON [svc].[byd_call_import_line] ([import_id], [row_number]);
    """)
    op.execute("""
        IF NOT EXISTS (SELECT 1 FROM [core].[permission] WHERE [code] = N'svc.call.import.view')
            INSERT INTO [core].[permission] ([code], [module], [description])
            VALUES (N'svc.call.import.view', N'Service', N'See the log of service-call imports and each row''s outcome');
    """)
    op.execute("""
        INSERT INTO [core].[role_permission] ([role_id], [permission_id])
        SELECT r.[id], p.[id]
        FROM [core].[role] r
        JOIN [core].[permission] p ON p.[code] = N'svc.call.import.view'
        WHERE r.[code] IN (N'ADMIN', N'BACK_OFFICE', N'MANAGEMENT')
          AND NOT EXISTS (SELECT 1 FROM [core].[role_permission] rp
                          WHERE rp.[role_id] = r.[id] AND rp.[permission_id] = p.[id]);
    """)


def downgrade() -> None:
    op.execute("""
        DELETE rp FROM [core].[role_permission] rp
        JOIN [core].[permission] p ON p.[id] = rp.[permission_id]
        WHERE p.[code] = N'svc.call.import.view';
        DELETE FROM [core].[permission] WHERE [code] = N'svc.call.import.view';
    """)
    op.execute("DROP TABLE [svc].[byd_call_import_line];")
