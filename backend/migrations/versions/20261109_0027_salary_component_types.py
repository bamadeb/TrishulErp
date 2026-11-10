"""Rename salary component categories without changing calculation rules.

Deduction becomes Employee Deduction. Employer contribution becomes
Employer Contribution. Informational is added. An employer contribution is
not part of employee net pay. Rates, formulas, amounts and bases are left
as they are.

Revision ID: 0027_salary_component_types
Revises: 0026_salary_components
Created: 2026-11-09
"""

from alembic import op

revision = "0027_salary_component_types"
down_revision = "0026_salary_components"
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.execute("""
        IF EXISTS (SELECT 1 FROM sys.check_constraints WHERE [name] = N'CK_hr_salary_component_component_type')
            ALTER TABLE [hr].[salary_component] DROP CONSTRAINT [CK_hr_salary_component_component_type];
    """)
    op.execute("""
        UPDATE [hr].[salary_component]
        SET [component_type] = N'Employee Deduction'
        WHERE [component_type] = N'Deduction';
    """)
    op.execute("""
        UPDATE [hr].[salary_component]
        SET [component_type] = N'Employer Contribution'
        WHERE [component_type] = N'Employer contribution';
    """)
    op.execute("""
        UPDATE [hr].[salary_component]
        SET [include_in_net_pay] = 0
        WHERE [component_type] = N'Employer Contribution' AND [include_in_net_pay] = 1;
    """)
    op.execute("""
        ALTER TABLE [hr].[salary_component] ADD CONSTRAINT [CK_hr_salary_component_component_type]
            CHECK ([component_type] IN (N'Earning', N'Employee Deduction', N'Employer Contribution', N'Reimbursement', N'Informational'));
    """)
    op.execute("""
        IF EXISTS (SELECT 1 FROM sys.check_constraints WHERE [name] = N'CK_hr_salary_component_revision_component_type')
            ALTER TABLE [hr].[salary_component_revision] DROP CONSTRAINT [CK_hr_salary_component_revision_component_type];
    """)
    op.execute("""
        IF OBJECT_ID(N'hr.salary_component_revision', N'U') IS NOT NULL
            UPDATE [hr].[salary_component_revision]
            SET [component_type] = CASE [component_type]
                WHEN N'Deduction' THEN N'Employee Deduction'
                WHEN N'Employer contribution' THEN N'Employer Contribution'
                ELSE [component_type]
            END
            WHERE [component_type] IN (N'Deduction', N'Employer contribution');
    """)
    op.execute("""
        IF OBJECT_ID(N'hr.salary_component_revision', N'U') IS NOT NULL
            ALTER TABLE [hr].[salary_component_revision] ADD CONSTRAINT [CK_hr_salary_component_revision_component_type]
                CHECK ([component_type] IN (N'Earning', N'Employee Deduction', N'Employer Contribution', N'Reimbursement', N'Informational'));
    """)


def downgrade() -> None:
    op.execute("""
        IF EXISTS (SELECT 1 FROM sys.check_constraints WHERE [name] = N'CK_hr_salary_component_component_type')
            ALTER TABLE [hr].[salary_component] DROP CONSTRAINT [CK_hr_salary_component_component_type];
    """)
    op.execute("""
        UPDATE [hr].[salary_component]
        SET [component_type] = N'Deduction'
        WHERE [component_type] IN (N'Employee Deduction', N'Informational');
    """)
    op.execute("""
        UPDATE [hr].[salary_component]
        SET [component_type] = N'Employer contribution'
        WHERE [component_type] = N'Employer Contribution';
    """)
    op.execute("""
        ALTER TABLE [hr].[salary_component] ADD CONSTRAINT [CK_hr_salary_component_component_type]
            CHECK ([component_type] IN (N'Earning', N'Deduction', N'Employer contribution', N'Reimbursement'));
    """)
