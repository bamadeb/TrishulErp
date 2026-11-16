"""Let one salary template name several designations and grades.

The grade still lives on hr.designation. These links do not change a saved
employee salary structure.

Revision ID: 0031_template_designation_grades
Revises: 0029_salary_templates
Created: 2026-11-10
"""

from alembic import op

revision = "0031_template_designation_grades"
down_revision = "0029_salary_templates"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        IF OBJECT_ID(N'hr.salary_template_designation', N'U') IS NULL
        CREATE TABLE [hr].[salary_template_designation] (
            [salary_template_id] BIGINT NOT NULL
                CONSTRAINT [FK_hr_salary_template_designation_template] REFERENCES [hr].[salary_template]([id]),
            [designation_id] BIGINT NOT NULL
                CONSTRAINT [FK_hr_salary_template_designation_designation] REFERENCES [hr].[designation]([id]),
            CONSTRAINT [PK_hr_salary_template_designation] PRIMARY KEY ([salary_template_id], [designation_id])
        );
    """)
    op.execute("""
        IF OBJECT_ID(N'hr.salary_template_grade', N'U') IS NULL
        CREATE TABLE [hr].[salary_template_grade] (
            [salary_template_id] BIGINT NOT NULL
                CONSTRAINT [FK_hr_salary_template_grade_template] REFERENCES [hr].[salary_template]([id]),
            [grade] NVARCHAR(10) NOT NULL,
            CONSTRAINT [PK_hr_salary_template_grade] PRIMARY KEY ([salary_template_id], [grade]),
            CONSTRAINT [CK_hr_salary_template_grade] CHECK (
                [grade] IN (N'E1', N'E2', N'E3', N'E4', N'E5', N'G1', N'G2', N'G3', N'G4', N'G5', N'G6')
            )
        );
    """)


def downgrade() -> None:
    op.execute("IF OBJECT_ID(N'hr.salary_template_grade', N'U') IS NOT NULL DROP TABLE [hr].[salary_template_grade];")
    op.execute(
        "IF OBJECT_ID(N'hr.salary_template_designation', N'U') IS NOT NULL "
        "DROP TABLE [hr].[salary_template_designation];"
    )
