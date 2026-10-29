"""Add the svc.call.view.assigned permission for the mobile 'my calls' list.

Unlike svc.call.view (the full branch register, office roles only — see migration 0001), this
endpoint is filtered to the engineer's own assigned calls, so SERVICE_ENGINEER gets it. Office
roles that triage and reassign keep it too, so they can see a call from the assignee's point of view.

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
        IF NOT EXISTS (SELECT 1 FROM [core].[permission] WHERE [code] = N'svc.call.view.assigned')
            INSERT INTO [core].[permission] ([code], [module], [description])
            VALUES (N'svc.call.view.assigned', N'Service', N'View service calls assigned to oneself (mobile)');
    """)
    op.execute("""
        INSERT INTO [core].[role_permission] ([role_id], [permission_id])
        SELECT r.[id], p.[id]
        FROM [core].[role] r
        JOIN [core].[permission] p ON p.[code] = N'svc.call.view.assigned'
        WHERE r.[code] IN (N'SERVICE_ENGINEER', N'ADMIN', N'BACK_OFFICE', N'TEAM_LEAD', N'MANAGEMENT')
          AND NOT EXISTS (SELECT 1 FROM [core].[role_permission] rp
                          WHERE rp.[role_id] = r.[id] AND rp.[permission_id] = p.[id]);
    """)


def downgrade() -> None:
    op.execute("""
        DELETE rp FROM [core].[role_permission] rp
        JOIN [core].[permission] p ON p.[id] = rp.[permission_id]
        WHERE p.[code] = N'svc.call.view.assigned';
        DELETE FROM [core].[permission] WHERE [code] = N'svc.call.view.assigned';
    """)
