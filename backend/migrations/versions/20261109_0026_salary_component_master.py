"""Extend the salary component master for the August 2026 salary statement.

hr.salary_component already stores the component code, name, type and calculation.
This adds the configuration the Salary Components screen needs, and an append-only
revision so a later change does not erase the rule a processed payroll used.

Reversals, LOP, LOP reversal, days in the month and effective workdays are not
components. Reversal amounts stay payroll adjustments; the earning only records
whether a reversal is allowed.

No statutory rate, wage ceiling or tax slab is stored here.

Revision ID: 0026_salary_components
Revises: 0025_trip_remarks
Created: 2026-11-09
"""

from alembic import op

revision = "0026_salary_components"
down_revision = "0025_trip_remarks"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        UPDATE [hr].[salary_component]
        SET [calculation_type] = CASE [calculation_type]
            WHEN N'Fixed' THEN N'Fixed Amount'
            WHEN N'Percent of basic' THEN N'Percentage'
            WHEN N'Statutory' THEN N'Formula'
            ELSE [calculation_type]
        END
        WHERE [calculation_type] IN (N'Fixed', N'Percent of basic', N'Statutory');
    """)
    op.execute("""
        IF EXISTS (SELECT 1 FROM sys.check_constraints WHERE [name] = N'CK_hr_salary_component_calculation_type')
            ALTER TABLE [hr].[salary_component] DROP CONSTRAINT [CK_hr_salary_component_calculation_type];
    """)
    op.execute("""
        ALTER TABLE [hr].[salary_component] ADD CONSTRAINT [CK_hr_salary_component_calculation_type]
            CHECK ([calculation_type] IN (N'Fixed Amount', N'Percentage', N'Formula', N'Manual Entry'));
    """)
    op.execute("""
        IF EXISTS (SELECT 1 FROM sys.check_constraints WHERE [name] = N'CK_hr_salary_component_component_type')
            ALTER TABLE [hr].[salary_component] DROP CONSTRAINT [CK_hr_salary_component_component_type];
    """)
    op.execute("""
        ALTER TABLE [hr].[salary_component] ADD CONSTRAINT [CK_hr_salary_component_component_type]
            CHECK ([component_type] IN (N'Earning', N'Deduction', N'Employer contribution', N'Reimbursement'));
    """)
    op.execute("""
        IF COL_LENGTH(N'hr.salary_component', N'description') IS NULL
            ALTER TABLE [hr].[salary_component] ADD
                [description] NVARCHAR(400) NULL,
                [calculation_basis] NVARCHAR(40) NULL,
                [fixed_amount] DECIMAL(18,2) NULL,
                [percentage] DECIMAL(7,4) NULL,
                [formula] NVARCHAR(300) NULL,
                [is_prorated] BIT NOT NULL CONSTRAINT [DF_hr_salary_component_is_prorated] DEFAULT (0),
                [allow_manual_override] BIT NOT NULL CONSTRAINT [DF_hr_salary_component_allow_manual_override] DEFAULT (0),
                [include_in_gross] BIT NOT NULL CONSTRAINT [DF_hr_salary_component_include_in_gross] DEFAULT (0),
                [include_in_net_pay] BIT NOT NULL CONSTRAINT [DF_hr_salary_component_include_in_net_pay] DEFAULT (1),
                [allow_reversal] BIT NOT NULL CONSTRAINT [DF_hr_salary_component_allow_reversal] DEFAULT (0),
                [display_in_statement] BIT NOT NULL CONSTRAINT [DF_hr_salary_component_display_in_statement] DEFAULT (1),
                [display_in_payslip] BIT NOT NULL CONSTRAINT [DF_hr_salary_component_display_in_payslip] DEFAULT (1),
                [display_order] INT NOT NULL CONSTRAINT [DF_hr_salary_component_display_order] DEFAULT (0),
                [effective_from] DATE NOT NULL CONSTRAINT [DF_hr_salary_component_effective_from] DEFAULT ('2026-08-01'),
                [effective_to] DATE NULL,
                CONSTRAINT [CK_hr_salary_component_calculation_basis] CHECK (
                    [calculation_basis] IS NULL OR [calculation_basis] IN (
                        N'Fixed Monthly Amount', N'Basic Salary', N'Gross Earnings',
                        N'Eligible PF Wages', N'Eligible ESI Wages',
                        N'Attendance / Effective Workdays', N'Custom Formula'
                    )
                );
    """)
    op.execute("""
        INSERT INTO [hr].[salary_component] (
            [code], [name], [component_type], [calculation_type], [calculation_basis], [description],
            [is_prorated], [is_taxable], [is_pf_wage], [is_esi_wage], [include_in_gross], [include_in_net_pay],
            [allow_reversal], [allow_manual_override], [display_in_statement], [display_in_payslip],
            [display_order], [effective_from]
        )
        SELECT v.[code], v.[name], v.[component_type], v.[calculation_type], v.[calculation_basis], v.[description],
            v.[is_prorated], v.[is_taxable], v.[is_pf_wage], v.[is_esi_wage], v.[include_in_gross], v.[include_in_net_pay],
            v.[allow_reversal], v.[allow_manual_override], v.[display_in_statement], v.[display_in_payslip],
            v.[display_order], v.[effective_from]
        FROM (VALUES
            (N'BASIC', N'Basic Salary', N'Earning', N'Fixed Amount', N'Attendance / Effective Workdays',
                N'Monthly basic pay. Prorated from attendance. A reversal is a separate payroll adjustment.',
                1, 1, 1, 0, 1, 1, 1, 0, 1, 1, 10, CAST(N'2026-08-01' AS DATE)),
            (N'HRA', N'House Rent Allowance', N'Earning', N'Percentage', N'Basic Salary',
                N'House rent allowance as a percentage of basic. The percentage is set on the component or the salary structure.',
                0, 1, 0, 0, 1, 1, 1, 0, 1, 1, 20, CAST(N'2026-08-01' AS DATE)),
            (N'CONV', N'Conveyance', N'Earning', N'Fixed Amount', N'Fixed Monthly Amount',
                N'Fixed conveyance. A reversal is a separate payroll adjustment.',
                0, 1, 0, 0, 1, 1, 1, 0, 1, 1, 30, CAST(N'2026-08-01' AS DATE)),
            (N'SPL', N'Special Allowance', N'Earning', N'Fixed Amount', N'Fixed Monthly Amount',
                N'Fixed special allowance. A reversal is a separate payroll adjustment.',
                0, 1, 0, 0, 1, 1, 1, 0, 1, 1, 40, CAST(N'2026-08-01' AS DATE)),
            (N'OTH_ALLOW', N'Other Allowance', N'Earning', N'Fixed Amount', N'Fixed Monthly Amount',
                N'Other fixed allowance. A reversal is a separate payroll adjustment.',
                0, 1, 0, 0, 1, 1, 1, 0, 1, 1, 50, CAST(N'2026-08-01' AS DATE)),
            (N'FIX_INC', N'Fixed Incentive', N'Earning', N'Formula', N'Custom Formula',
                N'Incentive by formula. No formula is preset.',
                0, 1, 0, 0, 1, 1, 0, 1, 1, 1, 60, CAST(N'2026-08-01' AS DATE)),
            (N'PF', N'Provident Fund', N'Deduction', N'Formula', N'Eligible PF Wages',
                N'Employee provident fund from the statutory PF rule. No rate is stored on this component.',
                0, 0, 0, 0, 0, 1, 0, 0, 1, 1, 70, CAST(N'2026-08-01' AS DATE)),
            (N'VPF', N'Voluntary Provident Fund', N'Deduction', N'Percentage', N'Eligible PF Wages',
                N'Voluntary provident fund. The percentage is left blank until HR sets it.',
                0, 0, 0, 0, 0, 1, 0, 0, 1, 1, 80, CAST(N'2026-08-01' AS DATE)),
            (N'ESI', N'Employee State Insurance', N'Deduction', N'Formula', N'Eligible ESI Wages',
                N'Employee state insurance from the statutory ESI rule. No rate is stored on this component.',
                0, 0, 0, 0, 0, 1, 0, 0, 1, 1, 90, CAST(N'2026-08-01' AS DATE)),
            (N'IT', N'Income Tax', N'Deduction', N'Formula', N'Custom Formula',
                N'Income tax. The formula or a manual amount is entered later. No tax slab is stored here.',
                0, 0, 0, 0, 0, 1, 0, 1, 1, 1, 100, CAST(N'2026-08-01' AS DATE)),
            (N'LOAN', N'Loan', N'Deduction', N'Manual Entry', CAST(NULL AS NVARCHAR(40)),
                N'Loan recovery. The amount comes from the employee loan record or a manual entry.',
                0, 0, 0, 0, 0, 1, 0, 1, 1, 1, 110, CAST(N'2026-08-01' AS DATE)),
            (N'OTH_LOAN', N'Other Loan', N'Deduction', N'Manual Entry', CAST(NULL AS NVARCHAR(40)),
                N'Other loan recovery. The amount comes from the employee loan record or a manual entry.',
                0, 0, 0, 0, 0, 1, 0, 1, 1, 1, 120, CAST(N'2026-08-01' AS DATE)),
            (N'SAL_ADV', N'Salary Advance', N'Deduction', N'Manual Entry', CAST(NULL AS NVARCHAR(40)),
                N'Salary advance recovery. The amount comes from the advance record or a manual entry.',
                0, 0, 0, 0, 0, 1, 0, 1, 1, 1, 130, CAST(N'2026-08-01' AS DATE)),
            (N'OTH_DED', N'Other Deduction', N'Deduction', N'Manual Entry', CAST(NULL AS NVARCHAR(40)),
                N'Other deduction entered for the payroll month.',
                0, 0, 0, 0, 0, 1, 0, 1, 1, 1, 140, CAST(N'2026-08-01' AS DATE))
        ) v(
            [code], [name], [component_type], [calculation_type], [calculation_basis], [description],
            [is_prorated], [is_taxable], [is_pf_wage], [is_esi_wage], [include_in_gross], [include_in_net_pay],
            [allow_reversal], [allow_manual_override], [display_in_statement], [display_in_payslip],
            [display_order], [effective_from]
        )
        WHERE NOT EXISTS (SELECT 1 FROM [hr].[salary_component] c WHERE c.[code] = v.[code]);
    """)
    op.execute("""
        -- Previous calculation rule for a salary component. Processed payslip amounts are not rewritten.
        IF OBJECT_ID(N'hr.salary_component_revision', N'U') IS NULL
            CREATE TABLE [hr].[salary_component_revision] (
                [id] BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT [PK_hr_salary_component_revision] PRIMARY KEY,
                [salary_component_id] BIGINT NOT NULL,
                [revision_no] INT NOT NULL,
                [code] NVARCHAR(20) NOT NULL,
                [name] NVARCHAR(80) NOT NULL,
                [component_type] NVARCHAR(30) NOT NULL,
                [calculation_type] NVARCHAR(30) NOT NULL,
                [calculation_basis] NVARCHAR(40) NULL,
                [fixed_amount] DECIMAL(18,2) NULL,
                [percentage] DECIMAL(7,4) NULL,
                [formula] NVARCHAR(300) NULL,
                [is_prorated] BIT NOT NULL,
                [is_taxable] BIT NOT NULL,
                [is_pf_wage] BIT NOT NULL,
                [is_esi_wage] BIT NOT NULL,
                [include_in_gross] BIT NOT NULL,
                [include_in_net_pay] BIT NOT NULL,
                [allow_reversal] BIT NOT NULL,
                [allow_manual_override] BIT NOT NULL,
                [display_in_statement] BIT NOT NULL,
                [display_in_payslip] BIT NOT NULL,
                [display_order] INT NOT NULL,
                [effective_from] DATE NOT NULL,
                [effective_to] DATE NULL,
                [is_active] BIT NOT NULL,
                [superseded_at] DATETIME2(0) NOT NULL CONSTRAINT [DF_hr_salary_component_revision_superseded_at] DEFAULT (SYSUTCDATETIME()),
                [created_at] DATETIME2(0) NOT NULL CONSTRAINT [DF_hr_salary_component_revision_created_at] DEFAULT (SYSUTCDATETIME()),
                [created_by_user_id] BIGINT NULL,
                CONSTRAINT [FK_hr_salary_component_revision_salary_component_id] FOREIGN KEY ([salary_component_id]) REFERENCES [hr].[salary_component] ([id]),
                CONSTRAINT [UX_hr_salary_component_revision] UNIQUE ([salary_component_id], [revision_no]),
                CONSTRAINT [CK_hr_salary_component_revision_component_type] CHECK ([component_type] IN (N'Earning', N'Deduction', N'Employer contribution', N'Reimbursement')),
                CONSTRAINT [CK_hr_salary_component_revision_calculation_type] CHECK ([calculation_type] IN (N'Fixed Amount', N'Percentage', N'Formula', N'Manual Entry')),
                CONSTRAINT [CK_hr_salary_component_revision_calculation_basis] CHECK (
                    [calculation_basis] IS NULL OR [calculation_basis] IN (
                        N'Fixed Monthly Amount', N'Basic Salary', N'Gross Earnings',
                        N'Eligible PF Wages', N'Eligible ESI Wages',
                        N'Attendance / Effective Workdays', N'Custom Formula'
                    )
                )
            );
    """)
    op.execute("""
        INSERT INTO [core].[permission] ([code], [module], [description])
        SELECT v.[code], N'HR', v.[description]
        FROM (VALUES
            (N'hr.salary_component.view', N'See salary components'),
            (N'hr.salary_component.manage', N'Add and change salary components, and mark them active or inactive')
        ) v([code], [description])
        WHERE NOT EXISTS (SELECT 1 FROM [core].[permission] p WHERE p.[code] = v.[code]);
    """)
    op.execute("""
        INSERT INTO [core].[role_permission] ([role_id], [permission_id])
        SELECT r.[id], p.[id]
        FROM (VALUES
            (N'ADMIN', N'hr.salary_component.view'), (N'ADMIN', N'hr.salary_component.manage'),
            (N'HR', N'hr.salary_component.view'), (N'HR', N'hr.salary_component.manage')
        ) v([role_code], [permission_code])
        JOIN [core].[role] r ON r.[code] = v.[role_code]
        JOIN [core].[permission] p ON p.[code] = v.[permission_code]
        WHERE NOT EXISTS (
            SELECT 1 FROM [core].[role_permission] rp
            WHERE rp.[role_id] = r.[id] AND rp.[permission_id] = p.[id]
        );
    """)
    op.execute("""
        IF EXISTS (
            SELECT 1 FROM sys.extended_properties ep
            JOIN sys.columns c ON c.[object_id] = ep.[major_id] AND c.[column_id] = ep.[minor_id]
            WHERE ep.[name] = N'MS_Description' AND c.[object_id] = OBJECT_ID(N'hr.salary_component') AND c.[name] = N'calculation_type'
        )
            EXEC sys.sp_updateextendedproperty N'MS_Description', N'How the amount is worked out. Allowed: Fixed Amount, Percentage, Formula, Manual Entry.', N'SCHEMA', N'hr', N'TABLE', N'salary_component', N'COLUMN', N'calculation_type';
        ELSE
            EXEC sys.sp_addextendedproperty N'MS_Description', N'How the amount is worked out. Allowed: Fixed Amount, Percentage, Formula, Manual Entry.', N'SCHEMA', N'hr', N'TABLE', N'salary_component', N'COLUMN', N'calculation_type';
        EXEC sys.sp_addextendedproperty N'MS_Description', N'What the method is applied to.', N'SCHEMA', N'hr', N'TABLE', N'salary_component', N'COLUMN', N'calculation_basis';
        EXEC sys.sp_addextendedproperty N'MS_Description', N'The earning may have a separate reversal adjustment. The reversal is not another component.', N'SCHEMA', N'hr', N'TABLE', N'salary_component', N'COLUMN', N'allow_reversal';
        EXEC sys.sp_addextendedproperty N'MS_Description', N'The rule this row replaced.', N'SCHEMA', N'hr', N'TABLE', N'salary_component_revision';
    """)


def downgrade() -> None:
    op.execute("""
        DELETE rp FROM [core].[role_permission] rp
        JOIN [core].[permission] p ON p.[id] = rp.[permission_id]
        WHERE p.[code] IN (N'hr.salary_component.view', N'hr.salary_component.manage');
        DELETE FROM [core].[permission]
        WHERE [code] IN (N'hr.salary_component.view', N'hr.salary_component.manage');
    """)
    op.execute("""
        IF OBJECT_ID(N'hr.salary_component_revision', N'U') IS NOT NULL
            DROP TABLE [hr].[salary_component_revision];
    """)
    op.execute("""
        DELETE FROM [hr].[salary_component]
        WHERE [code] IN (
            N'BASIC', N'HRA', N'CONV', N'SPL', N'OTH_ALLOW', N'FIX_INC',
            N'PF', N'VPF', N'ESI', N'IT', N'LOAN', N'OTH_LOAN', N'SAL_ADV', N'OTH_DED'
        );
    """)
    op.execute("""
        IF COL_LENGTH(N'hr.salary_component', N'description') IS NOT NULL
            ALTER TABLE [hr].[salary_component] DROP CONSTRAINT [CK_hr_salary_component_calculation_basis];
    """)
    op.execute("""
        IF COL_LENGTH(N'hr.salary_component', N'description') IS NOT NULL
            ALTER TABLE [hr].[salary_component] DROP COLUMN
                [description], [calculation_basis], [fixed_amount], [percentage], [formula],
                [is_prorated], [allow_manual_override], [include_in_gross], [include_in_net_pay],
                [allow_reversal], [display_in_statement], [display_in_payslip], [display_order],
                [effective_from], [effective_to];
    """)
