"""Attendance API routes (daily, muster, exceptions, shifts, rules, assignments)."""

import base64
import binascii
from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, Header, Path, Query

from trishul_api.auth import CurrentUserDep, DbSession, require_permission
from trishul_api.common.concurrency import if_match_row_version
from trishul_api.common.errors import ApiError
from trishul_api.modules.hr.attendance.finalization_ops import FinalizationService
from trishul_api.modules.hr.attendance.rules_ops import ShiftRulesService
from trishul_api.modules.hr.attendance.schemas import (
    AttendanceDashboardOut,
    AttendanceExceptionRowOut,
    AttendanceExceptionsPageOut,
    AttendanceExceptionsQuery,
    AttendanceHistoryOut,
    AttendanceHolidayPage,
    AttendanceReportsSummaryOut,
    AttendanceRulesOut,
    AttendanceRulesWrite,
    DailyAttendancePageOut,
    DailyAttendanceQuery,
    FinalizationLockOut,
    FinalizationPageOut,
    FinalizationQuery,
    LeaveYearOut,
    MineAttendancePageOut,
    MonthlyMusterPageOut,
    MonthlyMusterQuery,
    RegularizationCreateIn,
    RegularizationDecisionIn,
    RegularizationPageOut,
    RegularizationQuery,
    RegularizationRowOut,
    ResolveExceptionIn,
    ShiftAssignmentItem,
    ShiftAssignmentListQuery,
    ShiftAssignmentOptions,
    ShiftAssignmentPage,
    ShiftAssignmentWrite,
    ShiftItem,
    ShiftListQuery,
    ShiftPage,
    ShiftWrite,
)
from trishul_api.modules.hr.attendance.service import AttendanceService

router = APIRouter(prefix="/hr/attendance", tags=["attendance"])

# ESS (My Attendance) uses view/manage. Org-wide HR screens require manage (Admin/HR).
# Shifts / rules edits / finalize need their own permissions (not implied by HR/ADMIN).
CAN_VIEW = Depends(require_permission("core.employee.view", "core.employee.manage"))
CAN_MANAGE = Depends(require_permission("core.employee.manage"))
CAN_MANAGE_SHIFTS = Depends(require_permission("hr.attendance.shift.manage"))
CAN_MANAGE_RULES = Depends(require_permission("hr.attendance.rules.manage"))
CAN_FINALIZE = Depends(require_permission("hr.attendance.finalize"))


def get_attendance_service(db: DbSession) -> AttendanceService:
    return AttendanceService(db)


def get_shift_rules_service(db: DbSession) -> ShiftRulesService:
    return ShiftRulesService(db)


def get_finalization_service(db: DbSession) -> FinalizationService:
    return FinalizationService(db)


def optional_if_match_row_version(
    if_match: Annotated[str | None, Header(include_in_schema=False)] = None,
) -> bytes | None:
    """If-Match is optional on first save of attendance rules (no row yet)."""
    if not if_match:
        return None
    try:
        return base64.b64decode(if_match.strip().removeprefix("W/").strip('"'), validate=True)
    except (binascii.Error, ValueError) as exc:
        raise ApiError("If-Match is not a valid rowVersion.") from exc


Attendance = Annotated[AttendanceService, Depends(get_attendance_service)]
Rules = Annotated[ShiftRulesService, Depends(get_shift_rules_service)]
Finalization = Annotated[FinalizationService, Depends(get_finalization_service)]
EmployeeId = Annotated[int, Path(alias="employeeId", gt=0)]
RegularizationId = Annotated[int, Path(alias="regularizationId", gt=0)]
ShiftId = Annotated[int, Path(alias="shiftId", gt=0)]
AssignmentId = Annotated[int, Path(alias="assignmentId", gt=0)]
Match = Annotated[bytes, Depends(if_match_row_version)]
OptionalMatch = Annotated[bytes | None, Depends(optional_if_match_row_version)]


@router.get(
    "/dashboard",
    summary="Attendance dashboard KPIs, trend, departments and exceptions for a date",
    dependencies=[CAN_MANAGE],
)
def attendance_dashboard(
    attendance: Attendance,
    day: Annotated[date | None, Query(alias="date")] = None,
) -> AttendanceDashboardOut:
    return attendance.dashboard(day or date.today())


