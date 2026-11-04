"""Permissions for Organization Management.

hr.organization.view    see departments, designations, grades, branches, companies and reporting lines
hr.organization.manage  add and change those masters

Granted to ADMIN and HR. No new tables.

Chained after the two remote 0016 heads so it does not fork the alert migration,
which already continues from 0009_user_device_hw.

Revision ID: 0010_organization
Revises: 0016_asc_master, 0016_trk_gps_diagnostics
Created: 2026-11-03
"""

from alembic import op

revision = "0010_organization"
down_revision = ("0016_asc_master", "0016_trk_gps_diagnostics")
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        INSERT INTO [core].[permission] ([code], [module], [description])
        SELECT v.[code], N'HR', v.[description]
        FROM (VALUES
            (N'hr.organization.view', N'See organization departments, designations, grades, branches, companies and reporting lines'),
            (N'hr.organization.manage', N'Add and change organization departments, designations, grades, branches, companies and reporting lines')
        ) v([code], [description])
        WHERE NOT EXISTS (SELECT 1 FROM [core].[permission] p WHERE p.[code] = v.[code]);
    """)
    op.execute("""
        INSERT INTO [core].[role_permission] ([role_id], [permission_id])
        SELECT r.[id], p.[id]
        FROM (VALUES
            (N'ADMIN', N'hr.organization.view'), (N'ADMIN', N'hr.organization.manage'),
            (N'HR', N'hr.organization.view'), (N'HR', N'hr.organization.manage')
        ) v([role_code], [permission_code])
        JOIN [core].[role] r ON r.[code] = v.[role_code]
        JOIN [core].[permission] p ON p.[code] = v.[permission_code]
        WHERE NOT EXISTS (
            SELECT 1 FROM [core].[role_permission] rp
            WHERE rp.[role_id] = r.[id] AND rp.[permission_id] = p.[id]
        );
    """)


def downgrade() -> None:
    op.execute("""
        DELETE rp FROM [core].[role_permission] rp
        JOIN [core].[permission] p ON p.[id] = rp.[permission_id]
        WHERE p.[code] IN (N'hr.organization.view', N'hr.organization.manage');
        DELETE FROM [core].[permission]
        WHERE [code] IN (N'hr.organization.view', N'hr.organization.manage');
    """)
