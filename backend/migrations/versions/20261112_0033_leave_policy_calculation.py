"""Leave policy year, assignment mode, and entitlement calculation.

Existing policies remain fixed entitlements on a financial year with automatic
matching. No policy, assignment, or balance is inserted.

Revision ID: 0033_leave_policy_calculation
Revises: 0032_leave_masters
Created: 2026-11-12
"""

from alembic import op

revision = "0033_leave_policy_calculation"
down_revision = "0032_leave_masters"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        IF COL_LENGTH(N'hr.leave_policy', N'year_basis') IS NULL
        ALTER TABLE [hr].[leave_policy] ADD
            [state_id] BIGINT NULL
                CONSTRAINT [FK_hr_leave_policy_state] REFERENCES [core].[state]([id]),
            [year_basis] NVARCHAR(20) NOT NULL
                CONSTRAINT [DF_hr_leave_policy_year_basis] DEFAULT (N'FINANCIAL'),
            [assignment_mode] NVARCHAR(20) NOT NULL
                CONSTRAINT [DF_hr_leave_policy_assignment_mode] DEFAULT (N'AUTOMATIC');
    """)
    op.execute("""
        IF OBJECT_ID(N'CK_hr_leave_policy_year_basis', N'C') IS NULL
        ALTER TABLE [hr].[leave_policy] ADD CONSTRAINT [CK_hr_leave_policy_year_basis]
            CHECK ([year_basis] IN (N'FINANCIAL', N'CALENDAR'));
        IF OBJECT_ID(N'CK_hr_leave_policy_assignment_mode', N'C') IS NULL
        ALTER TABLE [hr].[leave_policy] ADD CONSTRAINT [CK_hr_leave_policy_assignment_mode]
            CHECK ([assignment_mode] IN (N'AUTOMATIC', N'EXPLICIT'));
    """)
    op.execute("""
        IF COL_LENGTH(N'hr.leave_policy_line', N'calculation_method') IS NULL
        ALTER TABLE [hr].[leave_policy_line] ADD
            [calculation_method] NVARCHAR(20) NOT NULL
                CONSTRAINT [DF_hr_leave_policy_line_method] DEFAULT (N'FIXED'),
            [credit_days] DECIMAL(6, 1) NULL,
            [qualifying_days_per_credit] SMALLINT NULL,
            [minimum_qualifying_days] SMALLINT NULL,
            [joining_year_rule] NVARCHAR(30) NOT NULL
                CONSTRAINT [DF_hr_leave_policy_line_joining_rule] DEFAULT (N'NONE'),
            [minimum_service_months] SMALLINT NULL,
            [adolescent_max_accumulation] DECIMAL(6, 1) NULL,
            [exclude_boundary_holidays] BIT NOT NULL
                CONSTRAINT [DF_hr_leave_policy_line_boundary] DEFAULT (0),
            [document_required] BIT NOT NULL
                CONSTRAINT [DF_hr_leave_policy_line_document] DEFAULT (0),
            [benefit_class] NVARCHAR(20) NOT NULL
                CONSTRAINT [DF_hr_leave_policy_line_benefit] DEFAULT (N'STANDARD'),
            [compensatory_basis] NVARCHAR(30) NOT NULL
                CONSTRAINT [DF_hr_leave_policy_line_comp_basis] DEFAULT (N'NONE'),
            [compensatory_expiry_months] SMALLINT NULL;
    """)
    op.execute("""
        IF OBJECT_ID(N'CK_hr_leave_policy_line_method', N'C') IS NULL
        ALTER TABLE [hr].[leave_policy_line] ADD CONSTRAINT [CK_hr_leave_policy_line_method]
            CHECK ([calculation_method] IN (N'FIXED', N'FORMULA', N'ELIGIBILITY'));
        IF OBJECT_ID(N'CK_hr_leave_policy_line_joining_rule', N'C') IS NULL
        ALTER TABLE [hr].[leave_policy_line] ADD CONSTRAINT [CK_hr_leave_policy_line_joining_rule]
            CHECK ([joining_year_rule] IN (N'NONE', N'TWO_THIRDS_REMAINDER'));
        IF OBJECT_ID(N'CK_hr_leave_policy_line_benefit', N'C') IS NULL
        ALTER TABLE [hr].[leave_policy_line] ADD CONSTRAINT [CK_hr_leave_policy_line_benefit]
            CHECK ([benefit_class] IN (N'STANDARD', N'STATUTORY', N'COMPANY'));
        IF OBJECT_ID(N'CK_hr_leave_policy_line_comp_basis', N'C') IS NULL
        ALTER TABLE [hr].[leave_policy_line] ADD CONSTRAINT [CK_hr_leave_policy_line_comp_basis]
            CHECK ([compensatory_basis] IN (N'NONE', N'STATUTORY_WEEKLY_REST', N'COMPANY_COMP_OFF'));
    """)


def downgrade() -> None:
    op.execute("""
        IF OBJECT_ID(N'CK_hr_leave_policy_line_comp_basis', N'C') IS NOT NULL
            ALTER TABLE [hr].[leave_policy_line] DROP CONSTRAINT [CK_hr_leave_policy_line_comp_basis];
        IF OBJECT_ID(N'CK_hr_leave_policy_line_benefit', N'C') IS NOT NULL
            ALTER TABLE [hr].[leave_policy_line] DROP CONSTRAINT [CK_hr_leave_policy_line_benefit];
        IF OBJECT_ID(N'CK_hr_leave_policy_line_joining_rule', N'C') IS NOT NULL
            ALTER TABLE [hr].[leave_policy_line] DROP CONSTRAINT [CK_hr_leave_policy_line_joining_rule];
        IF OBJECT_ID(N'CK_hr_leave_policy_line_method', N'C') IS NOT NULL
            ALTER TABLE [hr].[leave_policy_line] DROP CONSTRAINT [CK_hr_leave_policy_line_method];
        IF COL_LENGTH(N'hr.leave_policy_line', N'calculation_method') IS NOT NULL
        ALTER TABLE [hr].[leave_policy_line] DROP
            CONSTRAINT [DF_hr_leave_policy_line_method],
            CONSTRAINT [DF_hr_leave_policy_line_joining_rule],
            CONSTRAINT [DF_hr_leave_policy_line_boundary],
            CONSTRAINT [DF_hr_leave_policy_line_document],
            CONSTRAINT [DF_hr_leave_policy_line_benefit],
            CONSTRAINT [DF_hr_leave_policy_line_comp_basis],
            COLUMN [compensatory_expiry_months],
            COLUMN [compensatory_basis],
            COLUMN [benefit_class],
            COLUMN [document_required],
            COLUMN [exclude_boundary_holidays],
            COLUMN [adolescent_max_accumulation],
            COLUMN [minimum_service_months],
            COLUMN [joining_year_rule],
            COLUMN [minimum_qualifying_days],
            COLUMN [qualifying_days_per_credit],
            COLUMN [credit_days],
            COLUMN [calculation_method];
        IF OBJECT_ID(N'CK_hr_leave_policy_assignment_mode', N'C') IS NOT NULL
            ALTER TABLE [hr].[leave_policy] DROP CONSTRAINT [CK_hr_leave_policy_assignment_mode];
        IF OBJECT_ID(N'CK_hr_leave_policy_year_basis', N'C') IS NOT NULL
            ALTER TABLE [hr].[leave_policy] DROP CONSTRAINT [CK_hr_leave_policy_year_basis];
        IF COL_LENGTH(N'hr.leave_policy', N'year_basis') IS NOT NULL
        ALTER TABLE [hr].[leave_policy] DROP
            CONSTRAINT [FK_hr_leave_policy_state],
            CONSTRAINT [DF_hr_leave_policy_year_basis],
            CONSTRAINT [DF_hr_leave_policy_assignment_mode],
            COLUMN [assignment_mode],
            COLUMN [year_basis],
            COLUMN [state_id];
    """)
