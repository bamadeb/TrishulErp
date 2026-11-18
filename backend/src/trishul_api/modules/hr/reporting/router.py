"""Reporting Structure assignment. The live manager is core.employee.reporting_manager_id."""

from typing import Annotated

from fastapi import APIRouter, Depends, Path

from trishul_api.auth import CurrentUserDep, DbSession, require_permission
from trishul_api.common.errors import NOT_FOUND_RESPONSE
from trishul_api.modules.hr.reporting.schemas import (
    ReportingAssignmentCreate,
    ReportingAssignmentSaved,
    ReportingEmployee,
    ReportingHistoryItem,
    ReportingRemovalCreate,
)
from trishul_api.modules.hr.reporting.service import ReportingService

router = APIRouter(prefix="/hr/reporting", tags=["reporting"])

CAN_VIEW = Depends(
    require_permission(
        "core.employee.view",
        "core.employee.manage",
        "hr.organization.view",
        "hr.organization.manage",
    )
)
CAN_MANAGE = Depends(require_permission("core.employee.manage", "hr.organization.manage"))


def get_reporting_service(db: DbSession) -> ReportingService:
    return ReportingService(db)


Reporting = Annotated[ReportingService, Depends(get_reporting_service)]
EmployeeId = Annotated[int, Path(alias="employeeId", gt=0)]


@router.get("/employees", summary="Employees for the reporting structure screen", dependencies=[CAN_VIEW])
def list_reporting_employees(reporting: Reporting) -> list[ReportingEmployee]:
    return reporting.list_employees()


@router.get(
    "/employees/{employeeId}/history",
    summary="Saved reporting-manager changes for one employee",
    dependencies=[CAN_VIEW],
    responses=NOT_FOUND_RESPONSE,
)
def list_reporting_history(employee_id: EmployeeId, reporting: Reporting) -> list[ReportingHistoryItem]:
    return reporting.history(employee_id)


@router.post(
    "/assignments",
    summary="Save who an employee reports to",
    status_code=201,
    dependencies=[CAN_MANAGE],
    responses=NOT_FOUND_RESPONSE,
)
def create_reporting_assignment(
    data: ReportingAssignmentCreate, actor: CurrentUserDep, reporting: Reporting
) -> ReportingAssignmentSaved:
    return reporting.assign(actor, data)


@router.post(
    "/removals",
    summary="Clear who an employee reports to",
    status_code=201,
    dependencies=[CAN_MANAGE],
    responses=NOT_FOUND_RESPONSE,
)
def create_reporting_removal(
    data: ReportingRemovalCreate, actor: CurrentUserDep, reporting: Reporting
) -> ReportingAssignmentSaved:
    return reporting.remove(actor, data)
