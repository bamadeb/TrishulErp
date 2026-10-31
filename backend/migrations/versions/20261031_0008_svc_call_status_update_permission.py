"""Permission for a Service Engineer to change the status of the calls assigned to them.

svc.call.status.update   change the status of one's own assigned calls (the engineer's progress steps)

Team leads change any call's status through svc.call.assign; closing, cancelling and reopening keep
their own permissions (svc.call.close / svc.call.cancel / svc.call.reopen), which already exist.

Revision ID: 0008_svc_status_update
Revises: 0006_trk_trip_tracking
Created: 2026-10-31
"""

from alembic import op

revision = "0008_svc_status_update"
down_revision = "0006_trk_trip_tracking"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        IF NOT EXISTS (SELECT 1 FROM [core].[permission] WHERE [code] = N'svc.call.status.update')
            INSERT INTO [core].[permission] ([code], [module], [description])
            VALUES (N'svc.call.status.update', N'Service', N'Change the status of calls assigned to oneself');
    """)
    op.execute("""
        INSERT INTO [core].[role_permission] ([role_id], [permission_id])
        SELECT r.[id], p.[id]
        FROM [core].[role] r
        JOIN [core].[permission] p ON p.[code] = N'svc.call.status.update'
        WHERE r.[code] = N'SERVICE_ENGINEER'
          AND NOT EXISTS (SELECT 1 FROM [core].[role_permission] rp
                          WHERE rp.[role_id] = r.[id] AND rp.[permission_id] = p.[id]);
    """)


def downgrade() -> None:
    op.execute("""
        DELETE rp FROM [core].[role_permission] rp
        JOIN [core].[permission] p ON p.[id] = rp.[permission_id]
        WHERE p.[code] = N'svc.call.status.update';
        DELETE FROM [core].[permission] WHERE [code] = N'svc.call.status.update';
    """)
