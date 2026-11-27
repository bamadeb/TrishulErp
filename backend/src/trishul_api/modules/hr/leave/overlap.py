"""Centralized duplicate and overlapping leave checks for Pending and Approved requests.

Rejected and Cancelled (withdrawn) requests do not block reapplication. Half-day occupancy
is capped at one full day per calendar date without requiring a stored half-day part.
"""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal
from typing import Protocol

_ZERO = Decimal("0.0")
_HALF = Decimal("0.5")
_FULL = Decimal("1.0")
_ACTIVE = frozenset({"Pending", "Approved"})


class LeaveSpan(Protocol):
    id: int
    leave_type_id: int
    from_date: date
    to_date: date
    is_half_day: bool
    status: str
    days: Decimal


def day_weight(is_half_day: bool) -> Decimal:
    return _HALF if is_half_day else _FULL


def covers(row: LeaveSpan, day: date) -> bool:
    return row.from_date <= day <= row.to_date


def occupancy_on(rows: list[LeaveSpan], day: date, *, skip_id: int | None = None) -> Decimal:
    total = _ZERO
    for row in rows:
        if row.id == skip_id or not covers(row, day):
            continue
        total += day_weight(row.is_half_day)
    return total


def format_display_id(request_id: int) -> str:
    return f"LV-{request_id:04d}"


def format_day(day: date) -> str:
    return day.strftime("%d-%b-%Y")


def format_range(start: date, end: date) -> str:
    if start == end:
        return format_day(start)
    return f"{format_day(start)} to {format_day(end)}"


def conflict_message(
    *,
    leave_type_id: int,
    from_date: date,
    to_date: date,
    is_half_day: bool,
    existing: list[LeaveSpan],
    skip_id: int | None = None,
    type_names: dict[int, str] | None = None,
) -> str | None:
    """Return a clear validation message when the proposed leave conflicts, else None.

    Duplicate: same leave type and exact same from/to (and half-day flag) as an active request.
    Overlap: any calendar day where existing Pending/Approved occupancy plus the proposal
    would exceed one full day.
    """
    active = [row for row in existing if row.status in _ACTIVE and row.id != skip_id]
    names = type_names or {}

    # Exact full-day duplicates only. Complementary half-days share from/to/is_half_day and
    # are governed by per-day occupancy below (max one full day).
    if not is_half_day:
        for row in active:
            if (
                row.leave_type_id == leave_type_id
                and row.from_date == from_date
                and row.to_date == to_date
                and not row.is_half_day
            ):
                label = names.get(row.leave_type_id, "leave")
                return (
                    f"Duplicate submission for {format_range(from_date, to_date)} "
                    f"conflicts with {row.status.lower()} request {format_display_id(row.id)} ({label})."
                )

    proposed = day_weight(is_half_day)
    cursor = from_date
    conflict_days: list[date] = []
    offenders: list[LeaveSpan] = []
    while cursor <= to_date:
        used = occupancy_on(active, cursor, skip_id=skip_id)
        if used + proposed > _FULL:
            conflict_days.append(cursor)
            for row in active:
                if covers(row, cursor) and row not in offenders:
                    offenders.append(row)
        cursor += timedelta(days=1)

    if not conflict_days:
        return None

    when = format_range(conflict_days[0], conflict_days[-1]) if conflict_days else format_range(from_date, to_date)
    if len(offenders) == 1:
        row = offenders[0]
        label = names.get(row.leave_type_id, "leave")
        return (
            f"Overlapping leave on {when} conflicts with {row.status.lower()} request "
            f"{format_display_id(row.id)} ({label}, {format_range(row.from_date, row.to_date)})."
        )
    parts = [
        f"{format_display_id(row.id)} ({names.get(row.leave_type_id, 'leave')}, {row.status.lower()})"
        for row in offenders[:3]
    ]
    extra = "" if len(offenders) <= 3 else f" and {len(offenders) - 3} more"
    return f"Overlapping leave on {when} conflicts with {', '.join(parts)}{extra}."
