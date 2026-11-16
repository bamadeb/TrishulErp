"""Assignment, entitlement runs, balance transactions, weekly-rest grants, and attendance classes.

These tables do not assign employees, calculate leave, or change existing balances.
Attendance statuses are not seeded.

Revision ID: 0034_leave_policy_records
Revises: 0033_leave_policy_calculation
Created: 2026-11-12
"""

from alembic import op

revision = "0034_leave_policy_records"
down_revision = "0033_leave_policy_calculation"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        IF OBJECT_ID(N'hr.leave_policy_assignment', N'U') IS NULL
        CREATE TABLE [hr].[leave_policy_assignment] (
            [id] BIGINT IDENTITY(1, 1) NOT NULL CONSTRAINT [PK_hr_leave_policy_assignment] PRIMARY KEY,
            [leave_policy_id] BIGINT NOT NULL
                CONSTRAINT [FK_hr_leave_policy_assignment_policy] REFERENCES [hr].[leave_policy]([id]),
            [employee_id] BIGINT NOT NULL
                CONSTRAINT [FK_hr_leave_policy_assignment_employee] REFERENCES [core].[employee]([id]),
            [effective_from] DATE NOT NULL,
            [effective_to] DATE NULL,
            [created_at] DATETIME2(0) NOT NULL
                CONSTRAINT [DF_hr_leave_policy_assignment_created_at] DEFAULT (SYSUTCDATETIME()),
            [created_by_user_id] BIGINT NULL,
            [updated_at] DATETIME2(0) NULL,
            [updated_by_user_id] BIGINT NULL,
            [is_active] BIT NOT NULL CONSTRAINT [DF_hr_leave_policy_assignment_is_active] DEFAULT (1),
            [row_version] ROWVERSION NOT NULL,
            CONSTRAINT [UQ_hr_leave_policy_assignment] UNIQUE ([leave_policy_id], [employee_id], [effective_from]),
            CONSTRAINT [CK_hr_leave_policy_assignment_dates]
                CHECK ([effective_to] IS NULL OR [effective_to] > [effective_from])
        );
        IF NOT EXISTS (
            SELECT 1 FROM sys.indexes
            WHERE [name] = N'IX_hr_leave_policy_assignment_employee' AND [object_id] = OBJECT_ID(N'hr.leave_policy_assignment')
        )
        CREATE INDEX [IX_hr_leave_policy_assignment_employee]
            ON [hr].[leave_policy_assignment] ([employee_id], [effective_from]);
    """)
    op.execute("""
        IF OBJECT_ID(N'hr.leave_entitlement_run', N'U') IS NULL
        CREATE TABLE [hr].[leave_entitlement_run] (
            [id] BIGINT IDENTITY(1, 1) NOT NULL CONSTRAINT [PK_hr_leave_entitlement_run] PRIMARY KEY,
            [employee_id] BIGINT NOT NULL
                CONSTRAINT [FK_hr_leave_entitlement_run_employee] REFERENCES [core].[employee]([id]),
            [leave_policy_line_id] BIGINT NOT NULL
                CONSTRAINT [FK_hr_leave_entitlement_run_line] REFERENCES [hr].[leave_policy_line]([id]),
            [leave_year] SMALLINT NOT NULL,
            [eligibility_days] DECIMAL(7, 1) NOT NULL,
            [days_worked] DECIMAL(7, 1) NOT NULL,
            [deemed_days] DECIMAL(7, 1) NOT NULL,
            [credited_days] DECIMAL(6, 1) NOT NULL,
            [created_at] DATETIME2(0) NOT NULL
                CONSTRAINT [DF_hr_leave_entitlement_run_created_at] DEFAULT (SYSUTCDATETIME()),
            [created_by_user_id] BIGINT NULL,
            [is_active] BIT NOT NULL CONSTRAINT [DF_hr_leave_entitlement_run_is_active] DEFAULT (1),
            [row_version] ROWVERSION NOT NULL,
            CONSTRAINT [UQ_hr_leave_entitlement_run] UNIQUE ([employee_id], [leave_policy_line_id], [leave_year])
        );
    """)
    op.execute("""
        IF OBJECT_ID(N'hr.leave_balance_transaction', N'U') IS NULL
        CREATE TABLE [hr].[leave_balance_transaction] (
            [id] BIGINT IDENTITY(1, 1) NOT NULL CONSTRAINT [PK_hr_leave_balance_transaction] PRIMARY KEY,
            [employee_id] BIGINT NOT NULL
                CONSTRAINT [FK_hr_leave_balance_transaction_employee] REFERENCES [core].[employee]([id]),
            [leave_type_id] BIGINT NOT NULL
                CONSTRAINT [FK_hr_leave_balance_transaction_type] REFERENCES [hr].[leave_type]([id]),
            [leave_year] SMALLINT NOT NULL,
            [leave_balance_id] BIGINT NULL
                CONSTRAINT [FK_hr_leave_balance_transaction_balance] REFERENCES [hr].[leave_balance]([id]),
            [kind] NVARCHAR(20) NOT NULL,
            [days] DECIMAL(6, 1) NOT NULL,
            [remarks] NVARCHAR(300) NULL,
            [source_type] NVARCHAR(40) NULL,
            [source_id] BIGINT NULL,
            [created_at] DATETIME2(0) NOT NULL
                CONSTRAINT [DF_hr_leave_balance_transaction_created_at] DEFAULT (SYSUTCDATETIME()),
            [created_by_user_id] BIGINT NULL,
            [is_active] BIT NOT NULL CONSTRAINT [DF_hr_leave_balance_transaction_is_active] DEFAULT (1),
            [row_version] ROWVERSION NOT NULL,
            CONSTRAINT [CK_hr_leave_balance_transaction_kind] CHECK (
                [kind] IN (N'Credit', N'Debit', N'Expiry', N'Adjustment', N'Reversal')
            )
        );
        IF NOT EXISTS (
            SELECT 1 FROM sys.indexes
            WHERE [name] = N'IX_hr_leave_balance_transaction_employee'
              AND [object_id] = OBJECT_ID(N'hr.leave_balance_transaction')
        )
        CREATE INDEX [IX_hr_leave_balance_transaction_employee]
            ON [hr].[leave_balance_transaction] ([employee_id], [leave_year], [leave_type_id]);
    """)
    op.execute("""
        IF OBJECT_ID(N'hr.leave_weekly_rest_grant', N'U') IS NULL
        CREATE TABLE [hr].[leave_weekly_rest_grant] (
            [id] BIGINT IDENTITY(1, 1) NOT NULL CONSTRAINT [PK_hr_leave_weekly_rest_grant] PRIMARY KEY,
            [employee_id] BIGINT NOT NULL
                CONSTRAINT [FK_hr_leave_weekly_rest_grant_employee] REFERENCES [core].[employee]([id]),
            [leave_policy_line_id] BIGINT NOT NULL
                CONSTRAINT [FK_hr_leave_weekly_rest_grant_line] REFERENCES [hr].[leave_policy_line]([id]),
            [original_holiday_date] DATE NOT NULL,
            [granted_on] DATE NOT NULL,
            [expires_on] DATE NOT NULL,
            [days] DECIMAL(4, 1) NOT NULL,
            [created_at] DATETIME2(0) NOT NULL
                CONSTRAINT [DF_hr_leave_weekly_rest_grant_created_at] DEFAULT (SYSUTCDATETIME()),
            [created_by_user_id] BIGINT NULL,
            [is_active] BIT NOT NULL CONSTRAINT [DF_hr_leave_weekly_rest_grant_is_active] DEFAULT (1),
            [row_version] ROWVERSION NOT NULL,
            CONSTRAINT [UQ_hr_leave_weekly_rest_grant] UNIQUE ([employee_id], [original_holiday_date])
        );
    """)
    op.execute("""
        IF OBJECT_ID(N'hr.leave_attendance_class', N'U') IS NULL
        CREATE TABLE [hr].[leave_attendance_class] (
            [attendance_status] NVARCHAR(30) NOT NULL CONSTRAINT [PK_hr_leave_attendance_class] PRIMARY KEY,
            [counts_for_eligibility] BIT NOT NULL CONSTRAINT [DF_hr_leave_attendance_class_eligibility] DEFAULT (0),
            [counts_as_days_worked] BIT NOT NULL CONSTRAINT [DF_hr_leave_attendance_class_worked] DEFAULT (0),
            [is_deemed_work] BIT NOT NULL CONSTRAINT [DF_hr_leave_attendance_class_deemed] DEFAULT (0),
            [day_weight] DECIMAL(3, 1) NULL,
            [created_at] DATETIME2(0) NOT NULL
                CONSTRAINT [DF_hr_leave_attendance_class_created_at] DEFAULT (SYSUTCDATETIME()),
            [created_by_user_id] BIGINT NULL,
            [updated_at] DATETIME2(0) NULL,
            [updated_by_user_id] BIGINT NULL,
            [is_active] BIT NOT NULL CONSTRAINT [DF_hr_leave_attendance_class_is_active] DEFAULT (1),
            [row_version] ROWVERSION NOT NULL,
            CONSTRAINT [CK_hr_leave_attendance_class_status] CHECK (
                [attendance_status] IN (
                    N'Present', N'Absent', N'Half day', N'Leave', N'Holiday', N'Week off', N'On duty'
                )
            ),
            CONSTRAINT [CK_hr_leave_attendance_class_split] CHECK (
                [counts_as_days_worked] = 0 OR [is_deemed_work] = 0
            )
        );
    """)


def downgrade() -> None:
    op.execute("IF OBJECT_ID(N'hr.leave_attendance_class', N'U') IS NOT NULL DROP TABLE [hr].[leave_attendance_class];")
    op.execute("IF OBJECT_ID(N'hr.leave_weekly_rest_grant', N'U') IS NOT NULL DROP TABLE [hr].[leave_weekly_rest_grant];")
    op.execute(
        "IF OBJECT_ID(N'hr.leave_balance_transaction', N'U') IS NOT NULL DROP TABLE [hr].[leave_balance_transaction];"
    )
    op.execute("IF OBJECT_ID(N'hr.leave_entitlement_run', N'U') IS NOT NULL DROP TABLE [hr].[leave_entitlement_run];")
    op.execute(
        "IF OBJECT_ID(N'hr.leave_policy_assignment', N'U') IS NOT NULL DROP TABLE [hr].[leave_policy_assignment];"
    )
