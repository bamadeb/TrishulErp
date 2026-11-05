"""Organization masters on the existing department, designation, branch, company and employee tables."""

from datetime import UTC, datetime
from typing import Any

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from trishul_api.auth import CurrentUser
from trishul_api.common.concurrency import check_row_version
from trishul_api.common.errors import AlreadyExists, ApiError, NotFound
from trishul_api.common.schemas import Page
from trishul_api.db.models import Branch, Company, Department, Designation, District, Employee, Pincode, State
from trishul_api.db.models.generated.acc import GstinRegistration
from trishul_api.modules.hr.organization.repository import OrganizationRepository
from trishul_api.modules.hr.organization.schemas import (
    BranchCreate,
    BranchDetail,
    BranchListItem,
    BranchUpdate,
    CompanyCreate,
    CompanyDetail,
    CompanyListItem,
    CompanyUpdate,
    DepartmentCreate,
    DepartmentDetail,
    DepartmentListItem,
    DepartmentUpdate,
    DesignationCreate,
    DesignationDetail,
    DesignationListItem,
    DesignationUpdate,
    GradeCreate,
    GradeDetail,
    GradeListItem,
    GradeUpdate,
    HierarchyCreate,
    HierarchyDetail,
    HierarchyListItem,
    HierarchyUpdate,
    OrganizationQuery,
)


