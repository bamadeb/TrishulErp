"""Company working-hours policy for Head Office and every branch.

One office day for regular, contractual and trainee employees:

- 9:30 AM to 5:30 PM
- lunch 1:30 PM to 2:00 PM, deducted only while the employee is punched in
- net expected time 7 hours 30 minutes
- 15 minutes of arrival grace on 3 days per employee per calendar month
- a later arrival, or a fourth grace day, is still Late on the attendance
  record and a separate half-day salary deduction
- official out-of-office time comes from an approved regularization or an
  app trip (departure and return), and counts as work
- rejected and pending punches are not attendance
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta

OFFICE_START = time(9, 30)
OFFICE_END = time(17, 30)
LUNCH_START = time(13, 30)
LUNCH_END = time(14, 0)
GRACE_MINUTES = 15
GRACE_DAYS_PER_MONTH = 3
NET_MINUTES = 7 * 60 + 30

ATTENDANCE_PUNCH_STATUS = "Present"


def punch_counts_for_attendance(status: str | None) -> bool:
    """Rejected and pending mobile punches are kept, but they are not attendance."""
    return (status or "") == ATTENDANCE_PUNCH_STATUS


@dataclass(frozen=True)
class Arrival:
    """Attendance status and the payroll deduction are separate."""

    attendance_status: str
    payroll_status: str
    uses_grace: bool
    late_minutes: int
    remarks: str


@dataclass(frozen=True)
class OfficialVisit:
    departed_at: datetime
    returned_at: datetime | None


def expected_net_minutes(
    start: time = OFFICE_START,
    end: time = OFFICE_END,
    lunch_start: time = LUNCH_START,
    lunch_end: time = LUNCH_END,
) -> int:
    day = date(2000, 1, 1)
    span = _minutes(datetime.combine(day, start), datetime.combine(day, end))
    lunch = _overlap(
        datetime.combine(day, start),
        datetime.combine(day, end),
        datetime.combine(day, lunch_start),
        datetime.combine(day, lunch_end),
    )
    return max(0, span - lunch)


def punch_intervals(punches: list[tuple[datetime, str]]) -> list[tuple[datetime, datetime]]:
    ordered = sorted(punches, key=lambda item: item[0])
    intervals: list[tuple[datetime, datetime]] = []
    open_in: datetime | None = None
    for at, kind in ordered:
        if kind == "IN":
            if open_in is None:
                open_in = at
        elif kind == "OUT" and open_in is not None:
            if at > open_in:
                intervals.append((open_in, at))
            open_in = None
    if not intervals and len(ordered) >= 2:
        intervals.append((ordered[0][0], ordered[-1][0]))
    return intervals


def net_worked_minutes(
    punches: list[tuple[datetime, str]],
    day: date,
    visits: list[OfficialVisit] | None = None,
) -> int:
    """IN/OUT time, plus official visits, minus lunch that falls inside a punch interval."""
    intervals = punch_intervals(punches)
    lunch_start = datetime.combine(day, LUNCH_START)
    lunch_end = datetime.combine(day, LUNCH_END)
    worked = 0
    for start, end in intervals:
        worked += _minutes(start, end) - _overlap(start, end, lunch_start, lunch_end)
    for visit in visits or []:
        if visit.returned_at is None or visit.returned_at <= visit.departed_at:
            continue
        credit = _minutes(visit.departed_at, visit.returned_at)
        for start, end in intervals:
            credit -= _overlap(visit.departed_at, visit.returned_at, start, end)
        worked += max(0, credit)
    return max(0, worked)


def grace_days_before(
    first_ins: list[tuple[date, datetime]],
    day: date,
) -> int:
    """How many earlier days this month used the 15-minute arrival grace."""
    used = 0
    for earlier, first_in in sorted(first_ins):
        if earlier >= day or earlier.year != day.year or earlier.month != day.month:
            continue
        if _uses_grace(first_in, earlier):
            used += 1
    return used


def classify_arrival(first_in: datetime, day: date, grace_used_before: int) -> Arrival:
    start = datetime.combine(day, OFFICE_START)
    deadline = start + timedelta(minutes=GRACE_MINUTES)
    if first_in <= start:
        return Arrival("Present", "Present", False, 0, "")
    if first_in <= deadline:
        late_by = _minutes(start, first_in)
        if grace_used_before < GRACE_DAYS_PER_MONTH:
            number = grace_used_before + 1
            return Arrival(
                "Present",
                "Present",
                True,
                late_by,
                f"Grace day {number} of {GRACE_DAYS_PER_MONTH} ({late_by} min).",
            )
        return Arrival(
            "Late",
            "Half day",
            False,
            late_by,
            f"Grace allowance of {GRACE_DAYS_PER_MONTH} days is used. Half-day salary deduction.",
        )
    late_by = _minutes(deadline, first_in)
    return Arrival(
        "Late",
        "Half day",
        False,
        late_by,
        f"Late by {late_by} min after the 15-minute grace. Half-day salary deduction.",
    )


def leaves_early(last_out: datetime | None, day: date, visits: list[OfficialVisit] | None = None) -> bool:
    if last_out is None:
        return False
    end = datetime.combine(day, OFFICE_END)
    effective = last_out
    for visit in visits or []:
        if visit.departed_at <= end and (visit.returned_at is None or visit.returned_at >= end):
            return False
        if visit.returned_at is not None and visit.returned_at > effective:
            effective = visit.returned_at
    return effective < end


def _uses_grace(first_in: datetime, day: date) -> bool:
    start = datetime.combine(day, OFFICE_START)
    deadline = start + timedelta(minutes=GRACE_MINUTES)
    return start < first_in <= deadline


def _minutes(start: datetime, end: datetime) -> int:
    return max(0, int((end - start).total_seconds() // 60))


def _overlap(a0: datetime, a1: datetime, b0: datetime, b1: datetime) -> int:
    start = max(a0, b0)
    end = min(a1, b1)
    if end <= start:
        return 0
    return _minutes(start, end)
