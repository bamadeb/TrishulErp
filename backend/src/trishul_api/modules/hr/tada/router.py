"""Service engineer TA/DA report over trk.trip. Shown in Swagger under the payroll tag."""

from typing import Annotated

from fastapi import APIRouter, Depends, Path, Query

from trishul_api.auth import CurrentUserDep, DbSession, require_permission
from trishul_api.common.errors import NOT_FOUND_RESPONSE
from trishul_api.modules.hr.tada.schemas import (
    TadaBulkResult,
    TadaDecisionCreate,
    TadaEmployeeQuery,
    TadaEmployeeReport,
    TadaRates,
    TadaRatesUpdate,
    TadaReport,
    TadaReportQuery,
    TadaSettlementCreate,
    TadaTripDetail,
    TadaTripItem,
)
from trishul_api.modules.hr.tada.service import TadaService

router = APIRouter(prefix="/hr", tags=["payroll"])

CAN_VIEW = Depends(require_permission("core.employee.view", "core.employee.manage"))
CAN_MANAGE = Depends(require_permission("core.employee.manage"))

TripId = Annotated[int, Path(alias="tripId", gt=0)]
EmployeeId = Annotated[int, Path(alias="employeeId", gt=0)]
Month = Annotated[str, Query(pattern=r"^\d{4}-(0[1-9]|1[0-2])$", description="Payroll month, YYYY-MM.")]


def get_tada_service(db: DbSession) -> TadaService:
    return TadaService(db)


Tada = Annotated[TadaService, Depends(get_tada_service)]
ReportQuery = Annotated[TadaReportQuery, Query()]
EmployeeQuery = Annotated[TadaEmployeeQuery, Query()]


@router.get("/tada/report", summary="Service engineer TA/DA trips for a payroll month", dependencies=[CAN_VIEW])
def get_tada_report(query: ReportQuery, tada: Tada) -> TadaReport:
    return tada.report(query)


@router.get("/tada/employees", summary="Employee TA/DA summary for a payroll month", dependencies=[CAN_VIEW])
def get_tada_employees(query: EmployeeQuery, tada: Tada) -> TadaEmployeeReport:
    return tada.employees(query)


@router.get(
    "/tada/employees/{employeeId}/trips",
    summary="Trips for one employee in a payroll month",
    dependencies=[CAN_VIEW],
    responses=NOT_FOUND_RESPONSE,
)
def list_tada_employee_trips(employee_id: EmployeeId, month: Month, tada: Tada) -> list[TadaTripItem]:
    return tada.employee_trips(employee_id, month)


@router.post(
    "/tada/decisions",
    summary="Approve or reject selected employees",
    status_code=201,
    dependencies=[CAN_MANAGE],
)
def create_tada_decisions(data: TadaDecisionCreate, actor: CurrentUserDep, tada: Tada) -> TadaBulkResult:
    return tada.decide(data, actor)


@router.post(
    "/tada/settlements",
    summary="Send approved employees to payroll",
    status_code=201,
    dependencies=[CAN_MANAGE],
)
def create_tada_settlements(data: TadaSettlementCreate, actor: CurrentUserDep, tada: Tada) -> TadaBulkResult:
    return tada.send_to_payroll(data, actor)


@router.get(
    "/tada/trips/{tripId}",
    summary="One trip with route and monthly salary allowances",
    dependencies=[CAN_VIEW],
    responses=NOT_FOUND_RESPONSE,
)
def get_tada_trip(trip_id: TripId, tada: Tada) -> TadaTripDetail:
    return tada.trip(trip_id)


@router.get("/tada/rates", summary="Configured bike and car TA rates", dependencies=[CAN_VIEW])
def get_tada_rates(tada: Tada) -> TadaRates:
    return tada.rates()


@router.post("/tada/rates", summary="Save bike and car TA rates", status_code=201, dependencies=[CAN_MANAGE])
def create_tada_rates(data: TadaRatesUpdate, actor: CurrentUserDep, tada: Tada) -> TadaRates:
    return tada.save_rates(data, actor)
