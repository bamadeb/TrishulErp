"""Daily Attendance API routes."""

from typing import Annotated

from fastapi import APIRouter, Depends, Query

from trishul_api.auth import DbSession, require_permission
from trishul_api.modules.hr.attendance.schemas import DailyAttendancePageOut, DailyAttendanceQuery
from trishul_api.modules.hr.attendance.service import AttendanceService

router = APIRouter(prefix="/hr/attendance", tags=["attendance"])

# Match the Daily Attendance screen route guard (employee view/manage).
CAN_VIEW = Depends(require_permission("core.employee.view", "core.employee.manage"))


def get_attendance_service(db: DbSession) -> AttendanceService:
    return AttendanceService(db)


Attendance = Annotated[AttendanceService, Depends(get_attendance_service)]


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
