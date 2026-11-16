"""Join the service-report permission and salary-component migrations. No schema change.

0026_service_report_permissions and 0026_salary_components both continue from 0025_trip_remarks.
0027_salary_component_types continues from the salary migration, so the two heads are
0026_service_report_permissions and 0027_salary_component_types. Neither earlier revision is changed.

Revision ID: 0028_merge_service_report_salary
Revises: 0026_service_report_permissions, 0027_salary_component_types
Created: 2026-11-10
"""

revision = "0028_merge_service_report_salary"
down_revision = ("0026_service_report_permissions", "0027_salary_component_types")
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
