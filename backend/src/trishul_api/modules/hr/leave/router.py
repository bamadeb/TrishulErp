"""Leave type and policy routes."""

from typing import Annotated

from fastapi import APIRouter, Depends, Path, Query, Response

from trishul_api.auth import CurrentUserDep, DbSession, require_permission
from trishul_api.common.concurrency import if_match_row_version
from trishul_api.common.errors import CONCURRENCY_RESPONSES, NOT_FOUND_RESPONSE
from trishul_api.common.schemas import Page
from trishul_api.modules.hr.leave.balance_ops import (
    adjust_balance,
    balance_board,
    balance_detail,
    generate_entitlements,
    preview_generation,
)
from trishul_api.modules.hr.leave.balance_schemas import (
    BalanceAdjustment,
    BalanceBoard,
    BalanceDetail,
    EntitlementGenerateResult,
    EntitlementPreviewBoard,
    EntitlementPreviewRequest,
)
from trishul_api.modules.hr.leave.calendar_ops import LeaveCalendarRepository
from trishul_api.modules.hr.leave.calendar_schemas import LeaveCalendarBoard, LeaveCalendarQuery, LeaveCalendarSummary
from trishul_api.modules.hr.leave.dashboard_repository import LeaveDashboardRepository
from trishul_api.modules.hr.leave.dashboard_schemas import LeaveDashboard, LeaveDashboardQuery
from trishul_api.modules.hr.leave.employee_ops import EmployeeLeaveRepository
from trishul_api.modules.hr.leave.employee_schemas import (
    EmployeeLeaveBalanceView,
    EmployeeLeaveDetail,
    EmployeeLeaveHistoryItem,
    EmployeeLeavePage,
    EmployeeLeaveQuery,
    EmployeeLeaveStats,
    EmployeeUpcomingLeave,
)
from trishul_api.modules.hr.leave.holiday_ops import HolidayRepository
from trishul_api.modules.hr.leave.holiday_schemas import (
    HolidayCalendarQuery,
    HolidayFilters,
    HolidayItem,
    HolidayListQuery,
    HolidaySummary,
    HolidaySummaryQuery,
    HolidayWrite,
)
from trishul_api.modules.hr.leave.mine_repository import LeaveMineRepository
from trishul_api.modules.hr.leave.mine_schemas import (
    MineApply,
    MineBalances,
    MineCompOff,
    MineDayCount,
    MineDayCountResult,
    MineHoliday,
    MineHolidayQuery,
    MineProfile,
    MineRequestDetail,
    MineRequestPage,
    MineRequestQuery,
)
from trishul_api.modules.hr.leave.policy_ops import (
    assign,
    assignments,
    attendance_classes,
    grant_weekly_rest,
    preview_entitlement,
    save_attendance_classes,
)
from trishul_api.modules.hr.leave.request_ops import LeaveRequestRepository
from trishul_api.modules.hr.leave.request_schemas import (
    LeaveComment,
    LeaveHistoryEvent,
    LeaveReject,
    LeaveRequestDetail,
    LeaveRequestFilter,
    LeaveRequestPage,
    LeaveRequestQuery,
    LeaveRequestSummary,
)
from trishul_api.modules.hr.leave.schemas import (
    AttendanceClassItem,
    AttendanceClassWrite,
    EntitlementPreview,
    EntitlementPreviewQuery,
    LeaveAssignmentItem,
    LeaveAssignmentWrite,
    LeavePolicyItem,
    LeavePolicyLineItem,
    LeavePolicyQuery,
    LeavePolicyWrite,
    LeaveTypeItem,
    LeaveTypeQuery,
    LeaveTypeWrite,
    WeeklyRestGrantItem,
    WeeklyRestGrantWrite,
)
from trishul_api.modules.hr.leave.service import LeaveService

router = APIRouter(prefix="/hr/leave", tags=["leave"])

CAN_VIEW = Depends(require_permission("hr.leave.view", "hr.leave.manage"))
CAN_APPLY = Depends(require_permission("hr.leave.apply", "hr.leave.manage"))
CAN_MANAGE = Depends(require_permission("hr.leave.manage"))
CAN_DECIDE = Depends(require_permission("hr.leave.approve", "hr.leave.manage"))
TypeId = Annotated[int, Path(alias="leaveTypeId", gt=0)]
PolicyId = Annotated[int, Path(alias="leavePolicyId", gt=0)]
RequestId = Annotated[int, Path(alias="requestId", gt=0)]
EmployeeId = Annotated[int, Path(alias="employeeId", gt=0)]
Year = Annotated[int, Query(alias="financialYear", ge=2000, le=2100)]
TypeQuery = Annotated[LeaveTypeQuery, Query()]
PolicyQuery = Annotated[LeavePolicyQuery, Query()]
Match = Annotated[bytes, Depends(if_match_row_version)]


