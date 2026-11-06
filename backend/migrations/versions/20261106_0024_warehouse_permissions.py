"""Permissions for the Administration > Warehouses screen.

core.warehouse.view    see warehouses and which branch each one supplies
core.warehouse.manage  add, rename, activate and deactivate warehouses; set a branch's warehouse

Granted to ADMIN. No new tables: warehouses are core.branch rows of type Warehouse.

Idempotent: every statement checks first.

Revision ID: 0024_warehouse_permissions
Revises: 0023_warehouse_regions
Created: 2026-11-06
"""

from alembic import op

revision = "0024_warehouse_permissions"
down_revision = "0023_warehouse_regions"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        INSERT INTO [core].[permission] ([code], [module], [description])
        SELECT v.[code], N'Core', v.[description]
        FROM (VALUES
            (N'core.warehouse.view', N'See warehouses and the branches each one supplies'),
            (N'core.warehouse.manage', N'Add and change warehouses and set the warehouse of a branch')
        ) v([code], [description])
        WHERE NOT EXISTS (SELECT 1 FROM [core].[permission] p WHERE p.[code] = v.[code]);
    """)
    op.execute("""
        INSERT INTO [core].[role_permission] ([role_id], [permission_id])
        SELECT r.[id], p.[id]
        FROM [core].[role] r
        JOIN [core].[permission] p ON p.[code] IN (N'core.warehouse.view', N'core.warehouse.manage')
        WHERE r.[code] = N'ADMIN'
          AND NOT EXISTS (
            SELECT 1 FROM [core].[role_permission] rp
            WHERE rp.[role_id] = r.[id] AND rp.[permission_id] = p.[id]);
    """)


def downgrade() -> None:
    op.execute("""
        DELETE rp FROM [core].[role_permission] rp
        JOIN [core].[permission] p ON p.[id] = rp.[permission_id]
        WHERE p.[code] IN (N'core.warehouse.view', N'core.warehouse.manage');
        DELETE FROM [core].[permission] WHERE [code] IN (N'core.warehouse.view', N'core.warehouse.manage');
    """)
