"""Company working-hours policy: 9:30–5:30, lunch, grace, and official visits."""

from datetime import date, datetime

from trishul_api.modules.hr.attendance.policy import (
    NET_MINUTES,
    OfficialVisit,
    classify_arrival,
    expected_net_minutes,
    grace_days_before,
    leaves_early,
    net_worked_minutes,
    punch_counts_for_attendance,
)

DAY = date(2026, 11, 25)


def at(hour: int, minute: int, day: date = DAY) -> datetime:
    return datetime(day.year, day.month, day.day, hour, minute)


def test_on_time_arrival_is_present_with_no_grace_and_no_deduction() -> None:
    result = classify_arrival(at(9, 30), DAY, grace_used_before=0)
    assert result.attendance_status == "Present"
    assert result.payroll_status == "Present"
    assert result.uses_grace is False

    earlier = classify_arrival(at(9, 10), DAY, grace_used_before=2)
    assert earlier.attendance_status == "Present"
    assert earlier.uses_grace is False


def test_grace_is_tracked_for_the_first_three_days_of_the_month() -> None:
    firsts = [
        (date(2026, 11, 2), datetime(2026, 11, 2, 9, 40)),
        (date(2026, 11, 3), datetime(2026, 11, 3, 9, 45)),
        (date(2026, 11, 4), datetime(2026, 11, 4, 9, 20)),
    ]
    assert grace_days_before(firsts, date(2026, 11, 5)) == 2

    within = classify_arrival(at(9, 44), DAY, grace_used_before=2)
    assert within.attendance_status == "Present"
    assert within.payroll_status == "Present"
    assert within.uses_grace is True
    assert "Grace day 3 of 3" in within.remarks


def test_fourth_late_day_stays_late_and_deducts_a_half_day() -> None:
    result = classify_arrival(at(9, 40), DAY, grace_used_before=3)
    assert result.attendance_status == "Late"
    assert result.payroll_status == "Half day"
    assert result.uses_grace is False
    assert "Half-day salary deduction" in result.remarks


def test_arrival_after_the_fifteen_minute_grace_deducts_immediately() -> None:
    result = classify_arrival(at(9, 50), DAY, grace_used_before=0)
    assert result.attendance_status == "Late"
    assert result.payroll_status == "Half day"
    assert result.late_minutes == 5


def test_lunch_is_deducted_from_a_full_office_day() -> None:
    assert expected_net_minutes() == NET_MINUTES == 450
    punches = [("IN", at(9, 30)), ("OUT", at(17, 30))]
    typed = [(when, kind) for kind, when in punches]
    assert net_worked_minutes(typed, DAY) == 450


def test_lunch_is_not_deducted_twice_when_the_employee_is_already_out() -> None:
    typed = [(at(9, 30), "IN"), (at(13, 0), "OUT"), (at(14, 30), "IN"), (at(17, 30), "OUT")]
    # 3h 30m + 3h, lunch falls in the gap.
    assert net_worked_minutes(typed, DAY) == 6 * 60 + 30


def test_early_exit_before_five_thirty() -> None:
    assert leaves_early(at(17, 0), DAY) is True
    assert leaves_early(at(17, 30), DAY) is False


def test_missing_out_is_not_a_completed_day() -> None:
    typed = [(at(9, 30), "IN")]
    assert net_worked_minutes(typed, DAY) == 0


def test_official_visit_counts_as_work_and_is_not_an_early_exit() -> None:
    typed = [(at(9, 30), "IN"), (at(11, 0), "OUT"), (at(16, 0), "IN"), (at(17, 30), "OUT")]
    visit = OfficialVisit(departed_at=at(11, 0), returned_at=at(16, 0))
    without = net_worked_minutes(typed, DAY)
    with_visit = net_worked_minutes(typed, DAY, [visit])
    assert with_visit - without == 5 * 60
    assert leaves_early(at(16, 0), DAY, [OfficialVisit(at(16, 0), at(17, 30))]) is False


def test_rejected_and_pending_punches_are_not_attendance() -> None:
    assert punch_counts_for_attendance("Present") is True
    assert punch_counts_for_attendance("Rejected") is False
    assert punch_counts_for_attendance("Pending") is False
    assert punch_counts_for_attendance(None) is False