def get_leave_service(db: DbSession) -> LeaveService:
    return LeaveService(db)


Leave = Annotated[LeaveService, Depends(get_leave_service)]
DashQuery = Annotated[LeaveDashboardQuery, Query()]
MineQuery = Annotated[MineRequestQuery, Query()]
HolidayQuery = Annotated[MineHolidayQuery, Query()]


def get_leave_mine(db: DbSession) -> LeaveMineRepository:
    return LeaveMineRepository(db)


Mine = Annotated[LeaveMineRepository, Depends(get_leave_mine)]
RequestQuery = Annotated[LeaveRequestQuery, Query()]
RequestFilter = Annotated[LeaveRequestFilter, Query()]


def get_leave_requests(db: DbSession) -> LeaveRequestRepository:
    return LeaveRequestRepository(db)


Requests = Annotated[LeaveRequestRepository, Depends(get_leave_requests)]
EmployeeLeaveQueryDep = Annotated[EmployeeLeaveQuery, Query()]


def get_employee_leaves(db: DbSession) -> EmployeeLeaveRepository:
    return EmployeeLeaveRepository(db)


EmployeeLeaves = Annotated[EmployeeLeaveRepository, Depends(get_employee_leaves)]


def get_leave_calendar(db: DbSession) -> LeaveCalendarRepository:
    return LeaveCalendarRepository(db)


Calendar = Annotated[LeaveCalendarRepository, Depends(get_leave_calendar)]
CalendarQuery = Annotated[LeaveCalendarQuery, Query()]


def get_holidays(db: DbSession) -> HolidayRepository:
    return HolidayRepository(db)


Holidays = Annotated[HolidayRepository, Depends(get_holidays)]
HolidayList = Annotated[HolidayListQuery, Query()]
HolidaySummaryFilter = Annotated[HolidaySummaryQuery, Query()]
HolidayCalendarFilter = Annotated[HolidayCalendarQuery, Query()]
HolidayId = Annotated[int, Path(alias="holidayId", gt=0)]


@router.get("/requests/summary", summary="Leave request counts for the selected filters", dependencies=[CAN_VIEW])
def leave_request_summary(query: RequestFilter, actor: CurrentUserDep, requests: Requests) -> LeaveRequestSummary:
    return requests.summary(actor, query)


@router.get("/requests", summary="Leave requests for employees in the caller's scope", dependencies=[CAN_VIEW])
def leave_requests(query: RequestQuery, actor: CurrentUserDep, requests: Requests) -> LeaveRequestPage:
    return requests.page(actor, query)


@router.get(
    "/requests/{requestId}",
    summary="One leave request with employee and approval history",
    dependencies=[CAN_VIEW],
    responses=NOT_FOUND_RESPONSE,
)
def leave_request(request_id: RequestId, actor: CurrentUserDep, requests: Requests) -> LeaveRequestDetail:
    return requests.detail(actor, request_id)


@router.get(
    "/requests/{requestId}/history",
    summary="Approval history and comments for one leave request",
    dependencies=[CAN_VIEW],
    responses=NOT_FOUND_RESPONSE,
)
def leave_request_history(
    request_id: RequestId, actor: CurrentUserDep, requests: Requests
) -> list[LeaveHistoryEvent]:
    return requests.history(actor, request_id)


@router.post(
    "/requests/{requestId}/approve",
    summary="Approve a pending leave request and deduct the balance",
    dependencies=[CAN_DECIDE],
    responses=NOT_FOUND_RESPONSE,
)
def leave_request_approve(request_id: RequestId, actor: CurrentUserDep, requests: Requests) -> LeaveRequestDetail:
    return requests.approve(actor, request_id)


@router.post(
    "/requests/{requestId}/reject",
    summary="Reject a pending leave request without deducting balance",
    dependencies=[CAN_DECIDE],
    responses=NOT_FOUND_RESPONSE,
)
def leave_request_reject(
    request_id: RequestId, data: LeaveReject, actor: CurrentUserDep, requests: Requests
) -> LeaveRequestDetail:
    return requests.reject(actor, request_id, data.remarks)