@router.get(
    "/mine",
    summary="ESS: logged-in employee's attendance for a calendar month",
    dependencies=[CAN_VIEW],
)
def my_attendance(
    actor: CurrentUserDep,
    attendance: Attendance,
    year: Annotated[int, Query(ge=2000, le=2100)],
    month: Annotated[int, Query(ge=1, le=12)],
) -> MineAttendancePageOut:
    return attendance.mine(actor, year, month)


@router.post(
    "/mine/regularizations",
    summary="ESS: submit regularization for the authenticated employee only",
    dependencies=[CAN_VIEW],
    status_code=201,
)
def create_mine_regularization(
    data: RegularizationCreateIn,
    actor: CurrentUserDep,
    attendance: Attendance,
) -> RegularizationRowOut:
    return attendance.create_mine_regularization(actor, data)


@router.get(
    "/reports/summary",
    summary="Attendance reports summary for a month (muster + pending queues + lock)",
    dependencies=[CAN_MANAGE],
)
def attendance_reports_summary(
    attendance: Attendance,
    year: Annotated[int, Query(ge=2000, le=2100)],
    month: Annotated[int, Query(ge=1, le=12)],
) -> AttendanceReportsSummaryOut:
    return attendance.reports_summary(year, month)


@router.get(
    "/daily",
    summary="Daily attendance for a date (computed from punches, leave, holidays and shifts)",
    dependencies=[CAN_MANAGE],
)
def list_daily_attendance(
    query: Annotated[DailyAttendanceQuery, Query()],
    attendance: Attendance,
) -> DailyAttendancePageOut:
    return attendance.list_daily(query)


@router.get(
    "/daily/employees/{employeeId}/history",
    summary="Recent attendance history for one employee (lazy-loaded by the drawer)",
    dependencies=[CAN_MANAGE],
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
    dependencies=[CAN_MANAGE],
)
def list_monthly_muster(
    query: Annotated[MonthlyMusterQuery, Query()],
    attendance: Attendance,
) -> MonthlyMusterPageOut:
    return attendance.list_muster(query)


@router.get(
    "/exceptions",
    summary="Attendance exceptions for a date range (computed from punches, leave, holidays and shifts)",
    dependencies=[CAN_MANAGE],
)
def list_attendance_exceptions(
    query: Annotated[AttendanceExceptionsQuery, Query()],
    attendance: Attendance,
) -> AttendanceExceptionsPageOut:
    return attendance.list_exceptions(query)


@router.post(
    "/exceptions/{exceptionId}/resolve",
    summary="Mark an exception resolved via hr.attendance.is_regularized",
    dependencies=[CAN_MANAGE],
)
def resolve_attendance_exception(
    actor: CurrentUserDep,
    attendance: Attendance,
    exception_id: Annotated[int, Path(alias="exceptionId", gt=0)],
    body: ResolveExceptionIn | None = None,
) -> AttendanceExceptionRowOut:
    return attendance.resolve_exception(
        exception_id,
        actor=actor,
        remark=(body.remark if body else None),
        resolved_status=(body.resolved_status if body else None),
    )


@router.get(
    "/regularizations",
    summary="Attendance regularization requests from hr.attendance_regularization",
    dependencies=[CAN_MANAGE],
)
def list_regularizations(
    query: Annotated[RegularizationQuery, Query()],
    attendance: Attendance,
) -> RegularizationPageOut:
    return attendance.list_regularizations(query)


