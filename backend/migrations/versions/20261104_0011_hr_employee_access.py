"""Let the HR role open employee and payroll screens.

core.employee.view and core.employee.manage were granted to ADMIN only.
HR Management is limited to those permissions, so the HR role needs them too.
No other role receives them.

Revision ID: 0011_hr_employee_access
Revises: 0010_organization
Created: 2026-11-04
"""

from alembic import op

revision = "0011_hr_employee_access"
down_revision = "0010_organization"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        INSERT INTO [core].[role_permission] ([role_id], [permission_id])
        SELECT r.[id], p.[id]
        FROM [core].[role] r
        JOIN [core].[permission] p ON p.[code] IN (N'core.employee.view', N'core.employee.manage')
        WHERE r.[code] = N'HR'
          AND NOT EXISTS (
              SELECT 1 FROM [core].[role_permission] rp
              WHERE rp.[role_id] = r.[id] AND rp.[permission_id] = p.[id]
          );
    """)


def downgrade() -> None:
    op.execute("""
        DELETE rp
        FROM [core].[role_permission] rp
        JOIN [core].[role] r ON r.[id] = rp.[role_id]
        JOIN [core].[permission] p ON p.[id] = rp.[permission_id]
        WHERE r.[code] = N'HR'
          AND p.[code] IN (N'core.employee.view', N'core.employee.manage');
    """)
