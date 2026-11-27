"""Credit-wise Comp Off ledger. Each credit expires 90 days after it is credited.

Does not change existing leave balances or attendance rows.

Revision ID: 0049_comp_off_ledger
Revises: 0048_office_hours_policy
Created: 2026-11-27
"""

from alembic import op

revision = "0049_comp_off_ledger"
down_revision = "0048_office_hours_policy"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        IF OBJECT_ID(N'hr.comp_off_authorization', N'U') IS NULL
        CREATE TABLE [hr].[comp_off_authorization] (
            [id] BIGINT IDENTITY(1, 1) NOT NULL CONSTRAINT [PK_hr_comp_off_authorization] PRIMARY KEY,
            [employee_id] BIGINT NOT NULL
                CONSTRAINT [FK_hr_comp_off_authorization_employee] REFERENCES [core].[employee]([id]),
            [work_date] DATE NOT NULL,
            [day_kind] NVARCHAR(20) NOT NULL,
            [status] NVARCHAR(20) NOT NULL,
            [remarks] NVARCHAR(300) NULL,
            [regularization_id] BIGINT NULL,
            [authorized_by_user_id] BIGINT NULL,
            [authorized_at] DATETIME2(0) NOT NULL,
            [certified_by_user_id] BIGINT NULL,
            [certified_at] DATETIME2(0) NULL,
            [created_at] DATETIME2(0) NOT NULL
                CONSTRAINT [DF_hr_comp_off_authorization_created_at] DEFAULT (SYSUTCDATETIME()),
            [created_by_user_id] BIGINT NULL,
            [updated_at] DATETIME2(0) NULL,
            [updated_by_user_id] BIGINT NULL,
            [is_active] BIT NOT NULL CONSTRAINT [DF_hr_comp_off_authorization_is_active] DEFAULT (1),
            [row_version] ROWVERSION NOT NULL,
            CONSTRAINT [CK_hr_comp_off_authorization_kind] CHECK (
                [day_kind] IN (N'WEEKLY_OFF', N'COMPANY_HOLIDAY', N'NON_WORKING')
            ),
            CONSTRAINT [CK_hr_comp_off_authorization_status] CHECK (
                [status] IN (N'Authorized', N'Certified', N'Rejected', N'Cancelled')
            )
        );
        IF NOT EXISTS (
            SELECT 1 FROM sys.indexes
            WHERE [name] = N'UQ_hr_comp_off_authorization_open'
              AND [object_id] = OBJECT_ID(N'hr.comp_off_authorization')
        )
        CREATE UNIQUE INDEX [UQ_hr_comp_off_authorization_open]
            ON [hr].[comp_off_authorization] ([employee_id], [work_date])
            WHERE [status] IN (N'Authorized', N'Certified') AND [is_active] = 1;
    """)
    op.execute("""
        IF OBJECT_ID(N'hr.comp_off_credit', N'U') IS NULL
        CREATE TABLE [hr].[comp_off_credit] (
            [id] BIGINT IDENTITY(1, 1) NOT NULL CONSTRAINT [PK_hr_comp_off_credit] PRIMARY KEY,
            [authorization_id] BIGINT NULL
                CONSTRAINT [FK_hr_comp_off_credit_authorization] REFERENCES [hr].[comp_off_authorization]([id]),
            [employee_id] BIGINT NOT NULL
                CONSTRAINT [FK_hr_comp_off_credit_employee] REFERENCES [core].[employee]([id]),
            [leave_type_id] BIGINT NOT NULL
                CONSTRAINT [FK_hr_comp_off_credit_type] REFERENCES [hr].[leave_type]([id]),
            [work_date] DATE NOT NULL,
            [day_kind] NVARCHAR(20) NOT NULL,
            [credited_on] DATE NOT NULL,
            [expires_on] DATE NOT NULL,
            [days] DECIMAL(4, 1) NOT NULL,
            [consumed_days] DECIMAL(4, 1) NOT NULL
                CONSTRAINT [DF_hr_comp_off_credit_consumed] DEFAULT (0),
            [expired_days] DECIMAL(4, 1) NOT NULL
                CONSTRAINT [DF_hr_comp_off_credit_expired] DEFAULT (0),
            [status] NVARCHAR(20) NOT NULL,
            [created_at] DATETIME2(0) NOT NULL
                CONSTRAINT [DF_hr_comp_off_credit_created_at] DEFAULT (SYSUTCDATETIME()),
            [created_by_user_id] BIGINT NULL,
            [updated_at] DATETIME2(0) NULL,
            [updated_by_user_id] BIGINT NULL,
            [is_active] BIT NOT NULL CONSTRAINT [DF_hr_comp_off_credit_is_active] DEFAULT (1),
            [row_version] ROWVERSION NOT NULL,
            CONSTRAINT [CK_hr_comp_off_credit_days] CHECK ([days] > 0)
        );
        IF NOT EXISTS (
            SELECT 1 FROM sys.indexes
            WHERE [name] = N'UQ_hr_comp_off_credit_authorization'
              AND [object_id] = OBJECT_ID(N'hr.comp_off_credit')
        )
        CREATE UNIQUE INDEX [UQ_hr_comp_off_credit_authorization]
            ON [hr].[comp_off_credit] ([authorization_id])
            WHERE [authorization_id] IS NOT NULL;
        IF NOT EXISTS (
            SELECT 1 FROM sys.indexes
            WHERE [name] = N'IX_hr_comp_off_credit_employee'
              AND [object_id] = OBJECT_ID(N'hr.comp_off_credit')
        )
        CREATE INDEX [IX_hr_comp_off_credit_employee]
            ON [hr].[comp_off_credit] ([employee_id], [expires_on], [status]);
    """)
    op.execute("""
        IF OBJECT_ID(N'hr.comp_off_ledger', N'U') IS NULL
        CREATE TABLE [hr].[comp_off_ledger] (
            [id] BIGINT IDENTITY(1, 1) NOT NULL CONSTRAINT [PK_hr_comp_off_ledger] PRIMARY KEY,
            [credit_id] BIGINT NOT NULL
                CONSTRAINT [FK_hr_comp_off_ledger_credit] REFERENCES [hr].[comp_off_credit]([id]),
            [employee_id] BIGINT NOT NULL
                CONSTRAINT [FK_hr_comp_off_ledger_employee] REFERENCES [core].[employee]([id]),
            [kind] NVARCHAR(20) NOT NULL,
            [days] DECIMAL(4, 1) NOT NULL,
            [leave_request_id] BIGINT NULL,
            [remarks] NVARCHAR(300) NULL,
            [created_at] DATETIME2(0) NOT NULL
                CONSTRAINT [DF_hr_comp_off_ledger_created_at] DEFAULT (SYSUTCDATETIME()),
            [created_by_user_id] BIGINT NULL,
            [is_active] BIT NOT NULL CONSTRAINT [DF_hr_comp_off_ledger_is_active] DEFAULT (1),
            [row_version] ROWVERSION NOT NULL,
            CONSTRAINT [CK_hr_comp_off_ledger_kind] CHECK (
                [kind] IN (N'Credit', N'Consumption', N'Expiry', N'Adjustment', N'Reversal')
            )
        );
        IF NOT EXISTS (
            SELECT 1 FROM sys.indexes
            WHERE [name] = N'IX_hr_comp_off_ledger_employee'
              AND [object_id] = OBJECT_ID(N'hr.comp_off_ledger')
        )
        CREATE INDEX [IX_hr_comp_off_ledger_employee]
            ON [hr].[comp_off_ledger] ([employee_id], [credit_id]);
    """)


def downgrade() -> None:
    op.execute("IF OBJECT_ID(N'hr.comp_off_ledger', N'U') IS NOT NULL DROP TABLE [hr].[comp_off_ledger];")
    op.execute("IF OBJECT_ID(N'hr.comp_off_credit', N'U') IS NOT NULL DROP TABLE [hr].[comp_off_credit];")
    op.execute("IF OBJECT_ID(N'hr.comp_off_authorization', N'U') IS NOT NULL DROP TABLE [hr].[comp_off_authorization];")
