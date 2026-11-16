"""Join the three migration heads into one. No schema change.

- 0037_call_quotation_sent (service: 'Quotation sent' call status)
- 0037_leave_backdate (HR leave)
- 0011_hr_employee_access (an older HR revision nothing had continued from)

Revision ID: 0038_merge_heads
Revises: 0037_call_quotation_sent, 0037_leave_backdate, 0011_hr_employee_access
Created: 2026-11-16
"""

revision = "0038_merge_heads"
down_revision = ("0037_call_quotation_sent", "0037_leave_backdate", "0011_hr_employee_access")
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
