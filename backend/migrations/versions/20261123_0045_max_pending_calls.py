"""The most pending calls an engineer may have before no new call can be assigned.

  * core.system_setting row SERVICE_MAX_PENDING_CALLS (global), default 3.
  * Permission svc.config.manage (Admin): change it on the Configuration screen.

Revision ID: 0045_max_pending_calls
Revises: 0044_brand_inspection_report
Created: 2026-11-23
"""

from alembic import op

revision = "0045_max_pending_calls"
down_revision = "0044_brand_inspection_report"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        IF NOT EXISTS (SELECT 1 FROM [core].[system_setting]
                       WHERE [setting_key] = N'SERVICE_MAX_PENDING_CALLS' AND [company_id] IS NULL)
            INSERT INTO [core].[system_setting] ([company_id], [setting_key], [setting_value], [data_type], [description])
            VALUES (NULL, N'SERVICE_MAX_PENDING_CALLS', N'3', N'Number',
                    N'An engineer with more pending calls than this cannot be given another');
    """)
    op.execute("""
        IF NOT EXISTS (SELECT 1 FROM [core].[permission] WHERE [code] = N'svc.config.manage')
            INSERT INTO [core].[permission] ([code], [module], [description])
            VALUES (N'svc.config.manage', N'Service', N'Change service settings, such as the pending-call limit per engineer');
    """)
    op.execute("""
        INSERT INTO [core].[role_permission] ([role_id], [permission_id])
        SELECT r.[id], p.[id]
        FROM [core].[role] r
        JOIN [core].[permission] p ON p.[code] = N'svc.config.manage'
        WHERE r.[code] = N'ADMIN'
          AND NOT EXISTS (
            SELECT 1 FROM [core].[role_permission] rp
            WHERE rp.[role_id] = r.[id] AND rp.[permission_id] = p.[id]);
    """)


def downgrade() -> None:
    op.execute("""
        DELETE rp FROM [core].[role_permission] rp
        JOIN [core].[permission] p ON p.[id] = rp.[permission_id]
        WHERE p.[code] = N'svc.config.manage';
        DELETE FROM [core].[permission] WHERE [code] = N'svc.config.manage';
        DELETE FROM [core].[system_setting] WHERE [setting_key] = N'SERVICE_MAX_PENDING_CALLS' AND [company_id] IS NULL;
    """)
