"""Attendance API routes (daily, muster, exceptions)."""

from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, Path, Query

from trishul_api.auth import CurrentUserDep, DbSession, require_permission
from trishul_api.modules.hr.attendance.schemas import (
    AttendanceExceptionRowOut,
    AttendanceExceptionsPageOut,
    AttendanceExceptionsQuery,
    AttendanceHistoryOut,
    DailyAttendancePageOut,
    DailyAttendanceQuery,
    MonthlyMusterPageOut,
    MonthlyMusterQuery,
    RegularizationCreateIn,
    RegularizationDecisionIn,
    RegularizationPageOut,
    RegularizationQuery,
    RegularizationRowOut,
    ResolveExceptionIn,
)
from trishul_api.modules.hr.attendance.service import AttendanceService

router = APIRouter(prefix="/hr/attendance", tags=["attendance"])

# Match the Daily Attendance screen route guard (employee view/manage).
CAN_VIEW = Depends(require_permission("core.employee.view", "core.employee.manage"))
CAN_MANAGE = Depends(require_permission("core.employee.manage"))


def get_attendance_service(db: DbSession) -> AttendanceService:
    return AttendanceService(db)


Attendance = Annotated[AttendanceService, Depends(get_attendance_service)]
EmployeeId = Annotated[int, Path(alias="employeeId", gt=0)]
RegularizationId = Annotated[int, Path(alias="regularizationId", gt=0)]


@router.get(
    "/daily",
    summary="Daily attendance for a date (computed from punches, leave, holidays and shifts)",
    dependencies=[CAN_VIEW],
)
def list_daily_attendance(
    query: Annotated[DailyAttendanceQuery, Query()],
    attendance: Attendance,
) -> DailyAttendancePageOut:
    return attendance.list_daily(query)


@router.get(
    "/daily/employees/{employeeId}/history",
    summary="Recent attendance history for one employee (lazy-loaded by the drawer)",
    dependencies=[CAN_VIEW],
)
def employee_attendance_history(
    employee_id: EmployeeId,
    attendance: Attendance,
    before: Annotated[date, Query(description="History ends the day before this date")],
    days: Annotated[int, Query(ge=1, le=31)] = 7,
) -> list[AttendanceHistoryOut]:
    return attendance.employee_history(employee_id, before, days=days)


@router.get(
    "/muster",
    summary="Monthly muster matrix (computed from punches, leave, holidays and shifts)",
    dependencies=[CAN_VIEW],
)
def list_monthly_muster(
    query: Annotated[MonthlyMusterQuery, Query()],
    attendance: Attendance,
) -> MonthlyMusterPageOut:
    return attendance.list_muster(query)


@router.get(
    "/exceptions",
    summary="Attendance exceptions for a date range (computed from punches, leave, holidays and shifts)",
    dependencies=[CAN_VIEW],
)
def list_attendance_exceptions(
    query: Annotated[AttendanceExceptionsQuery, Query()],
    attendance: Attendance,
) -> AttendanceExceptionsPageOut:
    return attendance.list_exceptions(query)


@router.post(
    "/exceptions/{exceptionId}/resolve",
    summary="Mark an exception resolved via hr.attendance.is_regularized",
    dependencies=[CAN_VIEW],
)
def resolve_attendance_exception(
    attendance: Attendance,
    exception_id: Annotated[int, Path(alias="exceptionId", gt=0)],
    body: ResolveExceptionIn | None = None,
) -> AttendanceExceptionRowOut:
    return attendance.resolve_exception(exception_id, remark=(body.remark if body else None))


@router.get(
    "/regularizations",
    summary="Attendance regularization requests from hr.attendance_regularization",
    dependencies=[CAN_VIEW],
)
def list_regularizations(
    query: Annotated[RegularizationQuery, Query()],
    attendance: Attendance,
) -> RegularizationPageOut:
    return attendance.list_regularizations(query)


@router.post(
    "/regularizations",
    summary="Create an attendance regularization request",
    dependencies=[CAN_VIEW],
)
def create_regularization(
    data: RegularizationCreateIn,
    actor: CurrentUserDep,
    attendance: Attendance,
) -> RegularizationRowOut:
    return attendance.create_regularization(actor, data)


@router.post(
    "/regularizations/{regularizationId}/approve",
    summary="Approve a pending regularization request",
    dependencies=[CAN_MANAGE],
)
def approve_regularization(
    regularization_id: RegularizationId,
    actor: CurrentUserDep,
    attendance: Attendance,
    body: RegularizationDecisionIn | None = None,
) -> RegularizationRowOut:
    return attendance.decide_regularization(actor, regularization_id, approve=True, data=body)


@router.post(
    "/regularizations/{regularizationId}/reject",
    summary="Reject a pending regularization request",
    dependencies=[CAN_MANAGE],
)
def reject_regularization(
    regularization_id: RegularizationId,
    actor: CurrentUserDep,
    attendance: Attendance,
    body: RegularizationDecisionIn,
) -> RegularizationRowOut:
    return attendance.decide_regularization(actor, regularization_id, approve=False, data=body)
