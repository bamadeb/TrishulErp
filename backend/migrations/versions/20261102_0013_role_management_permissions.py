"""Permissions for role management (core.role and the permissions each role grants).

core.role.view    see roles and the permissions each one grants
core.role.manage  add and change roles, choose their permissions, mark them active or inactive

Both: ADMIN only.

Revision ID: 0013_role_management
Revises: 0012_trk_master_data
Created: 2026-11-02
"""

from alembic import op

revision = "0013_role_management"
down_revision = "0012_trk_master_data"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        INSERT INTO [core].[permission] ([code], [module], [description])
        SELECT v.[code], N'Core', v.[description]
        FROM (VALUES
            (N'core.role.view', N'See roles and the permissions each one grants'),
            (N'core.role.manage', N'Add and change roles, choose their permissions, mark them active or inactive')
        ) v([code], [description])
        WHERE NOT EXISTS (SELECT 1 FROM [core].[permission] p WHERE p.[code] = v.[code]);
    """)
    op.execute("""
        INSERT INTO [core].[role_permission] ([role_id], [permission_id])
        SELECT r.[id], p.[id]
        FROM [core].[role] r
        JOIN [core].[permission] p ON p.[code] IN (N'core.role.view', N'core.role.manage')
        WHERE r.[code] = N'ADMIN'
          AND NOT EXISTS (SELECT 1 FROM [core].[role_permission] rp
                          WHERE rp.[role_id] = r.[id] AND rp.[permission_id] = p.[id]);
    """)


def downgrade() -> None:
    op.execute("""
        DELETE rp FROM [core].[role_permission] rp
        JOIN [core].[permission] p ON p.[id] = rp.[permission_id]
        WHERE p.[code] IN (N'core.role.view', N'core.role.manage');
        DELETE FROM [core].[permission] WHERE [code] IN (N'core.role.view', N'core.role.manage');
    """)
