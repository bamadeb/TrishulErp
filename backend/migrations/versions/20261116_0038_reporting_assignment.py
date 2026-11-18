"""History of reporting-manager assignments.

The current manager remains core.employee.reporting_manager_id. This table stores
the previous manager, the new manager, the effective date and the remarks.
Alembic upgrade is not used for this database. scripts/apply_reporting_assignment.py
applies this SQL on TrishulDev.

Revision ID: 0038_reporting_assignment
Revises: 0037_leave_backdate
Created: 2026-11-16
"""

from alembic import op

revision = "0038_reporting_assignment"
down_revision = "0037_leave_backdate"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        IF OBJECT_ID(N'hr.reporting_assignment', N'U') IS NULL
        BEGIN
            CREATE TABLE hr.reporting_assignment (
                id BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT PK_hr_reporting_assignment PRIMARY KEY,
                employee_id BIGINT NOT NULL,
                previous_manager_id BIGINT NULL,
                manager_id BIGINT NOT NULL,
                effective_from DATE NOT NULL,
                remarks NVARCHAR(300) NULL,
                created_at DATETIME2(0) NOT NULL
                    CONSTRAINT DF_hr_reporting_assignment_created_at DEFAULT (SYSUTCDATETIME()),
                created_by_user_id BIGINT NULL,
                is_active BIT NOT NULL CONSTRAINT DF_hr_reporting_assignment_is_active DEFAULT (1),
                CONSTRAINT FK_hr_reporting_assignment_employee
                    FOREIGN KEY (employee_id) REFERENCES core.employee(id),
                CONSTRAINT FK_hr_reporting_assignment_previous_manager
                    FOREIGN KEY (previous_manager_id) REFERENCES core.employee(id),
                CONSTRAINT FK_hr_reporting_assignment_manager
                    FOREIGN KEY (manager_id) REFERENCES core.employee(id)
            );
            CREATE INDEX IX_hr_reporting_assignment_employee ON hr.reporting_assignment(employee_id);
        END
    """)


def downgrade() -> None:
    op.execute("""
        IF OBJECT_ID(N'hr.reporting_assignment', N'U') IS NOT NULL
            DROP TABLE hr.reporting_assignment;
    """)
