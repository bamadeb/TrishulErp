"""Employee master management (core.employee): list, view, add and update.

core.employee is a plain table (not Audited), so created_by_user_id / updated_by_user_id are set here.
Employee code and mobile are unique in the database; this checks them up front for clear errors and still
catches a concurrent duplicate on commit.
"""

from datetime import UTC, datetime

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from trishul_api.auth import CurrentUser
from trishul_api.common.concurrency import check_row_version
from trishul_api.common.errors import AlreadyExists, ApiError, NotFound
from trishul_api.db.models import Branch, Company, Department, Designation, Employee
from trishul_api.modules.core.employees.repository import EmployeeRepository
from trishul_api.modules.core.employees.schemas import EmployeeCreate, EmployeeDetail, EmployeeUpdate

_DUPLICATE = "Another employee already has this code or mobile number."
# Fields copied straight from the request to the row (code and mobile are handled separately for uniqueness).
_PLAIN_FIELDS = (
    "first_name",
    "last_name",
    "company_id",
    "branch_id",
    "department_id",
    "designation_id",
    "reporting_manager_id",
    "employee_type",
    "status",
    "date_of_joining",
    "date_of_exit",
    "mobile_platform",
)


class EmployeeService:
    def __init__(self, db: Session) -> None:
        self._db = db
        self._repo = EmployeeRepository(db)

    def get(self, employee_id: int) -> EmployeeDetail:
        self._require(employee_id)
        return self._detail(employee_id)

    def create(self, actor: CurrentUser, data: EmployeeCreate) -> EmployeeDetail:
        code = data.employee_code.strip()
        self._check_unique_code(code, None)
        if data.mobile:
            self._check_unique_mobile(data.mobile, None)
        self._check_references(data, employee_id=None)

        employee = Employee(
            employee_code=code,
            mobile=data.mobile,
            email=str(data.email) if data.email else None,
            created_by_user_id=actor.id,
            **{field: getattr(data, field) for field in _PLAIN_FIELDS},
        )
        self._repo.add(employee)
        new_id = self._save(employee)
        return self._detail(new_id)

    def update(
        self, actor: CurrentUser, employee_id: int, expected_row_version: bytes, data: EmployeeUpdate
    ) -> EmployeeDetail:
        employee = self._require(employee_id)
        check_row_version(employee.row_version, expected_row_version)
        changed = data.model_fields_set

        if "employee_code" in changed and data.employee_code:
            code = data.employee_code.strip()
            self._check_unique_code(code, employee.id)
            employee.employee_code = code
        if "mobile" in changed:
            if data.mobile:
                self._check_unique_mobile(data.mobile, employee.id)
            employee.mobile = data.mobile
        if "email" in changed:
            employee.email = str(data.email) if data.email else None
        self._check_references(data, employee_id=employee.id)
        for field in _PLAIN_FIELDS:
            if field in changed:
                setattr(employee, field, getattr(data, field))

        self._touch(employee, actor)
        self._save(employee)
        return self._detail(employee_id)

    def deactivate(self, actor: CurrentUser, employee_id: int) -> EmployeeDetail:
        employee = self._require(employee_id)
        if employee.is_active:
            if self._repo.active_login_exists(employee.id):
                raise ApiError("This employee has an active sign-in account. Deactivate the user first.")
            employee.is_active = False
            self._touch(employee, actor)
            self._db.commit()
        return self._detail(employee_id)

    def activate(self, actor: CurrentUser, employee_id: int) -> EmployeeDetail:
        employee = self._require(employee_id)
        if not employee.is_active:
            employee.is_active = True
            self._touch(employee, actor)
            self._db.commit()
        return self._detail(employee_id)

    # ------------------------------------------------------------------ helpers

    def _require(self, employee_id: int) -> Employee:
        employee = self._repo.get(employee_id)
        if employee is None:
            raise NotFound("Employee not found.")
        return employee

    def _detail(self, employee_id: int) -> EmployeeDetail:
        return EmployeeDetail.model_validate(self._repo.detail_row(employee_id))

    def _save(self, employee: Employee) -> int:
        try:
            self._repo.flush()
            employee_id = employee.id
            self._db.commit()
        except IntegrityError as error:
            self._db.rollback()
            raise AlreadyExists(_DUPLICATE) from error
        return employee_id

    def _check_unique_code(self, code: str, employee_id: int | None) -> None:
        owner = self._repo.code_owner(code)
        if owner is not None and owner != employee_id:
            raise AlreadyExists(f"Employee code '{code}' is already in use.")

    def _check_unique_mobile(self, mobile: str, employee_id: int | None) -> None:
        owner = self._repo.mobile_owner(mobile)
        if owner is not None and owner != employee_id:
            raise AlreadyExists(f"Mobile number '{mobile}' is already used by another employee.")

    def _check_references(self, data: EmployeeCreate | EmployeeUpdate, *, employee_id: int | None) -> None:
        changed = data.model_fields_set
        errors: dict[str, list[str]] = {}
        checks = (
            ("company_id", "companyId", Company),
            ("branch_id", "branchId", Branch),
            ("department_id", "departmentId", Department),
            ("designation_id", "designationId", Designation),
        )
        for field, key, model in checks:
            value = getattr(data, field)
            if field in changed and value is not None and self._repo.missing(model, [value]):
                errors[key] = [f"Unknown or inactive {field[:-3].replace('_', ' ')} {value}"]

        manager_id = data.reporting_manager_id
        if "reporting_manager_id" in changed and manager_id is not None:
            if manager_id == employee_id:
                errors["reportingManagerId"] = ["An employee cannot report to themselves."]
            elif self._repo.missing(Employee, [manager_id]):
                errors["reportingManagerId"] = [f"Unknown or inactive employee {manager_id}"]
        if errors:
            raise ApiError("Some of the selected references don't exist.", errors=errors)

    @staticmethod
    def _touch(employee: Employee, actor: CurrentUser) -> None:
        employee.updated_at = datetime.now(UTC).replace(tzinfo=None)
        employee.updated_by_user_id = actor.id