@router.post(
    "/regularizations",
    summary="HR/Admin: create a regularization request for an employee",
    dependencies=[CAN_MANAGE],
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


# --------------------------------------------------------------------------- shifts


@router.get("/shifts", summary="List work shifts from hr.shift", dependencies=[CAN_MANAGE])
def list_shifts(query: Annotated[ShiftListQuery, Query()], rules: Rules) -> ShiftPage:
    return rules.list_shifts(query)


@router.get("/shifts/{shiftId}", summary="Get one work shift", dependencies=[CAN_MANAGE])
def get_shift(shift_id: ShiftId, rules: Rules) -> ShiftItem:
    return rules.get_shift(shift_id)


@router.post(
    "/shifts",
    summary="Create a work shift",
    dependencies=[CAN_MANAGE_SHIFTS],
    status_code=201,
)
def create_shift(data: ShiftWrite, actor: CurrentUserDep, rules: Rules) -> ShiftItem:
    return rules.create_shift(actor, data)


@router.patch(
    "/shifts/{shiftId}",
    summary="Update a work shift",
    dependencies=[CAN_MANAGE_SHIFTS],
)
def update_shift(
    shift_id: ShiftId, data: ShiftWrite, actor: CurrentUserDep, rules: Rules, row_version: Match
) -> ShiftItem:
    return rules.update_shift(actor, shift_id, row_version, data)


@router.delete(
    "/shifts/{shiftId}",
    summary="Deactivate a work shift",
    dependencies=[CAN_MANAGE_SHIFTS],
    status_code=204,
)
def delete_shift(shift_id: ShiftId, rules: Rules, row_version: Match) -> None:
    rules.delete_shift(shift_id, row_version)


# --------------------------------------------------------------------------- attendance rules + leave year


@router.get(
    "/leave-year",
    summary="Current leave year from leave-policy year basis (financial or calendar)",
    dependencies=[CAN_MANAGE],
)
def current_leave_year(rules: Rules) -> LeaveYearOut:
    return rules.leave_year()


@router.get(
    "/holidays",
    summary="Holidays for the current configured leave year (from hr.holiday)",
    dependencies=[CAN_MANAGE],
)
def attendance_holidays(rules: Rules) -> AttendanceHolidayPage:
    return rules.holidays_for_leave_year()


@router.get(
    "/rules",
    summary="Organization attendance rules (core.system_setting hr.attendance.rules)",
    dependencies=[CAN_MANAGE],
)
def get_attendance_rules(rules: Rules) -> AttendanceRulesOut:
    return rules.get_rules()


@router.put(
    "/rules",
    summary="Save organization attendance rules",
    dependencies=[CAN_MANAGE_RULES],
)
def put_attendance_rules(
    data: AttendanceRulesWrite, actor: CurrentUserDep, rules: Rules, row_version: OptionalMatch
) -> AttendanceRulesOut:
    return rules.put_rules(actor, data, row_version)


# --------------------------------------------------------------------------- shift assignments


@router.get(
    "/shift-assignments/options",
    summary="Employees and shifts for assignment forms",
    dependencies=[CAN_MANAGE],
)
def shift_assignment_options(rules: Rules) -> ShiftAssignmentOptions:
    return rules.assignment_options()


@router.get(
    "/shift-assignments",
    summary="Employee shift assignments from hr.employee_shift (includes history when currentOnly=false)",
    dependencies=[CAN_MANAGE],
)
def list_shift_assignments(
    query: Annotated[ShiftAssignmentListQuery, Query()], rules: Rules
) -> ShiftAssignmentPage:
    return rules.list_assignments(query)


@router.post(
    "/shift-assignments",
    summary="Assign a shift (closes overlapping prior assignments to preserve history)",
    dependencies=[CAN_MANAGE_SHIFTS],
    status_code=201,
)
def create_shift_assignment(
    data: ShiftAssignmentWrite, actor: CurrentUserDep, rules: Rules
) -> ShiftAssignmentItem:
    return rules.create_assignment(actor, data)


@router.patch(
    "/shift-assignments/{assignmentId}",
    summary="Update a shift assignment",
    dependencies=[CAN_MANAGE_SHIFTS],
)
def update_shift_assignment(
    assignment_id: AssignmentId,
    data: ShiftAssignmentWrite,
    actor: CurrentUserDep,
    rules: Rules,
    row_version: Match,
) -> ShiftAssignmentItem:
    return rules.update_assignment(actor, assignment_id, row_version, data)


@router.delete(
    "/shift-assignments/{assignmentId}",
    summary="End / deactivate a shift assignment",
    dependencies=[CAN_MANAGE_SHIFTS],
    status_code=204,
)
def delete_shift_assignment(assignment_id: AssignmentId, rules: Rules, row_version: Match) -> None:
    rules.delete_assignment(assignment_id, row_version)


# --------------------------------------------------------------------------- finalization


@router.get(
    "/finalization",
    summary="Monthly attendance finalization overview by department or location",
    dependencies=[CAN_MANAGE],
)
def attendance_finalization(
    query: Annotated[FinalizationQuery, Query()], finalization: Finalization
) -> FinalizationPageOut:
    return finalization.overview(query)


@router.post(
    "/finalization/lock",
    summary="Finalize and lock monthly attendance after checklist validations pass",
    dependencies=[CAN_FINALIZE],
)
def lock_attendance_finalization(
    actor: CurrentUserDep,
    finalization: Finalization,
    year: Annotated[int, Query(ge=2000, le=2100)],
    month: Annotated[int, Query(ge=1, le=12)],
) -> FinalizationLockOut:
    return finalization.finalize(actor, year, month)
