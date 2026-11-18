"""Close date for a reporting assignment, and a row with no new manager.

Removal keeps the employee active and records the closed relationship.
Alembic upgrade is not used for this database. scripts/apply_reporting_assignment_close.py
applies this SQL on TrishulDev.

Revision ID: 0039_reporting_close
Revises: 0038_reporting_assignment
Created: 2026-11-17
"""

from alembic import op

revision = "0039_reporting_close"
down_revision = "0038_reporting_assignment"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        IF COL_LENGTH(N'hr.reporting_assignment', N'effective_to') IS NULL
            ALTER TABLE hr.reporting_assignment ADD effective_to DATE NULL;
        ALTER TABLE hr.reporting_assignment ALTER COLUMN manager_id BIGINT NULL;
    """)


def downgrade() -> None:
    op.execute("""
        IF COL_LENGTH(N'hr.reporting_assignment', N'effective_to') IS NOT NULL
            ALTER TABLE hr.reporting_assignment DROP COLUMN effective_to;
    """)