@router.post(
    "/requests/{requestId}/comments",
    summary="Add a comment to a leave request",
    dependencies=[CAN_VIEW],
    responses=NOT_FOUND_RESPONSE,
)
def leave_request_comment(
    request_id: RequestId, data: LeaveComment, actor: CurrentUserDep, requests: Requests
) -> LeaveRequestDetail:
    return requests.comment(actor, request_id, data.remarks)


@router.get("/employees/summary", summary="Employee leave counts for the selected year", dependencies=[CAN_VIEW])
def employee_leave_summary(
    query: EmployeeLeaveQueryDep, actor: CurrentUserDep, employees: EmployeeLeaves
) -> EmployeeLeaveStats:
    return employees.stats(actor, query)


@router.get("/employees/upcoming", summary="Approved leave that starts after today", dependencies=[CAN_VIEW])
def employee_leave_upcoming(
    query: EmployeeLeaveQueryDep, actor: CurrentUserDep, employees: EmployeeLeaves
) -> list[EmployeeUpcomingLeave]:
    return employees.upcoming(actor, query)


@router.get("/employees/export", summary="Employee leave rows for the current filters", dependencies=[CAN_VIEW])
def employee_leave_export(
    query: EmployeeLeaveQueryDep, actor: CurrentUserDep, employees: EmployeeLeaves
) -> EmployeeLeavePage:
    return employees.export(actor, query)


@router.get("/employees", summary="Employee leave register", dependencies=[CAN_VIEW])
def employee_leaves(
    query: EmployeeLeaveQueryDep, actor: CurrentUserDep, employees: EmployeeLeaves
) -> EmployeeLeavePage:
    return employees.page(actor, query)


@router.get(
    "/employees/{employeeId}/history",
    summary="Leave applications for one employee in the financial year",
    dependencies=[CAN_VIEW],
    responses=NOT_FOUND_RESPONSE,
)
def employee_leave_history(
    employee_id: EmployeeId, financial_year: Year, actor: CurrentUserDep, employees: EmployeeLeaves
) -> list[EmployeeLeaveHistoryItem]:
    return employees.history(actor, employee_id, financial_year)


@router.get(
    "/employees/{employeeId}/balance",
    summary="Stored leave balances for one employee",
    dependencies=[CAN_VIEW],
    responses=NOT_FOUND_RESPONSE,
)
def employee_leave_balance(
    employee_id: EmployeeId, financial_year: Year, actor: CurrentUserDep, employees: EmployeeLeaves
) -> dict[str, EmployeeLeaveBalanceView]:
    return employees.balance(actor, employee_id, financial_year)


@router.get(
    "/employees/{employeeId}",
    summary="Employee leave details, history and stored balances",
    dependencies=[CAN_VIEW],
    responses=NOT_FOUND_RESPONSE,
)
def employee_leave_detail(
    employee_id: EmployeeId, financial_year: Year, actor: CurrentUserDep, employees: EmployeeLeaves
) -> EmployeeLeaveDetail:
    return employees.detail(actor, employee_id, financial_year)


@router.get("/calendar/summary", summary="Leave calendar counts for the selected month", dependencies=[CAN_VIEW])
def leave_calendar_summary(
    query: CalendarQuery, actor: CurrentUserDep, calendar: Calendar
) -> LeaveCalendarSummary:
    return calendar.summary(actor, query)


@router.get("/calendar", summary="Leave calendar entries, holidays and counts", dependencies=[CAN_VIEW])
def leave_calendar(query: CalendarQuery, actor: CurrentUserDep, calendar: Calendar) -> LeaveCalendarBoard:
    return calendar.board(actor, query)


@router.get("/holidays/filters", summary="Holiday categories, states, locations and years", dependencies=[CAN_VIEW])
def holiday_filters(holidays: Holidays) -> HolidayFilters:
    return holidays.filters()


@router.get("/holidays/summary", summary="Holiday counts for the selected filters", dependencies=[CAN_VIEW])
def holiday_summary(query: HolidaySummaryFilter, holidays: Holidays) -> HolidaySummary:
    return holidays.summary(query)


@router.get("/holidays/calendar", summary="Holidays between two dates", dependencies=[CAN_VIEW])
def holiday_calendar(query: HolidayCalendarFilter, holidays: Holidays) -> list[HolidayItem]:
    return holidays.calendar(query)