class OrganizationService:
    def __init__(self, db: Session) -> None:
        self._db = db
        self._repo = OrganizationRepository(db)

    def list_departments(self, query: OrganizationQuery) -> Page[DepartmentListItem]:
        return self._repo.search_departments(query)

    def get_department(self, department_id: int) -> DepartmentDetail:
        return DepartmentDetail.model_validate(self._row(self._repo.department(department_id), "Department"))

    def create_department(self, actor: CurrentUser, data: DepartmentCreate) -> DepartmentDetail:
        self._unique(self._repo.department_code_owner(data.code), None, "Department", data.code)
        self._refs(
            {
                "parentDepartmentId": (Department, data.parent_department_id),
                "headEmployeeId": (Employee, data.head_employee_id),
            }
        )
        row = Department(
            code=data.code,
            name=data.name,
            parent_department_id=data.parent_department_id,
            head_employee_id=data.head_employee_id,
            created_by_user_id=actor.id,
        )
        return self.get_department(self._save(row, "Department"))

    def update_department(
        self, actor: CurrentUser, department_id: int, expected: bytes, data: DepartmentUpdate
    ) -> DepartmentDetail:
        row = self._model(Department, department_id, "Department")
        check_row_version(row.row_version, expected)
        if data.parent_department_id == department_id:
            raise ApiError(
                "A department cannot be its own parent.",
                errors={"parentDepartmentId": ["Choose another department."]},
            )
        if "code" in data.model_fields_set and data.code:
            self._unique(self._repo.department_code_owner(data.code), department_id, "Department", data.code)
        self._apply(row, data, ("code", "name", "parent_department_id", "head_employee_id", "is_active"))
        self._refs(
            {
                "parentDepartmentId": (Department, row.parent_department_id),
                "headEmployeeId": (Employee, row.head_employee_id),
            }
        )
        self._touch(row, actor)
        self._save(row, "Department")
        return self.get_department(department_id)

    def list_designations(self, query: OrganizationQuery) -> Page[DesignationListItem]:
        return self._repo.search_designations(query)

    def get_designation(self, designation_id: int) -> DesignationDetail:
        return DesignationDetail.model_validate(self._row(self._repo.designation(designation_id), "Designation"))

    def create_designation(self, actor: CurrentUser, data: DesignationCreate) -> DesignationDetail:
        self._unique(self._repo.designation_code_owner(data.code), None, "Designation", data.code)
        self._refs({"departmentId": (Department, data.department_id)})
        row = Designation(
            code=data.code,
            name=data.name,
            grade=data.grade,
            department_id=data.department_id,
            created_by_user_id=actor.id,
        )
        return self.get_designation(self._save(row, "Designation"))

    def update_designation(
        self, actor: CurrentUser, designation_id: int, expected: bytes, data: DesignationUpdate
    ) -> DesignationDetail:
        row = self._model(Designation, designation_id, "Designation")
        check_row_version(row.row_version, expected)
        if "code" in data.model_fields_set and data.code:
            self._unique(self._repo.designation_code_owner(data.code), designation_id, "Designation", data.code)
        self._apply(row, data, ("code", "name", "grade", "department_id", "is_active"))
        self._refs({"departmentId": (Department, row.department_id)})
        self._touch(row, actor)
        self._save(row, "Designation")
        return self.get_designation(designation_id)

    def list_grades(self, query: OrganizationQuery) -> Page[GradeListItem]:
        return self._repo.search_grades(query)

    def get_grade(self, grade: str) -> GradeDetail:
        found = self._repo.grade(grade)
        if found is None:
            raise NotFound("Grade not found.")
        return found

    def create_grade(self, actor: CurrentUser, data: GradeCreate) -> GradeDetail:
        row = self._model(Designation, data.designation_id, "Designation")
        row.grade = data.grade
        self._touch(row, actor)
        self._save(row, "Designation")
        return self.get_grade(data.grade)

    def rename_grade(self, actor: CurrentUser, grade: str, data: GradeUpdate) -> GradeDetail:
        changed = self._repo.rename_grade(grade, data.grade, updated_at=_now(), updated_by_user_id=actor.id)
        if changed == 0:
            raise NotFound("Grade not found.")
        self._db.commit()
        return self.get_grade(data.grade)

    def list_branches(self, query: OrganizationQuery) -> Page[BranchListItem]:
        return self._repo.search_branches(query)

    def get_branch(self, branch_id: int) -> BranchDetail:
        return BranchDetail.model_validate(self._row(self._repo.branch(branch_id), "Branch"))

    def create_branch(self, actor: CurrentUser, data: BranchCreate) -> BranchDetail:
        self._unique(self._repo.branch_code_owner(data.code), None, "Branch", data.code)
        self._branch_refs(data)
        row = Branch(
            code=data.code,
            name=data.name,
            branch_type=data.branch_type,
            company_id=data.company_id,
            state_id=data.state_id,
            parent_warehouse_id=data.parent_warehouse_id,
            address=data.address,
            district_id=data.district_id,
            pincode_id=data.pincode_id,
            gstin_registration_id=data.gstin_registration_id,
            phone=data.phone,
            email=str(data.email) if data.email else None,
            latitude=data.latitude,
            longitude=data.longitude,
            created_by_user_id=actor.id,
        )
        return self.get_branch(self._save(row, "Branch"))

    def update_branch(self, actor: CurrentUser, branch_id: int, expected: bytes, data: BranchUpdate) -> BranchDetail:
        row = self._model(Branch, branch_id, "Branch")
        check_row_version(row.row_version, expected)
        if "code" in data.model_fields_set and data.code:
            self._unique(self._repo.branch_code_owner(data.code), branch_id, "Branch", data.code)
        if "email" in data.model_fields_set:
            row.email = str(data.email) if data.email else None
        self._apply(
            row,
            data,
            (
                "code",
                "name",
                "branch_type",
                "company_id",
                "state_id",
                "parent_warehouse_id",
                "address",
                "district_id",
                "pincode_id",
                "gstin_registration_id",
                "phone",
                "latitude",
                "longitude",
                "is_active",
            ),
        )
        self._branch_refs(row)
        self._touch(row, actor)
        self._save(row, "Branch")
        return self.get_branch(branch_id)

    def list_companies(self, query: OrganizationQuery) -> Page[CompanyListItem]:
        return self._repo.search_companies(query)

    def get_company(self, company_id: int) -> CompanyDetail:
        return CompanyDetail.model_validate(self._row(self._repo.company(company_id), "Company"))

    def create_company(self, actor: CurrentUser, data: CompanyCreate) -> CompanyDetail:
        self._unique(self._repo.company_code_owner(data.code), None, "Company", data.code)
        self._refs({"stateId": (State, data.state_id)}, active=False)
        row = Company(
            code=data.code, legal_name=data.legal_name, trade_name=data.trade_name, pan=data.pan, cin=data.cin,
            address=data.address, state_id=data.state_id, logo_url=data.logo_url,
            fiscal_year_start_month=data.fiscal_year_start_month, created_by_user_id=actor.id,
        )
        return self.get_company(self._save(row, "Company"))

    def update_company(
        self, actor: CurrentUser, company_id: int, expected: bytes, data: CompanyUpdate
    ) -> CompanyDetail:
        row = self._model(Company, company_id, "Company")
        check_row_version(row.row_version, expected)
        if "code" in data.model_fields_set and data.code:
            self._unique(self._repo.company_code_owner(data.code), company_id, "Company", data.code)
        self._apply(
            row,
            data,
            (
                "code",
                "legal_name",
                "trade_name",
                "pan",
                "cin",
                "address",
                "state_id",
                "logo_url",
                "fiscal_year_start_month",
                "is_active",
            ),
        )
        self._refs({"stateId": (State, row.state_id)}, active=False)
        self._touch(row, actor)
        self._save(row, "Company")
        return self.get_company(company_id)

    def list_hierarchy(self, query: OrganizationQuery) -> Page[HierarchyListItem]:
        return self._repo.search_hierarchy(query)

    def get_hierarchy_member(self, employee_id: int) -> HierarchyDetail:
        return HierarchyDetail.model_validate(self._row(self._repo.hierarchy_member(employee_id), "Employee"))

    def create_hierarchy_link(self, actor: CurrentUser, data: HierarchyCreate) -> HierarchyDetail:
        row = self._model(Employee, data.employee_id, "Employee")
        self._check_manager(row.id, data.reporting_manager_id)
        row.reporting_manager_id = data.reporting_manager_id
        self._touch(row, actor)
        self._save(row, "Employee")
        return self.get_hierarchy_member(row.id)

    def update_hierarchy(
        self, actor: CurrentUser, employee_id: int, expected: bytes, data: HierarchyUpdate
    ) -> HierarchyDetail:
        row = self._model(Employee, employee_id, "Employee")
        check_row_version(row.row_version, expected)
        if "reporting_manager_id" in data.model_fields_set:
            self._check_manager(employee_id, data.reporting_manager_id)
            row.reporting_manager_id = data.reporting_manager_id
        self._touch(row, actor)
        self._save(row, "Employee")
        return self.get_hierarchy_member(employee_id)

    def _row(self, row: dict[str, Any] | None, label: str) -> dict[str, Any]:
        if row is None:
            raise NotFound(f"{label} not found.")
        return row

    def _model(self, model: type[Any], row_id: int, label: str) -> Any:
        row = self._repo.get(model, row_id)
        if row is None:
            raise NotFound(f"{label} not found.")
        return row

    def _unique(self, owner: int | None, current_id: int | None, label: str, code: str) -> None:
        if owner is not None and owner != current_id:
            raise AlreadyExists(f"{label} code '{code}' is already in use.")

    def _refs(self, fields: dict[str, tuple[type[Any], int | None]], *, active: bool = True) -> None:
        errors = {
            name: [f"Unknown reference {row_id}."]
            for name, (model, row_id) in fields.items()
            if row_id is not None and self._repo.missing(model, {row_id}, active=active)
        }
        if errors:
            raise ApiError("Some of the selected references don't exist.", errors=errors)

    def _branch_refs(self, data: Any) -> None:
        self._refs(
            {
                "companyId": (Company, data.company_id),
                "stateId": (State, data.state_id),
                "parentWarehouseId": (Branch, data.parent_warehouse_id),
                "districtId": (District, data.district_id),
                "pincodeId": (Pincode, data.pincode_id),
                "gstinRegistrationId": (GstinRegistration, data.gstin_registration_id),
            },
            active=False,
        )

    def _check_manager(self, employee_id: int, manager_id: int | None) -> None:
        if manager_id is None:
            return
        if manager_id == employee_id:
            raise ApiError(
                "An employee cannot report to themselves.",
                errors={"reportingManagerId": ["Choose someone else."]},
            )
        if self._repo.missing(Employee, {manager_id}, active=False):
            raise ApiError(
                "Some of the selected references don't exist.",
                errors={"reportingManagerId": [f"Unknown employee {manager_id}."]},
            )
        seen: set[int] = set()
        current: int | None = manager_id
        while current is not None and current not in seen:
            if current == employee_id:
                raise ApiError(
                    "That manager already reports through this employee.",
                    errors={"reportingManagerId": ["Choose a manager outside this chain."]},
                )
            seen.add(current)
            current = self._repo.manager_of(current)

    def _apply(self, row: Any, data: Any, fields: tuple[str, ...]) -> None:
        for field in fields:
            if field in data.model_fields_set:
                setattr(row, field, getattr(data, field))

    def _touch(self, row: Any, actor: CurrentUser) -> None:
        row.updated_at = _now()
        row.updated_by_user_id = actor.id

    def _save(self, row: Any, label: str) -> int:
        self._repo.add(row)
        try:
            self._repo.flush()
            row_id = int(row.id)
            self._db.commit()
        except IntegrityError as error:
            self._db.rollback()
            raise AlreadyExists(f"{label} could not be saved. The code may already be in use.") from error
        return row_id


def _now() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)
