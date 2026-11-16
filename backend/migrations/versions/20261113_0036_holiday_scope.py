"""State, notification and description columns on the existing holiday table.

Does not create a second holiday table. National, Festival and Optional remain the stored types.
Regional on the screen is Festival. Alembic upgrade is not used for this database because other
stamped revisions are not in this checkout. scripts/seed_official_holidays.py applies this SQL.

Revision ID: 0036_holiday_scope
Revises: 0034_leave_policy_records
Created: 2026-11-13
"""

from alembic import op

revision = "0036_holiday_scope"
down_revision = "0034_leave_policy_records"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        IF COL_LENGTH(N'hr.holiday', N'state_id') IS NULL
            ALTER TABLE hr.holiday ADD state_id BIGINT NULL;
    """)
    op.execute("""
        IF NOT EXISTS (SELECT 1 FROM sys.foreign_keys WHERE name = N'FK_hr_holiday_state_id')
            ALTER TABLE hr.holiday ADD CONSTRAINT FK_hr_holiday_state_id
                FOREIGN KEY (state_id) REFERENCES core.state(id);
    """)
    op.execute("""
        IF COL_LENGTH(N'hr.holiday', N'source_notification_no') IS NULL
            ALTER TABLE hr.holiday ADD source_notification_no NVARCHAR(40) NULL;
    """)
    op.execute("""
        IF COL_LENGTH(N'hr.holiday', N'source_notification_date') IS NULL
            ALTER TABLE hr.holiday ADD source_notification_date DATE NULL;
    """)
    op.execute("""
        IF COL_LENGTH(N'hr.holiday', N'description') IS NULL
            ALTER TABLE hr.holiday ADD description NVARCHAR(400) NULL;
    """)


def downgrade() -> None:
    op.execute("""
        IF EXISTS (SELECT 1 FROM sys.foreign_keys WHERE name = N'FK_hr_holiday_state_id')
            ALTER TABLE hr.holiday DROP CONSTRAINT FK_hr_holiday_state_id;
    """)
    op.execute("""
        IF COL_LENGTH(N'hr.holiday', N'description') IS NOT NULL
            ALTER TABLE hr.holiday DROP COLUMN description;
    """)
    op.execute("""
        IF COL_LENGTH(N'hr.holiday', N'source_notification_date') IS NOT NULL
            ALTER TABLE hr.holiday DROP COLUMN source_notification_date;
    """)
    op.execute("""
        IF COL_LENGTH(N'hr.holiday', N'source_notification_no') IS NOT NULL
            ALTER TABLE hr.holiday DROP COLUMN source_notification_no;
    """)
    op.execute("""
        IF COL_LENGTH(N'hr.holiday', N'state_id') IS NOT NULL
            ALTER TABLE hr.holiday DROP COLUMN state_id;
    """)
