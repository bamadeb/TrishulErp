"""Add reusable salary templates without changing existing structures or payroll.

A template packages existing salary components. Assigning it copies those values
onto hr.salary_structure. A later template edit does not rewrite that structure.

Revision ID: 0029_salary_templates
Revises: 0027_salary_component_types
Created: 2026-11-10
"""

from alembic import op

revision = "0029_salary_templates"
down_revision = "0027_salary_component_types"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        IF OBJECT_ID(N'hr.salary_template', N'U') IS NULL
        CREATE TABLE [hr].[salary_template] (
            [id] BIGINT IDENTITY(1, 1) NOT NULL CONSTRAINT [PK_hr_salary_template] PRIMARY KEY,
            [code] NVARCHAR(20) NOT NULL,
            [name] NVARCHAR(80) NOT NULL,
            [description] NVARCHAR(400) NULL,
            [template_type] NVARCHAR(20) NOT NULL,
            [employee_category] NVARCHAR(30) NULL,
            [department_id] BIGINT NULL CONSTRAINT [FK_hr_salary_template_department] REFERENCES [hr].[department]([id]),
            [designation_id] BIGINT NULL CONSTRAINT [FK_hr_salary_template_designation] REFERENCES [hr].[designation]([id]),
            [effective_from] DATE NOT NULL,
            [effective_to] DATE NULL,
            [created_at] DATETIME2(0) NOT NULL CONSTRAINT [DF_hr_salary_template_created_at] DEFAULT (SYSUTCDATETIME()),
            [created_by_user_id] BIGINT NULL,
            [updated_at] DATETIME2(0) NULL,
            [updated_by_user_id] BIGINT NULL,
            [is_active] BIT NOT NULL CONSTRAINT [DF_hr_salary_template_is_active] DEFAULT (1),
            [row_version] ROWVERSION NOT NULL,
            CONSTRAINT [UQ_hr_salary_template_code] UNIQUE ([code]),
            CONSTRAINT [CK_hr_salary_template_type] CHECK ([template_type] = N'Monthly'),
            CONSTRAINT [CK_hr_salary_template_category] CHECK (
                [employee_category] IS NULL OR [employee_category] IN (N'Permanent', N'Contract', N'Trainee', N'Consultant')
            ),
            CONSTRAINT [CK_hr_salary_template_dates] CHECK ([effective_to] IS NULL OR [effective_to] > [effective_from])
        );
    """)
    op.execute("""
        IF OBJECT_ID(N'hr.salary_template_line', N'U') IS NULL
        CREATE TABLE [hr].[salary_template_line] (
            [id] BIGINT IDENTITY(1, 1) NOT NULL CONSTRAINT [PK_hr_salary_template_line] PRIMARY KEY,
            [salary_template_id] BIGINT NOT NULL CONSTRAINT [FK_hr_salary_template_line_template] REFERENCES [hr].[salary_template]([id]),
            [salary_component_id] BIGINT NOT NULL CONSTRAINT [FK_hr_salary_template_line_component] REFERENCES [hr].[salary_component]([id]),
            [monthly_amount] NUMERIC(18, 2) NULL,
            [percentage] NUMERIC(5, 2) NULL,
            [formula] NVARCHAR(300) NULL,
            [display_order] INT NOT NULL CONSTRAINT [DF_hr_salary_template_line_display_order] DEFAULT (0),
            [created_at] DATETIME2(0) NOT NULL CONSTRAINT [DF_hr_salary_template_line_created_at] DEFAULT (SYSUTCDATETIME()),
            [created_by_user_id] BIGINT NULL,
            [updated_at] DATETIME2(0) NULL,
            [updated_by_user_id] BIGINT NULL,
            [is_active] BIT NOT NULL CONSTRAINT [DF_hr_salary_template_line_is_active] DEFAULT (1),
            [row_version] ROWVERSION NOT NULL,
            CONSTRAINT [UQ_hr_salary_template_line] UNIQUE ([salary_template_id], [salary_component_id])
        );
    """)
    op.execute("""
        IF OBJECT_ID(N'hr.salary_template_assignment', N'U') IS NULL
        CREATE TABLE [hr].[salary_template_assignment] (
            [id] BIGINT IDENTITY(1, 1) NOT NULL CONSTRAINT [PK_hr_salary_template_assignment] PRIMARY KEY,
            [salary_template_id] BIGINT NOT NULL CONSTRAINT [FK_hr_salary_template_assignment_template] REFERENCES [hr].[salary_template]([id]),
            [salary_structure_id] BIGINT NOT NULL CONSTRAINT [FK_hr_salary_template_assignment_structure] REFERENCES [hr].[salary_structure]([id]),
            [employee_id] BIGINT NOT NULL CONSTRAINT [FK_hr_salary_template_assignment_employee] REFERENCES [core].[employee]([id]),
            [created_at] DATETIME2(0) NOT NULL CONSTRAINT [DF_hr_salary_template_assignment_created_at] DEFAULT (SYSUTCDATETIME()),
            [created_by_user_id] BIGINT NULL,
            [updated_at] DATETIME2(0) NULL,
            [updated_by_user_id] BIGINT NULL,
            [is_active] BIT NOT NULL CONSTRAINT [DF_hr_salary_template_assignment_is_active] DEFAULT (1),
            [row_version] ROWVERSION NOT NULL,
            CONSTRAINT [UQ_hr_salary_template_assignment_structure] UNIQUE ([salary_structure_id])
        );
    """)


def downgrade() -> None:
    op.execute("IF OBJECT_ID(N'hr.salary_template_assignment', N'U') IS NOT NULL DROP TABLE [hr].[salary_template_assignment];")
    op.execute("IF OBJECT_ID(N'hr.salary_template_line', N'U') IS NOT NULL DROP TABLE [hr].[salary_template_line];")
    op.execute("IF OBJECT_ID(N'hr.salary_template', N'U') IS NOT NULL DROP TABLE [hr].[salary_template];")
