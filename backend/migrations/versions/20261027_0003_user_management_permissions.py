"""Permissions for user management (core.app_user and its Cognito sign-in accounts).

core.user.view    see users, their roles and sign-in status
core.user.manage  add users, change roles / brands, deactivate, reset passwords

Granted to ADMIN only; other roles get them through the admin screens later.

Revision ID: 0003
Revises: 0002
Created: 2026-10-27
"""

from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        INSERT INTO [core].[permission] ([code], [module], [description])
        SELECT v.[code], N'Core', v.[description]
        FROM (VALUES
            (N'core.user.view', N'See users, their roles and sign-in status'),
            (N'core.user.manage', N'Add users, change roles and brands, deactivate, reset passwords')
        ) v([code], [description])
        WHERE NOT EXISTS (SELECT 1 FROM [core].[permission] p WHERE p.[code] = v.[code]);
    """)
    op.execute("""
        INSERT INTO [core].[role_permission] ([role_id], [permission_id])
        SELECT r.[id], p.[id]
        FROM [core].[role] r
        JOIN [core].[permission] p ON p.[code] IN (N'core.user.view', N'core.user.manage')
        WHERE r.[code] = N'ADMIN'
          AND NOT EXISTS (SELECT 1 FROM [core].[role_permission] rp
                          WHERE rp.[role_id] = r.[id] AND rp.[permission_id] = p.[id]);
    """)


def downgrade() -> None:
    op.execute("""
        DELETE rp FROM [core].[role_permission] rp
        JOIN [core].[permission] p ON p.[id] = rp.[permission_id]
        WHERE p.[code] IN (N'core.user.view', N'core.user.manage');
        DELETE FROM [core].[permission] WHERE [code] IN (N'core.user.view', N'core.user.manage');
    """)
