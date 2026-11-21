"""Whether a brand's service report must be the full inspection report.

  * core.principal.inspection_report_required   1 = checklist, root cause and sign-off are required (the
    default); 0 = a note or a file is enough. Tata Hitachi was hard-coded as "note or file" until now, so
    it is set to 0 here and nothing changes for it.

Managed on the Configuration screen (core.brand.manage).

Revision ID: 0044_brand_inspection_report
Revises: 0043_brand_company_name
Created: 2026-11-21
"""

from alembic import op

revision = "0044_brand_inspection_report"
down_revision = "0043_brand_company_name"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        IF COL_LENGTH('core.principal', 'inspection_report_required') IS NULL
            ALTER TABLE [core].[principal] ADD [inspection_report_required] BIT NOT NULL
                CONSTRAINT [DF_core_principal_inspection_report_required] DEFAULT (1);
    """)
    op.execute("""
        EXEC sys.sp_addextendedproperty N'MS_Description',
            N'Service reports of this brand need the full inspection report; when off, a note or a file is enough',
            N'SCHEMA', N'core', N'TABLE', N'principal', N'COLUMN', N'inspection_report_required';
    """)
    op.execute("UPDATE [core].[principal] SET [inspection_report_required] = 0 WHERE [code] = N'TATA_HITACHI';")


def downgrade() -> None:
    op.execute("""
        EXEC sys.sp_dropextendedproperty N'MS_Description',
            N'SCHEMA', N'core', N'TABLE', N'principal', N'COLUMN', N'inspection_report_required';
    """)
    op.execute("""
        ALTER TABLE [core].[principal] DROP CONSTRAINT [DF_core_principal_inspection_report_required];
        ALTER TABLE [core].[principal] DROP COLUMN [inspection_report_required];
    """)
