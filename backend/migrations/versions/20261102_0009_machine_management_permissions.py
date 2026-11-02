"""Permissions for machine management (core.machine_unit, linked to a customer).

core.machine.view    see machines, their owner and details
core.machine.manage  add and change machines, link them to a customer, mark them active/inactive

view:   ADMIN, TEAM_LEAD, BACK_OFFICE, MANAGEMENT
manage: ADMIN, TEAM_LEAD, BACK_OFFICE (the roles that log service calls)

Linking a machine (or a new call) to a customer means searching the customer master, which needs
core.customer.view (until now ADMIN only). It is granted here to the same roles as core.machine.view;
changing customers (core.customer.manage) stays with ADMIN.

Revision ID: 0009_machine_management
Revises: 1e85a20c9857
Created: 2026-11-02 
"""

from alembic import op

revision = "0009_machine_management"
down_revision = "1e85a20c9857"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        INSERT INTO [core].[permission] ([code], [module], [description])
        SELECT v.[code], N'Service', v.[description]
        FROM (VALUES
            (N'core.machine.view', N'See machines, their owner and details'),
            (N'core.machine.manage', N'Add and change machines, link them to a customer, mark them active or inactive')
        ) v([code], [description])
        WHERE NOT EXISTS (SELECT 1 FROM [core].[permission] p WHERE p.[code] = v.[code]);
    """)
    op.execute("""
        INSERT INTO [core].[role_permission] ([role_id], [permission_id])
        SELECT r.[id], p.[id]
        FROM (VALUES
            (N'ADMIN', N'core.machine.view'), (N'ADMIN', N'core.machine.manage'),
            (N'TEAM_LEAD', N'core.machine.view'), (N'TEAM_LEAD', N'core.machine.manage'),
            (N'BACK_OFFICE', N'core.machine.view'), (N'BACK_OFFICE', N'core.machine.manage'),
            (N'MANAGEMENT', N'core.machine.view'),
            (N'TEAM_LEAD', N'core.customer.view'), (N'BACK_OFFICE', N'core.customer.view'),
            (N'MANAGEMENT', N'core.customer.view')
        ) g([role_code], [permission_code])
        JOIN [core].[role] r ON r.[code] = g.[role_code]
        JOIN [core].[permission] p ON p.[code] = g.[permission_code]
        WHERE NOT EXISTS (SELECT 1 FROM [core].[role_permission] rp
                          WHERE rp.[role_id] = r.[id] AND rp.[permission_id] = p.[id]);
    """)


def downgrade() -> None:
    op.execute("""
        DELETE rp FROM [core].[role_permission] rp
        JOIN [core].[permission] p ON p.[id] = rp.[permission_id]
        WHERE p.[code] IN (N'core.machine.view', N'core.machine.manage');
        DELETE FROM [core].[permission] WHERE [code] IN (N'core.machine.view', N'core.machine.manage');
        DELETE rp FROM [core].[role_permission] rp
        JOIN [core].[permission] p ON p.[id] = rp.[permission_id]
        JOIN [core].[role] r ON r.[id] = rp.[role_id]
        WHERE p.[code] = N'core.customer.view' AND r.[code] IN (N'TEAM_LEAD', N'BACK_OFFICE', N'MANAGEMENT');
    """)
