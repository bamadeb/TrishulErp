"""Explicit attendance manage permissions (shifts, rules, finalize).

hr.attendance.shift.manage   create/update/deactivate shifts and shift assignments
hr.attendance.rules.manage   edit organization attendance rules
hr.attendance.finalize       finalize and lock monthly attendance

These are NOT granted to HR or ADMIN automatically — assign via Role Management.
Also merges migration heads 0044_brand_inspection_report and 0043_biometric_foundation.

Revision ID: 0045_attendance_manage_permissions
Revises: 0044_brand_inspection_report, 0043_biometric_foundation
Created: 2026-11-23
"""

from alembic import op

revision = "0045_attendance_manage_permissions"
down_revision = ("0044_brand_inspection_report", "0043_biometric_foundation")
branch_labels = None
depends_on = None

_PERMISSIONS = (
    (
        "hr.attendance.shift.manage",
        "Create, update and deactivate work shifts and employee shift assignments",
    ),
    (
        "hr.attendance.rules.manage",
        "Edit organization attendance rules (grace, overtime, weekly off, etc.)",
    ),
    (
        "hr.attendance.finalize",
        "Finalize and lock monthly attendance for payroll",
    ),
)


def upgrade() -> None:
    for code, description in _PERMISSIONS:
        op.execute(
            f"""
            INSERT INTO [core].[permission] ([code], [module], [description])
            SELECT N'{code}', N'HR', N'{description}'
            WHERE NOT EXISTS (
                SELECT 1 FROM [core].[permission] WHERE [code] = N'{code}'
            );
            """
        )


def downgrade() -> None:
    codes = ", ".join(f"N'{code}'" for code, _ in _PERMISSIONS)
    op.execute(
        f"""
        DELETE rp FROM [core].[role_permission] rp
        JOIN [core].[permission] p ON p.[id] = rp.[permission_id]
        WHERE p.[code] IN ({codes});
        DELETE FROM [core].[permission] WHERE [code] IN ({codes});
        """
    )
