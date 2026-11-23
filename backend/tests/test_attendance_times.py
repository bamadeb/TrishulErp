"""Daily attendance punch times are Indian clock times and must reach the browser as +05:30, not as UTC."""

from datetime import UTC, datetime

from trishul_api.modules.hr.attendance.schemas import (
    AttendanceExceptionRowOut,
    AttendancePunchOut,
    DailyAttendanceRowOut,
    RegularizationRowOut,
)


def test_punch_times_are_sent_as_indian_time() -> None:
    punch = AttendancePunchOut(kind="IN", at=datetime(2026, 11, 23, 16, 39, 40), device="Mobile app (face)")
    assert punch.model_dump(mode="json", by_alias=True)["at"] == "2026-11-23T16:39:40+05:30"


def test_daily_row_in_and_out_times_keep_their_clock_time() -> None:
    data = DailyAttendanceRowOut.model_validate(
        {
            "id": 1,
            "employee_id": 5,
            "employee_code": "EMP0005",
            "employee_name": "Padmalochan",
            "department": "Service",
            "location": "Bhadrak",
            "shift": "General",
            "employee_type": "Permanent",
            "reporting_manager": "",
            "first_in": datetime(2026, 11, 23, 9, 5),
            "last_out": datetime(2026, 11, 23, 18, 2),
            "status": "Present",
        }
    ).model_dump(mode="json", by_alias=True)
    assert data["firstIn"] == "2026-11-23T09:05:00+05:30"
    assert data["lastOut"] == "2026-11-23T18:02:00+05:30"
    # The same instant as the UTC the punch was recorded in (09:05 IST = 03:35 UTC).
    assert datetime.fromisoformat(data["firstIn"]).astimezone(UTC).hour == 3


def test_exception_and_regularization_times_too_but_submitted_on_stays_utc() -> None:
    def converter(model: type, field: str) -> str:
        info = model.model_fields[field]  # type: ignore[attr-defined]
        return f"{info.annotation} {info.metadata}"

    for model, field in [
        (AttendanceExceptionRowOut, "first_in"),
        (AttendanceExceptionRowOut, "last_out"),
        (RegularizationRowOut, "original_in"),
        (RegularizationRowOut, "original_out"),
    ]:
        assert "_as_india" in converter(model, field), f"{model.__name__}.{field}"
    # Created in the database with SYSUTCDATETIME: a real UTC time.
    assert "_as_utc" in converter(RegularizationRowOut, "submitted_on")
