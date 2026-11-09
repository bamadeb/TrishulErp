"""Permission for the inspection checklist screen.

svc.checklist.manage  add and change inspection checklists (svc.checklist_template)

Granted to ADMIN and TEAM_LEAD. svc.report.submit (engineers) already exists. No new tables: the service
report, its checklist answers and the checklist templates are existing svc tables.

Idempotent: every statement checks first.

Revision ID: 0026_service_report_permissions
Revises: 0025_trip_remarks
Created: 2026-11-09
"""

from alembic import op

revision = "0026_service_report_permissions"
down_revision = "0025_trip_remarks"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        INSERT INTO [core].[permission] ([code], [module], [description])
        SELECT N'svc.checklist.manage', N'Service', N'Add and change inspection checklists'
        WHERE NOT EXISTS (SELECT 1 FROM [core].[permission] WHERE [code] = N'svc.checklist.manage');
    """)
    op.execute("""
        INSERT INTO [core].[role_permission] ([role_id], [permission_id])
        SELECT r.[id], p.[id]
        FROM [core].[role] r
        JOIN [core].[permission] p ON p.[code] = N'svc.checklist.manage'
        WHERE r.[code] IN (N'ADMIN', N'TEAM_LEAD')
          AND NOT EXISTS (
            SELECT 1 FROM [core].[role_permission] rp
            WHERE rp.[role_id] = r.[id] AND rp.[permission_id] = p.[id]);
    """)


def downgrade() -> None:
    op.execute("""
        DELETE rp FROM [core].[role_permission] rp
        JOIN [core].[permission] p ON p.[id] = rp.[permission_id]
        WHERE p.[code] = N'svc.checklist.manage';
        DELETE FROM [core].[permission] WHERE [code] = N'svc.checklist.manage';
    """)
