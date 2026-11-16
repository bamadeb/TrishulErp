"""Retrospective date limits on a leave policy line.

Existing leave requests are not changed. A null limit means HR has not set one.
Zero means the leave cannot start before today. Authorization lets HR submit past dates.

Revision ID: 0037_leave_backdate
Revises: 0036_holiday_scope
Created: 2026-11-16
"""

from alembic import op

revision = "0037_leave_backdate"
down_revision = "0036_holiday_scope"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        IF COL_LENGTH(N'hr.leave_policy_line', N'max_backdate_days') IS NULL
            ALTER TABLE hr.leave_policy_line ADD max_backdate_days SMALLINT NULL;
    """)
    op.execute("""
        IF COL_LENGTH(N'hr.leave_policy_line', N'backdate_requires_authorization') IS NULL
            ALTER TABLE hr.leave_policy_line ADD backdate_requires_authorization BIT NOT NULL
                CONSTRAINT DF_hr_leave_policy_line_backdate_hr DEFAULT 0;
    """)
    op.execute("""
        UPDATE line
        SET max_backdate_days = CASE type.code
                WHEN N'CL' THEN 2
                WHEN N'SL' THEN 3
                WHEN N'EL' THEN 0
                WHEN N'CO' THEN 0
                WHEN N'WR' THEN 0
                WHEN N'LWP' THEN 0
            END,
            backdate_requires_authorization = CASE
                WHEN type.code = N'LWP' THEN 1
                ELSE line.backdate_requires_authorization
            END
        FROM hr.leave_policy_line AS line
        INNER JOIN hr.leave_type AS type ON type.id = line.leave_type_id
        WHERE line.max_backdate_days IS NULL
          AND type.code IN (N'CL', N'SL', N'EL', N'CO', N'WR', N'LWP');
    """)
    op.execute("""
        INSERT INTO hr.leave_policy_line (
            leave_policy_id, leave_type_id, annual_entitlement, accrual_frequency,
            max_backdate_days, backdate_requires_authorization
        )
        SELECT policy.id, type.id, 0, N'None', 0, 1
        FROM hr.leave_policy AS policy
        CROSS JOIN hr.leave_type AS type
        WHERE policy.name = N'Odisha Private Company Leave Policy'
          AND type.code = N'LWP'
          AND NOT EXISTS (
              SELECT 1 FROM hr.leave_policy_line AS existing
              WHERE existing.leave_policy_id = policy.id AND existing.leave_type_id = type.id
          );
    """)


def downgrade() -> None:
    op.execute("""
        IF COL_LENGTH(N'hr.leave_policy_line', N'backdate_requires_authorization') IS NOT NULL
            ALTER TABLE hr.leave_policy_line DROP CONSTRAINT DF_hr_leave_policy_line_backdate_hr;
    """)
    op.execute("""
        IF COL_LENGTH(N'hr.leave_policy_line', N'backdate_requires_authorization') IS NOT NULL
            ALTER TABLE hr.leave_policy_line DROP COLUMN backdate_requires_authorization;
    """)
    op.execute("""
        IF COL_LENGTH(N'hr.leave_policy_line', N'max_backdate_days') IS NOT NULL
            ALTER TABLE hr.leave_policy_line DROP COLUMN max_backdate_days;
    """)
