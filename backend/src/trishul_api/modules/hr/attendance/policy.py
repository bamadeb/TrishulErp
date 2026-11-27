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
from datetime import date, datetime, time, timedelta, timezone

IST = timezone(timedelta(hours=5, minutes=30))
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


def ist_now() -> datetime:
    """Indian clock time without a timezone, matching stored punch and shift times."""
    return datetime.now(IST).replace(tzinfo=None)


def shift_bounds(day: date, start: time, end: time) -> tuple[datetime, datetime]:
    """Shift window. An end at or before the start finishes on the next day."""
    start_at = datetime.combine(day, start)
    end_at = datetime.combine(day, end)
    if end <= start:
        end_at += timedelta(days=1)
    return start_at, end_at


def punches_for_shift_day(punches: list, day: date, start: time, end: time) -> list:
    """Punches that belong to this shift.

    A day shift keeps punches on that calendar date. An overnight shift also
    keeps the punches after midnight up to the end of the shift.
    """
    start_at, end_at = shift_bounds(day, start, end)
    lo = start_at - timedelta(hours=3)
    hi = end_at + timedelta(hours=2)
    return [punch for punch in punches if lo <= _punched_at(punch) <= hi]


def _punched_at(punch) -> datetime:
    if isinstance(punch, datetime):
        return punch
    return punch[0] if isinstance(punch, tuple) else punch.punched_at


def expected_net_minutes(
    start: time = OFFICE_START,
    end: time = OFFICE_END,
    lunch_start: time = LUNCH_START,
    lunch_end: time = LUNCH_END,
) -> int:
    day = date(2000, 1, 1)
    start_at, end_at = shift_bounds(day, start, end)
    lunch = _overlap(
        start_at,
        end_at,
        datetime.combine(day, lunch_start),
        datetime.combine(day, lunch_end),
    )
    return max(0, _minutes(start_at, end_at) - lunch)


def punch_intervals(punches: list[tuple[datetime, str]]) -> list[tuple[datetime, datetime]]:
    intervals, _open_in = punch_sessions(punches)
    if not intervals and len(punches) >= 2:
        ordered = sorted(punches, key=lambda item: item[0])
        intervals.append((ordered[0][0], ordered[-1][0]))
    return intervals


def punch_sessions(
    punches: list[tuple[datetime, str]],
) -> tuple[list[tuple[datetime, datetime]], datetime | None]:
    """Closed IN→OUT pairs and the unmatched open IN (if the employee is currently punched in).

    Breaks between an OUT and the next IN are not counted. Duplicate INs before an OUT keep the first.
    """
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
    return intervals, open_in


