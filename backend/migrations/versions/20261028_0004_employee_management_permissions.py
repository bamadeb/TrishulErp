"""Permissions for employee management (core.employee).

core.employee.view    see employees and their details
core.employee.manage  add and change employees, mark them active/inactive

Granted to ADMIN only; other roles get them through the admin screens later.

Revision ID: 0004
Revises: 0003
Created: 2026-10-28
"""

from alembic import op

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        INSERT INTO [core].[permission] ([code], [module], [description])
        SELECT v.[code], N'Core', v.[description]
        FROM (VALUES
            (N'core.employee.view', N'See employees and their details'),
            (N'core.employee.manage', N'Add and change employees, mark them active or inactive')
        ) v([code], [description])
        WHERE NOT EXISTS (SELECT 1 FROM [core].[permission] p WHERE p.[code] = v.[code]);
    """)
    op.execute("""
        INSERT INTO [core].[role_permission] ([role_id], [permission_id])
        SELECT r.[id], p.[id]
        FROM [core].[role] r
        JOIN [core].[permission] p ON p.[code] IN (N'core.employee.view', N'core.employee.manage')
        WHERE r.[code] = N'ADMIN'
          AND NOT EXISTS (SELECT 1 FROM [core].[role_permission] rp
                          WHERE rp.[role_id] = r.[id] AND rp.[permission_id] = p.[id]);
    """)


def downgrade() -> None:
    op.execute("""
        DELETE rp FROM [core].[role_permission] rp
        JOIN [core].[permission] p ON p.[id] = rp.[permission_id]
        WHERE p.[code] IN (N'core.employee.view', N'core.employee.manage');
        DELETE FROM [core].[permission] WHERE [code] IN (N'core.employee.view', N'core.employee.manage');
    """)