@router.get("/holidays", summary="Holiday list", dependencies=[CAN_VIEW])
def holiday_list(query: HolidayList, holidays: Holidays) -> Page[HolidayItem]:
    items, total = holidays.page(query)
    return Page(items=items, total=total, page=query.page, page_size=query.page_size)


@router.post("/holidays", summary="Add a holiday", status_code=201, dependencies=[CAN_MANAGE])
def create_holiday(data: HolidayWrite, actor: CurrentUserDep, holidays: Holidays, response: Response) -> HolidayItem:
    created = holidays.create(actor, data)
    response.headers["Location"] = f"holidays/{created.id}"
    return created


@router.get(
    "/holidays/{holidayId}",
    summary="One holiday",
    dependencies=[CAN_VIEW],
    responses=NOT_FOUND_RESPONSE,
)
def holiday_detail(holiday_id: HolidayId, holidays: Holidays) -> HolidayItem:
    return holidays.get(holiday_id)


@router.patch(
    "/holidays/{holidayId}",
    summary="Change a holiday",
    dependencies=[CAN_MANAGE],
    responses={**NOT_FOUND_RESPONSE, **CONCURRENCY_RESPONSES},
)
def update_holiday(
    holiday_id: HolidayId, data: HolidayWrite, actor: CurrentUserDep, holidays: Holidays, row_version: Match
) -> HolidayItem:
    return holidays.update(actor, holiday_id, row_version, data)


@router.delete(
    "/holidays/{holidayId}",
    summary="Delete a holiday",
    status_code=204,
    dependencies=[CAN_MANAGE],
    responses={**NOT_FOUND_RESPONSE, **CONCURRENCY_RESPONSES},
)
def delete_holiday(holiday_id: HolidayId, holidays: Holidays, row_version: Match) -> None:
    holidays.delete(holiday_id, row_version)


@router.get("/dashboard", summary="Leave dashboard for the selected month", dependencies=[CAN_VIEW])
def leave_dashboard(query: DashQuery, actor: CurrentUserDep, db: DbSession) -> LeaveDashboard:
    return LeaveDashboardRepository(db).build(actor, query)


@router.get("/mine/profile", summary="Signed-in employee profile for My Leave", dependencies=[CAN_VIEW])
def leave_mine_profile(actor: CurrentUserDep, mine: Mine) -> MineProfile:
    return mine.profile(actor)


@router.get("/mine/balances", summary="Signed-in employee leave balances", dependencies=[CAN_VIEW])
def leave_mine_balances(financial_year: Year, actor: CurrentUserDep, mine: Mine) -> MineBalances:
    return mine.balances(actor, financial_year)


@router.get("/mine/comp-off", summary="Signed-in employee compensatory off balance", dependencies=[CAN_VIEW])
def leave_mine_comp_off(financial_year: Year, actor: CurrentUserDep, mine: Mine) -> MineCompOff:
    return mine.comp_off(actor, financial_year)


@router.get("/mine/holidays", summary="Holidays for the signed-in employee's branch", dependencies=[CAN_VIEW])
def leave_mine_holidays(query: HolidayQuery, actor: CurrentUserDep, mine: Mine) -> list[MineHoliday]:
    return mine.holidays(actor, query)


@router.post("/mine/day-count", summary="Count leave days using company rules", dependencies=[CAN_APPLY])
def leave_mine_day_count(data: MineDayCount, actor: CurrentUserDep, mine: Mine) -> MineDayCountResult:
    return MineDayCountResult(days=mine.count_days(actor, data))


@router.get("/mine/requests", summary="Signed-in employee leave requests", dependencies=[CAN_VIEW])
def leave_mine_requests(query: MineQuery, actor: CurrentUserDep, mine: Mine) -> MineRequestPage:
    return mine.requests(actor, query)


@router.post("/mine/requests", summary="Apply for leave", status_code=201, dependencies=[CAN_APPLY])
def leave_mine_apply(data: MineApply, actor: CurrentUserDep, mine: Mine, response: Response) -> MineRequestDetail:
    created = mine.apply(actor, data)
    response.headers["Location"] = f"mine/requests/{created.request_id}"
    return created


