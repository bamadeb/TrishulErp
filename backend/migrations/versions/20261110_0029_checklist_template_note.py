"""A note on an inspection checklist (shown to the engineer with the checklist).

svc.checklist_template.inspection_note  NVARCHAR(2000) NULL. Existing checklists keep NULL.

Files attached to a checklist use the common document module (core.attachment); no table change for those.

Idempotent: every statement checks first.

Revision ID: 0029_checklist_template_note
Revises: 0028_merge_service_report_salary
Created: 2026-11-10
"""

from alembic import op

revision = "0029_checklist_template_note"
down_revision = "0028_merge_service_report_salary"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        IF COL_LENGTH(N'svc.checklist_template', N'inspection_note') IS NULL
            ALTER TABLE [svc].[checklist_template] ADD [inspection_note] NVARCHAR(2000) NULL;
    """)


def downgrade() -> None:
    op.execute("""
        IF COL_LENGTH(N'svc.checklist_template', N'inspection_note') IS NOT NULL
            ALTER TABLE [svc].[checklist_template] DROP COLUMN [inspection_note];
    """)
