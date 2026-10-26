"""Add the svc.call.view permission used by the service call register.

Granted to office roles. Not to SERVICE_ENGINEER yet: the register is not filtered to the
engineer's own calls, so they would see every call in their branch.

Revision ID: 0001
Revises: v3_baseline
Created: 2026-10-26
"""

from alembic import op

revision = "0001"
down_revision = "v3_baseline"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        IF NOT EXISTS (SELECT 1 FROM [core].[permission] WHERE [code] = N'svc.call.view')
            INSERT INTO [core].[permission] ([code], [module], [description])
            VALUES (N'svc.call.view', N'Service', N'View the service call register');
    """)
    op.execute("""
        INSERT INTO [core].[role_permission] ([role_id], [permission_id])
        SELECT r.[id], p.[id]
        FROM [core].[role] r
        JOIN [core].[permission] p ON p.[code] = N'svc.call.view'
        WHERE r.[code] IN (N'ADMIN', N'BACK_OFFICE', N'TEAM_LEAD', N'MANAGEMENT')
          AND NOT EXISTS (SELECT 1 FROM [core].[role_permission] rp
                          WHERE rp.[role_id] = r.[id] AND rp.[permission_id] = p.[id]);
    """)


def downgrade() -> None:
    op.execute("""
        DELETE rp FROM [core].[role_permission] rp
        JOIN [core].[permission] p ON p.[id] = rp.[permission_id]
        WHERE p.[code] = N'svc.call.view';
        DELETE FROM [core].[permission] WHERE [code] = N'svc.call.view';
    """)