@router.get(
    "/mine/requests/{requestId}",
    summary="One of the signed-in employee's leave requests",
    dependencies=[CAN_VIEW],
    responses=NOT_FOUND_RESPONSE,
)
def leave_mine_request(request_id: RequestId, actor: CurrentUserDep, mine: Mine) -> MineRequestDetail:
    return mine.request(actor, request_id)


@router.patch(
    "/mine/requests/{requestId}",
    summary="Change a pending leave request",
    dependencies=[CAN_APPLY],
    responses=NOT_FOUND_RESPONSE,
)
def leave_mine_update(request_id: RequestId, data: MineApply, actor: CurrentUserDep, mine: Mine) -> MineRequestDetail:
    return mine.update(actor, request_id, data)


@router.post(
    "/mine/requests/{requestId}/cancel",
    summary="Cancel the signed-in employee's leave request",
    dependencies=[CAN_APPLY],
    responses=NOT_FOUND_RESPONSE,
)
def leave_mine_cancel(request_id: RequestId, actor: CurrentUserDep, mine: Mine) -> MineRequestDetail:
    return mine.cancel(actor, request_id)


@router.get("/types", summary="Leave types", dependencies=[CAN_VIEW])
def list_leave_types(query: TypeQuery, leave: Leave) -> Page[LeaveTypeItem]:
    return leave.list_types(query)


@router.post("/types", summary="Add a leave type", status_code=201, dependencies=[CAN_MANAGE])
def create_leave_type(data: LeaveTypeWrite, actor: CurrentUserDep, leave: Leave, response: Response) -> LeaveTypeItem:
    created = leave.create_type(actor, data)
    response.headers["Location"] = f"types/{created.id}"
    return created


@router.patch(
    "/types/{leaveTypeId}",
    summary="Change a leave type",
    dependencies=[CAN_MANAGE],
    responses={**NOT_FOUND_RESPONSE, **CONCURRENCY_RESPONSES},
)
def update_leave_type(
    leave_type_id: TypeId, data: LeaveTypeWrite, actor: CurrentUserDep, leave: Leave, row_version: Match
) -> LeaveTypeItem:
    return leave.update_type(actor, leave_type_id, row_version, data)


@router.get("/policies", summary="Leave policies", dependencies=[CAN_VIEW])
def list_leave_policies(query: PolicyQuery, leave: Leave) -> Page[LeavePolicyItem]:
    return leave.list_policies(query)


@router.post("/policies", summary="Add a leave policy", status_code=201, dependencies=[CAN_MANAGE])
def create_leave_policy(
    data: LeavePolicyWrite, actor: CurrentUserDep, leave: Leave, response: Response
) -> LeavePolicyItem:
    created = leave.create_policy(actor, data)
    response.headers["Location"] = f"policies/{created.id}"
    return created


@router.patch(
    "/policies/{leavePolicyId}",
    summary="Change a leave policy",
    dependencies=[CAN_MANAGE],
    responses={**NOT_FOUND_RESPONSE, **CONCURRENCY_RESPONSES},
)
def update_leave_policy(
    policy_id: PolicyId, data: LeavePolicyWrite, actor: CurrentUserDep, leave: Leave, row_version: Match
) -> LeavePolicyItem:
    return leave.update_policy(actor, policy_id, row_version, data)


@router.get(
    "/policies/{leavePolicyId}",
    summary="One leave policy",
    dependencies=[CAN_VIEW],
    responses=NOT_FOUND_RESPONSE,
)
def get_leave_policy(policy_id: PolicyId, leave: Leave) -> LeavePolicyItem:
    return leave.get_policy(policy_id)


@router.get(
    "/policies/{leavePolicyId}/entitlements",
    summary="Entitlement lines on a leave policy",
    dependencies=[CAN_VIEW],
    responses=NOT_FOUND_RESPONSE,
)
def leave_policy_entitlements(policy_id: PolicyId, leave: Leave) -> list[LeavePolicyLineItem]:
    return leave.get_policy(policy_id).lines


@router.get(
    "/policies/{leavePolicyId}/assignments",
    summary="Employees explicitly assigned to a leave policy",
    dependencies=[CAN_VIEW],
    responses=NOT_FOUND_RESPONSE,
)
def leave_policy_assignments(policy_id: PolicyId, db: DbSession) -> list[LeaveAssignmentItem]:
    return assignments(db, policy_id)


