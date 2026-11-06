"""Permissions for the Documents administration screen.

core.document.view    see every document of every module (the Administration > Documents library)
core.document.manage  rename and remove any document

Granted to ADMIN. No new tables: documents are core.attachment rows.

Idempotent: every statement checks first.

Revision ID: 0022_document_permissions
Revises: 0021_tracking_config
Created: 2026-11-06
"""

from alembic import op

revision = "0022_document_permissions"
down_revision = "0021_tracking_config"
branch_labels = None
depends_on = None

_CODES = ("core.document.view", "core.document.manage")


def upgrade() -> None:
    op.execute("""
        INSERT INTO [core].[permission] ([code], [module], [description])
        SELECT v.[code], N'Core', v.[description]
        FROM (VALUES
            (N'core.document.view', N'See every document of every module in the Documents library'),
            (N'core.document.manage', N'Rename and remove any document in the Documents library')
        ) v([code], [description])
        WHERE NOT EXISTS (SELECT 1 FROM [core].[permission] p WHERE p.[code] = v.[code]);
    """)
    op.execute("""
        INSERT INTO [core].[role_permission] ([role_id], [permission_id])
        SELECT r.[id], p.[id]
        FROM [core].[role] r
        JOIN [core].[permission] p ON p.[code] IN (N'core.document.view', N'core.document.manage')
        WHERE r.[code] = N'ADMIN'
          AND NOT EXISTS (
            SELECT 1 FROM [core].[role_permission] rp
            WHERE rp.[role_id] = r.[id] AND rp.[permission_id] = p.[id]);
    """)


def downgrade() -> None:
    op.execute("""
        DELETE rp FROM [core].[role_permission] rp
        JOIN [core].[permission] p ON p.[id] = rp.[permission_id]
        WHERE p.[code] IN (N'core.document.view', N'core.document.manage');
        DELETE FROM [core].[permission] WHERE [code] IN (N'core.document.view', N'core.document.manage');
    """)
