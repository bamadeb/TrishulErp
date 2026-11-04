"""Organization schemas stay on the existing tables and reject values those columns cannot store."""

from datetime import UTC, datetime
from decimal import Decimal

import pytest
from pydantic import ValidationError
from sqlalchemy.orm import configure_mappers

from trishul_api.db.models import Base, Branch, Company, Department, Designation, Employee
from trishul_api.modules.hr.organization.models import GRADE_COLUMN, HIERARCHY_COLUMN, SECTION_MODELS
from trishul_api.modules.hr.organization.schemas import (
    BranchCreate,
    CompanyCreate,
    DepartmentCreate,
    DepartmentDetail,
    DesignationCreate,
    GradeCreate,
    GradeDetail,
    HierarchyCreate,
    HierarchyDetail,
    HierarchyListItem,
)


def test_sections_reuse_generated_tables_and_add_none() -> None:
    configure_mappers()
    before = set(Base.metadata.tables)
    assert set(Base.metadata.tables) == before
    assert SECTION_MODELS["departments"] is Department
    assert SECTION_MODELS["designations"] is Designation
    assert SECTION_MODELS["grades"] is Designation
    assert SECTION_MODELS["locations"] is Branch
    assert SECTION_MODELS["companies"] is Company
    assert SECTION_MODELS["hierarchy"] is Employee
    assert SECTION_MODELS["departments"].__table__.fullname == "hr.department"  # type: ignore[attr-defined]
    assert SECTION_MODELS["locations"].__table__.fullname == "core.branch"  # type: ignore[attr-defined]
    assert "hr.grade" not in Base.metadata.tables
    assert "hr.reporting_level" not in Base.metadata.tables


def test_grade_and_hierarchy_are_columns_not_tables() -> None:
    assert GRADE_COLUMN is Designation.grade
    assert GRADE_COLUMN.expression.table.fullname == "hr.designation"
    assert GRADE_COLUMN.type.length == 10
    assert GRADE_COLUMN.nullable
    assert HIERARCHY_COLUMN is Employee.reporting_manager_id
    foreign_keys = list(HIERARCHY_COLUMN.expression.foreign_keys)
    assert len(foreign_keys) == 1
    assert foreign_keys[0].column.table.fullname == "core.employee"
    assert HIERARCHY_COLUMN.nullable
    assert not Branch.state_id.nullable
    assert not Branch.company_id.nullable
    assert Department.parent_department_id.nullable
    assert Department.head_employee_id.nullable
    assert Designation.department_id.nullable
    assert Company.state_id.nullable


def test_create_schemas_accept_a_valid_row_and_trim_text() -> None:
    department = DepartmentCreate.model_validate({"code": "  ADM ", "name": "Administration"})
    assert department.code == "ADM"
    assert department.parent_department_id is None
    assert department.head_employee_id is None

    designation = DesignationCreate(code="MGR", name="Manager", grade="L2", department_id=None)
    assert designation.grade == "L2"

    branch = BranchCreate(code="HO", name="Head office", branch_type="Head office", company_id=1, state_id=21)
    assert branch.parent_warehouse_id is None
    assert branch.latitude is None

    company = CompanyCreate(code="TREAD", legal_name="Trishul Tread Pvt Ltd")
    assert company.fiscal_year_start_month == 4
    assert company.state_id is None

    grade = GradeCreate(grade="L1", designation_id=3)
    assert grade.designation_id == 3

    link = HierarchyCreate(employee_id=14, reporting_manager_id=None)
    assert link.reporting_manager_id is None


def test_column_lengths_and_required_relationships_are_enforced() -> None:
    with pytest.raises(ValidationError):
        DepartmentCreate(code="X" * 21, name="Administration")
    with pytest.raises(ValidationError):
        DesignationCreate(code="MGR", name="Manager", grade="X" * 11)
    with pytest.raises(ValidationError):
        CompanyCreate(code="X" * 11, legal_name="Trishul")
    with pytest.raises(ValidationError):
        CompanyCreate(code="TT", legal_name="Trishul", fiscal_year_start_month=13)
    with pytest.raises(ValidationError):
        BranchCreate(code="HO", name="Head office", branch_type="Depot", company_id=1, state_id=21)
    with pytest.raises(ValidationError):
        BranchCreate.model_validate({"code": "HO", "name": "Head office", "branchType": "Branch", "companyId": 1})
    with pytest.raises(ValidationError):
        BranchCreate(
            code="HO",
            name="Head office",
            branch_type="Branch",
            company_id=1,
            state_id=21,
            latitude=Decimal("1234.1234567"),
        )
    with pytest.raises(ValidationError):
        DepartmentCreate.model_validate({"code": "ADM", "name": "Administration", "isActive": True})
    with pytest.raises(ValidationError):
        HierarchyCreate(employee_id=14, reporting_manager_id=14)
    with pytest.raises(ValidationError):
        GradeCreate(grade="", designation_id=1)


def test_responses_expose_related_names_counts_and_row_version() -> None:
    created = datetime(2026, 11, 3, 8, 0, tzinfo=UTC)
    department = DepartmentDetail.model_validate(
        {
            "id": 1,
            "code": "ADM",
            "name": "Administration",
            "parent_department_id": None,
            "parent_department_name": None,
            "head_employee_id": 14,
            "head_name": "Ananya Rao",
            "employee_count": 26,
            "is_active": True,
            "created_at": created,
            "updated_at": None,
            "row_version": b"\x00\x00\x00\x00\x00\x00\x07\xd1",
        }
    )
    body = department.model_dump(by_alias=True)
    assert body["headName"] == "Ananya Rao"
    assert body["employeeCount"] == 26
    assert body["rowVersion"] == "AAAAAAAAB9E="

    grade = GradeDetail(grade="L2", designation_count=2, employee_count=18)
    assert grade.designations == []
    assert "row_version" not in GradeDetail.model_fields

    person = HierarchyListItem.model_validate(
        {
            "id": 14,
            "employee_code": "TT000001",
            "first_name": "Ananya",
            "last_name": "Rao",
            "department_id": 1,
            "department_name": "Administration",
            "designation_id": 2,
            "designation_name": "Manager",
            "grade": "L2",
            "company_id": 3,
            "company_name": "Trishul Tread Pvt Ltd",
            "branch_id": 2,
            "branch_name": "Head office",
            "reporting_manager_id": None,
            "reporting_manager_code": None,
            "reporting_manager_name": None,
            "direct_report_count": 4,
            "status": "Active",
            "is_active": True,
            "created_at": created,
        }
    )
    assert person.full_name == "Ananya Rao"
    assert "row_version" in HierarchyDetail.model_fields