@router.post(
    "/policies/{leavePolicyId}/assign",
    summary="Assign an employee to an active explicit policy",
    status_code=201,
    dependencies=[CAN_MANAGE],
    responses=NOT_FOUND_RESPONSE,
)
def leave_policy_assign(
    policy_id: PolicyId, data: LeaveAssignmentWrite, actor: CurrentUserDep, db: DbSession
) -> LeaveAssignmentItem:
    return assign(db, actor, policy_id, data)


@router.post(
    "/policies/{leavePolicyId}/entitlement-preview",
    summary="Preview formula entitlement from classified attendance without writing balances",
    dependencies=[CAN_MANAGE],
    responses=NOT_FOUND_RESPONSE,
)
def leave_entitlement_preview(
    policy_id: PolicyId, query: EntitlementPreviewQuery, actor: CurrentUserDep, db: DbSession
) -> EntitlementPreview:
    return preview_entitlement(db, actor, policy_id, query)


@router.get("/attendance-classes", summary="Attendance status classification", dependencies=[CAN_VIEW])
def list_attendance_classes(db: DbSession) -> list[AttendanceClassItem]:
    return attendance_classes(db)


@router.put("/attendance-classes", summary="Save attendance status classification", dependencies=[CAN_MANAGE])
def put_attendance_classes(
    rows: list[AttendanceClassWrite], actor: CurrentUserDep, db: DbSession
) -> list[AttendanceClassItem]:
    return save_attendance_classes(db, actor, rows)


@router.post(
    "/weekly-rest-grants",
    summary="Record statutory weekly-rest compensatory leave",
    status_code=201,
    dependencies=[CAN_MANAGE],
    responses=NOT_FOUND_RESPONSE,
)
def post_weekly_rest_grant(
    data: WeeklyRestGrantWrite, actor: CurrentUserDep, db: DbSession
) -> WeeklyRestGrantItem:
    return grant_weekly_rest(db, actor, data)


@router.get("/balances", summary="Employee leave balances for a policy year", dependencies=[CAN_VIEW])
def list_leave_balances(
    actor: CurrentUserDep,
    db: DbSession,
    year: Annotated[int, Query(ge=2000, le=2100)],
    policy_id: Annotated[int | None, Query(alias="policyId")] = None,
    department_id: Annotated[int | None, Query(alias="departmentId")] = None,
    branch_id: Annotated[int | None, Query(alias="branchId")] = None,
    search: Annotated[str | None, Query()] = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(alias="pageSize", ge=1, le=100)] = 10,
    sort: Annotated[str, Query()] = "employeeCode",
) -> BalanceBoard:
    return balance_board(
        db,
        actor,
        year=year,
        policy_id=policy_id,
        department_id=department_id,
        branch_id=branch_id,
        search=search,
        page=page,
        page_size=page_size,
        sort=sort,
    )


@router.post(
    "/balances/entitlement-preview",
    summary="Preview entitlement credits without posting balances",
    dependencies=[CAN_MANAGE],
)
def post_entitlement_preview(
    data: EntitlementPreviewRequest, actor: CurrentUserDep, db: DbSession
) -> EntitlementPreviewBoard:
    return preview_generation(db, actor, data)


@router.post(
    "/balances/entitlements",
    summary="Post confirmed entitlement credits",
    status_code=201,
    dependencies=[CAN_MANAGE],
)
def post_entitlements(
    data: EntitlementPreviewRequest, actor: CurrentUserDep, db: DbSession
) -> EntitlementGenerateResult:
    return generate_entitlements(db, actor, data)


@router.get(
    "/balances/{employeeId}",
    summary="One employee's leave balance and transactions",
    dependencies=[CAN_VIEW],
    responses=NOT_FOUND_RESPONSE,
)
def get_leave_balance(
    employee_id: Annotated[int, Path(alias="employeeId", gt=0)],
    actor: CurrentUserDep,
    db: DbSession,
    year: Annotated[int, Query(ge=2000, le=2100)],
) -> BalanceDetail:
    return balance_detail(db, actor, employee_id, year)


@router.post(
    "/balances/{employeeId}/adjustments",
    summary="Adjust a leave balance and keep an audit record",
    dependencies=[CAN_MANAGE],
    responses=NOT_FOUND_RESPONSE,
)
def post_leave_adjustment(
    employee_id: Annotated[int, Path(alias="employeeId", gt=0)],
    data: BalanceAdjustment,
    actor: CurrentUserDep,
    db: DbSession,
) -> BalanceDetail:
    return adjust_balance(db, actor, employee_id, data)
