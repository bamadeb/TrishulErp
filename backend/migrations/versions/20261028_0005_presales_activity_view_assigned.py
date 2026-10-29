"""Add the pre.activity.view.assigned permission for the mobile pre-sales 'my activities' list.

Mirror of svc.call.view.assigned (migration 0004): the list is filtered to the salesperson's own
activities, so the field roles get it, plus office roles that review pipeline.

NOTE: at the time this was written the live DB's alembic_version was stamped at a revision 0005 that
originated on another branch; this revision uses a distinct id and chains from 0004. Reconcile the two
heads with `alembic merge` before the next `alembic upgrade`.

Device registration (core.user_device) needs no new permission: every signed-in user registers their
own device (the endpoint is marked SIGNED_IN_USERS).

Revision ID: 0005_presales_assigned
Revises: 0004
Created: 2026-10-28
"""

from alembic import op

revision = "0005_presales_assigned"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        IF NOT EXISTS (SELECT 1 FROM [core].[permission] WHERE [code] = N'pre.activity.view.assigned')
            INSERT INTO [core].[permission] ([code], [module], [description])
            VALUES (N'pre.activity.view.assigned', N'Presales', N'View own pre-sales activities (mobile)');
    """)
    op.execute("""
        INSERT INTO [core].[role_permission] ([role_id], [permission_id])
        SELECT r.[id], p.[id]
        FROM [core].[role] r
        JOIN [core].[permission] p ON p.[code] = N'pre.activity.view.assigned'
        WHERE r.[code] IN (N'SALESPERSON', N'SALES_MANAGER', N'ADMIN', N'MANAGEMENT')
          AND NOT EXISTS (SELECT 1 FROM [core].[role_permission] rp
                          WHERE rp.[role_id] = r.[id] AND rp.[permission_id] = p.[id]);
    """)


def downgrade() -> None:
    op.execute("""
        DELETE rp FROM [core].[role_permission] rp
        JOIN [core].[permission] p ON p.[id] = rp.[permission_id]
        WHERE p.[code] = N'pre.activity.view.assigned';
        DELETE FROM [core].[permission] WHERE [code] = N'pre.activity.view.assigned';
    """)
