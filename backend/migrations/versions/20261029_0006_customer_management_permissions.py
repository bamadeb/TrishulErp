"""Permissions for customer management (core.customer).

core.customer.view    see customers and their details
core.customer.manage  add and change customers, mark them active/inactive

Granted to ADMIN only; other roles get them through the admin screens later.

Revision ID: 0006
Revises: 0005
Created: 2026-10-29
"""

from alembic import op

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        INSERT INTO [core].[permission] ([code], [module], [description])
        SELECT v.[code], N'Core', v.[description]
        FROM (VALUES
            (N'core.customer.view', N'See customers and their details'),
            (N'core.customer.manage', N'Add and change customers, mark them active or inactive')
        ) v([code], [description])
        WHERE NOT EXISTS (SELECT 1 FROM [core].[permission] p WHERE p.[code] = v.[code]);
    """)
    op.execute("""
        INSERT INTO [core].[role_permission] ([role_id], [permission_id])
        SELECT r.[id], p.[id]
        FROM [core].[role] r
        JOIN [core].[permission] p ON p.[code] IN (N'core.customer.view', N'core.customer.manage')
        WHERE r.[code] = N'ADMIN'
          AND NOT EXISTS (SELECT 1 FROM [core].[role_permission] rp
                          WHERE rp.[role_id] = r.[id] AND rp.[permission_id] = p.[id]);
    """)


def downgrade() -> None:
    op.execute("""
        DELETE rp FROM [core].[role_permission] rp
        JOIN [core].[permission] p ON p.[id] = rp.[permission_id]
        WHERE p.[code] IN (N'core.customer.view', N'core.customer.manage');
        DELETE FROM [core].[permission] WHERE [code] IN (N'core.customer.view', N'core.customer.manage');
    """)
