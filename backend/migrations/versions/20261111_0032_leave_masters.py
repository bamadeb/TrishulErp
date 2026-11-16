"""Leave type settings, leave policies, and leave permissions.

Extends the existing hr.leave_type table. Policies are new. Balances and
applications stay on hr.leave_balance and hr.leave_request.

Revision ID: 0032_leave_masters
Revises: 0031_template_designation_grades
Created: 2026-11-11
"""

from alembic import op

revision = "0032_leave_masters"
down_revision = "0031_template_designation_grades"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        IF OBJECT_ID(N'hr.leave_type_setting', N'U') IS NULL
        CREATE TABLE [hr].[leave_type_setting] (
            [leave_type_id] BIGINT NOT NULL CONSTRAINT [PK_hr_leave_type_setting] PRIMARY KEY
                CONSTRAINT [FK_hr_leave_type_setting_type] REFERENCES [hr].[leave_type]([id]),
            [description] NVARCHAR(400) NULL,
            [accrual_applicable] BIT NOT NULL CONSTRAINT [DF_hr_leave_type_setting_accrual] DEFAULT (0),
            [half_day_allowed] BIT NOT NULL CONSTRAINT [DF_hr_leave_type_setting_half_day] DEFAULT (1),
            [attachment_required] BIT NOT NULL CONSTRAINT [DF_hr_leave_type_setting_attachment] DEFAULT (0),
            [max_consecutive_days] SMALLINT NULL
        );
    """)
    op.execute("""
        IF OBJECT_ID(N'hr.leave_policy', N'U') IS NULL
        CREATE TABLE [hr].[leave_policy] (
            [id] BIGINT IDENTITY(1, 1) NOT NULL CONSTRAINT [PK_hr_leave_policy] PRIMARY KEY,
            [name] NVARCHAR(80) NOT NULL,
            [employee_type] NVARCHAR(30) NULL,
            [department_id] BIGINT NULL CONSTRAINT [FK_hr_leave_policy_department] REFERENCES [hr].[department]([id]),
            [branch_id] BIGINT NULL CONSTRAINT [FK_hr_leave_policy_branch] REFERENCES [core].[branch]([id]),
            [applies_during_probation] BIT NOT NULL CONSTRAINT [DF_hr_leave_policy_probation] DEFAULT (0),
            [negative_balance_allowed] BIT NOT NULL CONSTRAINT [DF_hr_leave_policy_negative] DEFAULT (0),
            [effective_from] DATE NOT NULL,
            [effective_to] DATE NULL,
            [created_at] DATETIME2(0) NOT NULL CONSTRAINT [DF_hr_leave_policy_created_at] DEFAULT (SYSUTCDATETIME()),
            [created_by_user_id] BIGINT NULL,
            [updated_at] DATETIME2(0) NULL,
            [updated_by_user_id] BIGINT NULL,
            [is_active] BIT NOT NULL CONSTRAINT [DF_hr_leave_policy_is_active] DEFAULT (1),
            [row_version] ROWVERSION NOT NULL,
            CONSTRAINT [CK_hr_leave_policy_category] CHECK (
                [employee_type] IS NULL OR [employee_type] IN (N'Permanent', N'Contract', N'Trainee', N'Consultant')
            ),
            CONSTRAINT [CK_hr_leave_policy_dates] CHECK ([effective_to] IS NULL OR [effective_to] > [effective_from])
        );
    """)
    op.execute("""
        IF OBJECT_ID(N'hr.leave_policy_line', N'U') IS NULL
        CREATE TABLE [hr].[leave_policy_line] (
            [id] BIGINT IDENTITY(1, 1) NOT NULL CONSTRAINT [PK_hr_leave_policy_line] PRIMARY KEY,
            [leave_policy_id] BIGINT NOT NULL CONSTRAINT [FK_hr_leave_policy_line_policy] REFERENCES [hr].[leave_policy]([id]),
            [leave_type_id] BIGINT NOT NULL CONSTRAINT [FK_hr_leave_policy_line_type] REFERENCES [hr].[leave_type]([id]),
            [annual_entitlement] DECIMAL(6, 1) NOT NULL,
            [accrual_frequency] NVARCHAR(20) NOT NULL,
            [carry_forward] BIT NOT NULL CONSTRAINT [DF_hr_leave_policy_line_carry] DEFAULT (0),
            [max_accumulation] DECIMAL(6, 1) NULL,
            [encashment_eligible] BIT NOT NULL CONSTRAINT [DF_hr_leave_policy_line_encash] DEFAULT (0),
            [created_at] DATETIME2(0) NOT NULL CONSTRAINT [DF_hr_leave_policy_line_created_at] DEFAULT (SYSUTCDATETIME()),
            [created_by_user_id] BIGINT NULL,
            [updated_at] DATETIME2(0) NULL,
            [updated_by_user_id] BIGINT NULL,
            [is_active] BIT NOT NULL CONSTRAINT [DF_hr_leave_policy_line_is_active] DEFAULT (1),
            [row_version] ROWVERSION NOT NULL,
            CONSTRAINT [UQ_hr_leave_policy_line] UNIQUE ([leave_policy_id], [leave_type_id]),
            CONSTRAINT [CK_hr_leave_policy_line_accrual] CHECK (
                [accrual_frequency] IN (N'None', N'Monthly', N'Yearly')
            )
        );
    """)
    op.execute("""
        INSERT INTO [hr].[leave_type] ([code], [name], [is_paid], [is_encashable])
        SELECT v.[code], v.[name], v.[is_paid], v.[is_encashable]
        FROM (VALUES
            (N'CL', N'Casual Leave', 1, 0),
            (N'EL', N'Earned Leave', 1, 1),
            (N'SL', N'Sick Leave', 1, 0),
            (N'CO', N'Compensatory Off', 1, 0),
            (N'ML', N'Maternity Leave', 1, 0),
            (N'PL', N'Paternity Leave', 1, 0),
            (N'LWP', N'Leave Without Pay', 0, 0)
        ) v([code], [name], [is_paid], [is_encashable])
        WHERE NOT EXISTS (SELECT 1 FROM [hr].[leave_type] t WHERE t.[code] = v.[code]);
    """)
    op.execute("""
        INSERT INTO [core].[permission] ([code], [module], [description])
        SELECT v.[code], N'HR', v.[description]
        FROM (VALUES
            (N'hr.leave.view', N'See leave types, policies, balances and own leave'),
            (N'hr.leave.apply', N'Apply for own leave'),
            (N'hr.leave.approve', N'Approve or reject another employee''s leave'),
            (N'hr.leave.manage', N'Configure leave types and policies and adjust balances')
        ) v([code], [description])
        WHERE NOT EXISTS (SELECT 1 FROM [core].[permission] p WHERE p.[code] = v.[code]);
    """)
    op.execute("""
        INSERT INTO [core].[role_permission] ([role_id], [permission_id])
        SELECT r.[id], p.[id]
        FROM (VALUES
            (N'ADMIN', N'hr.leave.view'), (N'ADMIN', N'hr.leave.apply'),
            (N'ADMIN', N'hr.leave.approve'), (N'ADMIN', N'hr.leave.manage'),
            (N'HR', N'hr.leave.view'), (N'HR', N'hr.leave.apply'), (N'HR', N'hr.leave.manage'),
            (N'MANAGEMENT', N'hr.leave.view'), (N'MANAGEMENT', N'hr.leave.approve'),
            (N'TEAM_LEAD', N'hr.leave.view'), (N'TEAM_LEAD', N'hr.leave.apply'), (N'TEAM_LEAD', N'hr.leave.approve'),
            (N'SALES_MANAGER', N'hr.leave.view'), (N'SALES_MANAGER', N'hr.leave.apply'), (N'SALES_MANAGER', N'hr.leave.approve'),
            (N'SERVICE_ENGINEER', N'hr.leave.view'), (N'SERVICE_ENGINEER', N'hr.leave.apply'),
            (N'SALESPERSON', N'hr.leave.view'), (N'SALESPERSON', N'hr.leave.apply'),
            (N'BACK_OFFICE', N'hr.leave.view'), (N'BACK_OFFICE', N'hr.leave.apply'),
            (N'ACCOUNTS', N'hr.leave.view'), (N'ACCOUNTS', N'hr.leave.apply'),
            (N'BRAND_MANAGER', N'hr.leave.view'), (N'BRAND_MANAGER', N'hr.leave.apply'),
            (N'WAREHOUSE', N'hr.leave.view'), (N'WAREHOUSE', N'hr.leave.apply'),
            (N'PURCHASE', N'hr.leave.view'), (N'PURCHASE', N'hr.leave.apply')
        ) v([role_code], [permission_code])
        JOIN [core].[role] r ON r.[code] = v.[role_code]
        JOIN [core].[permission] p ON p.[code] = v.[permission_code]
        WHERE NOT EXISTS (
            SELECT 1 FROM [core].[role_permission] rp
            WHERE rp.[role_id] = r.[id] AND rp.[permission_id] = p.[id]
        );
    """)


def downgrade() -> None:
    op.execute("""
        DELETE rp FROM [core].[role_permission] rp
        JOIN [core].[permission] p ON p.[id] = rp.[permission_id]
        WHERE p.[code] IN (N'hr.leave.view', N'hr.leave.apply', N'hr.leave.approve', N'hr.leave.manage');
        DELETE FROM [core].[permission]
        WHERE [code] IN (N'hr.leave.view', N'hr.leave.apply', N'hr.leave.approve', N'hr.leave.manage');
    """)
    op.execute("IF OBJECT_ID(N'hr.leave_policy_line', N'U') IS NOT NULL DROP TABLE [hr].[leave_policy_line];")
    op.execute("IF OBJECT_ID(N'hr.leave_policy', N'U') IS NOT NULL DROP TABLE [hr].[leave_policy];")
    op.execute("IF OBJECT_ID(N'hr.leave_type_setting', N'U') IS NOT NULL DROP TABLE [hr].[leave_type_setting];")