def _clock_minutes(start: datetime, end: datetime) -> int:
    """Minutes between displayed punch clocks (seconds dropped so 09:36→11:57 = 141)."""
    a = start.replace(second=0, microsecond=0)
    b = end.replace(second=0, microsecond=0)
    return max(0, int((b - a).total_seconds() // 60))


def session_worked_minutes(
    punches: list[tuple[datetime, str]],
    *,
    now: datetime | None = None,
) -> tuple[int, list[int], datetime | None]:
    """Wall-clock minutes for each closed session, plus live elapsed when currently IN.

    Returns (total_minutes, per_session_minutes including open segment, open_in_at).
    Lunch is not deducted here — Daily Attendance / Punch Logs show actual punched time.
    """
    intervals, open_in = punch_sessions(punches)
    parts = [_clock_minutes(start, end) for start, end in intervals]
    if open_in is not None and now is not None and now > open_in:
        parts.append(_clock_minutes(open_in, now))
    return sum(parts), parts, open_in


def shift_gross_minutes(start: time = OFFICE_START, end: time = OFFICE_END) -> int:
    """Full shift length (start→end), used as Required Hours on the daily board."""
    day = date(2000, 1, 1)
    start_at, end_at = shift_bounds(day, start, end)
    return _minutes(start_at, end_at)


def net_worked_minutes(
    punches: list[tuple[datetime, str]],
    day: date,
    visits: list[OfficialVisit] | None = None,
    *,
    shift_start: time = OFFICE_START,
    shift_end: time = OFFICE_END,
) -> int:
    """IN/OUT time, plus official visits, minus lunch that falls inside a punch interval."""
    intervals = punch_intervals(punches)
    lunch_start = datetime.combine(day, LUNCH_START)
    lunch_end = datetime.combine(day, LUNCH_END)
    window_start, window_end = shift_bounds(day, shift_start, shift_end)
    lunch_in_shift = _overlap(window_start, window_end, lunch_start, lunch_end) > 0
    worked = 0
    for start, end in intervals:
        lunch_cut = _overlap(start, end, lunch_start, lunch_end) if lunch_in_shift else 0
        worked += _minutes(start, end) - lunch_cut
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
    *,
    shift_start: time = OFFICE_START,
    grace_minutes: int = GRACE_MINUTES,
    shift_starts: dict[date, time] | None = None,
) -> int:
    """How many earlier days this month used the arrival grace for that day's shift."""
    used = 0
    for earlier, first_in in sorted(first_ins):
        if earlier >= day or earlier.year != day.year or earlier.month != day.month:
            continue
        start = (shift_starts or {}).get(earlier, shift_start)
        if _uses_grace(first_in, earlier, start, grace_minutes):
            used += 1
    return used


def classify_arrival(
    first_in: datetime,
    day: date,
    grace_used_before: int,
    *,
    shift_start: time = OFFICE_START,
    grace_minutes: int = GRACE_MINUTES,
    grace_days: int = GRACE_DAYS_PER_MONTH,
) -> Arrival:
    start = datetime.combine(day, shift_start)
    deadline = start + timedelta(minutes=grace_minutes)
    if first_in <= start:
        return Arrival("Present", "Present", False, 0, "")
    if first_in <= deadline:
        late_by = _minutes(start, first_in)
        if grace_used_before < grace_days:
            number = grace_used_before + 1
            return Arrival(
                "Present",
                "Present",
                True,
                late_by,
                f"Grace day {number} of {grace_days} ({late_by} min).",
            )
        return Arrival(
            "Late",
            "Half day",
            False,
            late_by,
            f"Grace allowance of {grace_days} days is used. Half-day salary deduction.",
        )
    late_by = _minutes(deadline, first_in)
    return Arrival(
        "Late",
        "Half day",
        False,
        late_by,
        f"Late by {late_by} min after the {grace_minutes}-minute grace. Half-day salary deduction.",
    )


def early_exit_minutes(
    last_out: datetime | None,
    day: date,
    visits: list[OfficialVisit] | None = None,
    *,
    shift_start: time = OFFICE_START,
    shift_end: time = OFFICE_END,
    early_grace_minutes: int = 0,
) -> int:
    """Minutes left before the shift end, after early-exit grace and official visits.

    ``0`` means the employee did not leave early. The same window as ``leaves_early``.
    """
    if last_out is None:
        return 0
    _, end = shift_bounds(day, shift_start, shift_end)
    deadline = end - timedelta(minutes=max(0, early_grace_minutes))
    effective = last_out
    for visit in visits or []:
        if visit.departed_at <= end and (visit.returned_at is None or visit.returned_at >= end):
            return 0
        if visit.returned_at is not None and visit.returned_at > effective:
            effective = visit.returned_at
    if effective >= deadline:
        return 0
    return _minutes(effective, deadline)


def leaves_early(
    last_out: datetime | None,
    day: date,
    visits: list[OfficialVisit] | None = None,
    *,
    shift_start: time = OFFICE_START,
    shift_end: time = OFFICE_END,
    early_grace_minutes: int = 0,
) -> bool:
    return (
        early_exit_minutes(
            last_out,
            day,
            visits,
            shift_start=shift_start,
            shift_end=shift_end,
            early_grace_minutes=early_grace_minutes,
        )
        > 0
    )


def _uses_grace(first_in: datetime, day: date, shift_start: time = OFFICE_START, grace_minutes: int = GRACE_MINUTES) -> bool:
    start = datetime.combine(day, shift_start)
    deadline = start + timedelta(minutes=grace_minutes)
    return start < first_in <= deadline


def _minutes(start: datetime, end: datetime) -> int:
    return max(0, int((end - start).total_seconds() // 60))


def _overlap(a0: datetime, a1: datetime, b0: datetime, b1: datetime) -> int:
    start = max(a0, b0)
    end = min(a1, b1)
    if end <= start:
        return 0
    return _minutes(start, end)
