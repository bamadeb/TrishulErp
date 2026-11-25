"""Unit tests for Daily Attendance status calculation helpers."""

from datetime import date, datetime, time

from trishul_api.modules.hr.attendance.repository import (
    EmployeeDaySource,
    PunchSource,
    ShiftAssignment,
    off_weekdays,
)
from trishul_api.modules.hr.attendance.service import AttendanceService


def _employee() -> EmployeeDaySource:
    return EmployeeDaySource(
        id=1,
        employee_code="EMP0001",
        first_name="Aswani",
        last_name="Sahu",
        employee_type="Permanent",
        department_name="Service",
        branch_id=1,
        branch_name="Bhadrak",
        branch_state_id=None,
        reporting_manager_name="Lead",
    )


def _shift() -> ShiftAssignment:
    return ShiftAssignment(
        shift_id=None,
        shift_name="General",
        start_time=time(9, 0),
        end_time=time(18, 0),
        grace_minutes=10,
        weekly_off_days="SUN",
    )


def test_off_weekdays_default_sunday():
    assert off_weekdays(None) == {6}
    assert off_weekdays("SAT,SUN") == {5, 6}


def test_present_and_late_from_punches():
    service = AttendanceService.__new__(AttendanceService)
    day = date(2026, 11, 19)
    shift = _shift()
    present = service._from_punches(
        day,
        shift,
        [
            PunchSource(1, datetime(2026, 11, 19, 9, 2), "IN", "Gate"),
            PunchSource(1, datetime(2026, 11, 19, 18, 10), "OUT", "Gate"),
        ],
    )
    assert present[4] == "Present"
    assert present[2] is False

    late = service._from_punches(
        day,
        shift,
        [
            PunchSource(1, datetime(2026, 11, 19, 9, 25), "IN", "Gate"),
            PunchSource(1, datetime(2026, 11, 19, 18, 5), "OUT", "Gate"),
        ],
    )
    assert late[4] == "Late"
    assert late[2] is True


def test_missing_punch_and_absent():
    service = AttendanceService.__new__(AttendanceService)
    day = date(2026, 11, 19)
    shift = _shift()
    missing = service._from_punches(
        day,
        shift,
        [PunchSource(1, datetime(2026, 11, 19, 9, 1), "IN", "Gate")],
    )
    assert missing[4] == "Missing Punch"

    absent = service._from_punches(day, shift, [])
    assert absent[4] == "Absent"


def test_weekly_off_without_punches():
    service = AttendanceService.__new__(AttendanceService)
    service._repo = type("R", (), {"holiday_applies": lambda self, h, b, s: True})()
    sunday = date(2026, 11, 15)  # Sunday
    first_in, last_out, late, hours, status, remarks = service._evaluate(
        day=sunday,
        employee=_employee(),
        shift=_shift(),
        holidays=[],
        leave=None,
        punches=[],
    )
    assert status == "Off Day"
    assert remarks == "Weekly off"
    assert first_in is None and last_out is None and late is False and hours is None


def test_persist_status_policy_alignment():
    """TTPL: late beyond grace → Half day; Missing Punch not silently Absent."""
    from decimal import Decimal

    from trishul_api.modules.hr.attendance.service import _persist_status

    assert _persist_status("Missing Punch", None) is None
    assert _persist_status("Late", None) == "Half day"
    assert _persist_status("Present", None) == "Present"
    assert _persist_status("Absent", None) == "Absent"
    assert (
        _persist_status("Present", None, worked_hours=Decimal("3"), half_day_hours=4.0)
        == "Half day"
    )


def test_muster_status_codes_and_hours_parse():
    from trishul_api.modules.hr.attendance.service import _status_to_muster_code

    assert _status_to_muster_code("Present") == "P"
    assert _status_to_muster_code("Late") == "L"
    assert _status_to_muster_code("Missing Punch") == "P"
    assert _status_to_muster_code("Absent") == "A"
    assert _status_to_muster_code("On Leave") == "PL"
    assert _status_to_muster_code("Holiday") == "H"
    assert _status_to_muster_code("Off Day") == "OFF"

    service = AttendanceService.__new__(AttendanceService)
    assert service._parse_hours_minutes("7h 15m") == 7 * 60 + 15
    assert service._parse_hours_minutes(None) == 0


def test_exception_detection_absent_late_missing():
    service = AttendanceService.__new__(AttendanceService)
    service._repo = type("R", (), {"holiday_applies": lambda self, h, b, s: True})()
    day = date(2026, 11, 19)  # Wednesday
    shift = _shift()

    absent = service._detect_exception(
        day=day,
        employee=_employee(),
        shift=shift,
        holidays=[],
        leave=None,
        punches=[],
    )
    assert absent is not None and absent[0] == "Absent"

    missing = service._detect_exception(
        day=day,
        employee=_employee(),
        shift=shift,
        holidays=[],
        leave=None,
        punches=[PunchSource(1, datetime(2026, 11, 19, 9, 1), "IN", "Gate")],
    )
    assert missing is not None and missing[0] == "Missing Punch"

    late = service._detect_exception(
        day=day,
        employee=_employee(),
        shift=shift,
        holidays=[],
        leave=None,
        punches=[
            PunchSource(1, datetime(2026, 11, 19, 9, 40), "IN", "Gate"),
            PunchSource(1, datetime(2026, 11, 19, 18, 5), "OUT", "Gate"),
        ],
    )
    assert late is not None and late[0] == "Late Arrival"

    early = service._detect_exception(
        day=day,
        employee=_employee(),
        shift=shift,
        holidays=[],
        leave=None,
        punches=[
            PunchSource(1, datetime(2026, 11, 19, 9, 2), "IN", "Gate"),
            PunchSource(1, datetime(2026, 11, 19, 15, 0), "OUT", "Gate"),
        ],
    )
    assert early is not None and early[0] == "Early Exit"
