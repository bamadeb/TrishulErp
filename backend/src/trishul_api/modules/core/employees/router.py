from typing import Annotated

from fastapi import APIRouter, Depends, Path, Query, Response

from trishul_api.auth import CurrentUserDep, DbSession, require_permission
from trishul_api.common.concurrency import if_match_row_version
from trishul_api.common.errors import CONCURRENCY_RESPONSES, NOT_FOUND_RESPONSE
from trishul_api.common.schemas import Page
from trishul_api.modules.core.employees.repository import EmployeeRepository
from trishul_api.modules.core.employees.schemas import (
    CompanyOption,
    DepartmentOption,
    DesignationOption,
    EmployeeCreate,
    EmployeeDetail,
    EmployeeListItem,
    EmployeeQuery,
    EmployeeUpdate,
)
from trishul_api.modules.core.employees.service import EmployeeService

router = APIRouter(prefix="/core", tags=["employees"])

CAN_VIEW = Depends(require_permission("core.employee.view", "core.employee.manage"))
CAN_MANAGE = Depends(require_permission("core.employee.manage"))

EmployeeId = Annotated[int, Path(alias="employeeId")]


def get_employee_service(db: DbSession) -> EmployeeService:
    return EmployeeService(db)


def get_employee_repository(db: DbSession) -> EmployeeRepository:
    return EmployeeRepository(db)


Employees = Annotated[EmployeeService, Depends(get_employee_service)]
EmployeeRepo = Annotated[EmployeeRepository, Depends(get_employee_repository)]


@router.get("/employees", summary="Employees, filtered and paged", dependencies=[CAN_VIEW])
def list_employees(query: Annotated[EmployeeQuery, Query()], repo: EmployeeRepo) -> Page[EmployeeListItem]:
    return repo.search(query)


@router.get("/employees/{employeeId}", summary="One employee", dependencies=[CAN_VIEW], responses=NOT_FOUND_RESPONSE)
def get_employee(employee_id: EmployeeId, employees: Employees) -> EmployeeDetail:
    return employees.get(employee_id)


@router.post("/employees", summary="Add an employee", status_code=201, dependencies=[CAN_MANAGE])
def create_employee(
    data: EmployeeCreate, actor: CurrentUserDep, employees: Employees, response: Response
) -> EmployeeDetail:
    created = employees.create(actor, data)
    response.headers["Location"] = f"employees/{created.id}"
    return created


@router.patch(
    "/employees/{employeeId}",
    summary="Change an employee's details",
    dependencies=[CAN_MANAGE],
    responses={**NOT_FOUND_RESPONSE, **CONCURRENCY_RESPONSES},
)
def update_employee(
    employee_id: EmployeeId,
    data: EmployeeUpdate,
    actor: CurrentUserDep,
    employees: Employees,
    row_version: Annotated[bytes, Depends(if_match_row_version)],
) -> EmployeeDetail:
    return employees.update(actor, employee_id, row_version, data)


@router.post(
    "/employees/{employeeId}/deactivate",
    summary="Mark an employee inactive",
    dependencies=[CAN_MANAGE],
    responses=NOT_FOUND_RESPONSE,
)
def deactivate_employee(employee_id: EmployeeId, actor: CurrentUserDep, employees: Employees) -> EmployeeDetail:
    return employees.deactivate(actor, employee_id)


@router.post(
    "/employees/{employeeId}/activate",
    summary="Mark an employee active again",
    dependencies=[CAN_MANAGE],
    responses=NOT_FOUND_RESPONSE,
)
def activate_employee(employee_id: EmployeeId, actor: CurrentUserDep, employees: Employees) -> EmployeeDetail:
    return employees.activate(actor, employee_id)


@router.get("/companies", summary="Companies, for the employee form", dependencies=[CAN_VIEW])
def list_companies(repo: EmployeeRepo) -> list[CompanyOption]:
    return repo.companies()


@router.get("/departments", summary="Departments, for the employee form", dependencies=[CAN_VIEW])
def list_departments(repo: EmployeeRepo) -> list[DepartmentOption]:
    return repo.departments()


@router.get("/designations", summary="Designations, for the employee form", dependencies=[CAN_VIEW])
def list_designations(repo: EmployeeRepo) -> list[DesignationOption]:
    return repo.designations()
