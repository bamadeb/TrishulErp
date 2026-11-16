"""Statutory entitlement arithmetic. Attendance classification stays outside this module."""

import calendar
from datetime import date, timedelta
from decimal import Decimal

_ZERO = Decimal("0.0")
_STEP = Decimal("0.1")


def add_calendar_months(day: date, months: int) -> date:
    """The same day three calendar months later, clamped to the last day of that month."""
    index = day.month - 1 + months
    year = day.year + index // 12
    month = index % 12 + 1
    return date(year, month, min(day.day, calendar.monthrange(year, month)[1]))


def joining_threshold(joining: date | None, year: int, full_year_days: int) -> int:
    """240 days, or two-thirds of the days from a mid-year joining date through 31 December.

    Two-thirds is rounded up. A joining date on or before 1 January uses the full-year minimum.
    """
    opening = date(year, 1, 1)
    if joining is None or joining <= opening or joining.year != year:
        return full_year_days
    remainder = (date(year, 12, 31) - joining).days + 1
    return (remainder * 2 + 2) // 3


def earned_leave_days(
    *,
    eligibility_days: Decimal,
    days_worked: Decimal,
    credit_days: Decimal,
    per_days: int,
    minimum_qualifying_days: int,
    joining: date | None,
    attendance_year: int,
    joining_rule: str,
) -> Decimal:
    """Credit from days actually worked. The eligibility total may also include deemed-work days."""
    minimum = minimum_qualifying_days
    if joining_rule == "TWO_THIRDS_REMAINDER":
        minimum = joining_threshold(joining, attendance_year, minimum_qualifying_days)
    if eligibility_days < minimum or per_days <= 0:
        return _ZERO
    units = (days_worked // Decimal(per_days)).to_integral_value()
    return (units * credit_days).quantize(_STEP)


def rule_summary(line: object) -> list[str]:
    """Short sentences for the entitlement editor. `line` is a policy line write or stored row."""
    method = getattr(line, "calculation_method", "FIXED")
    benefit = getattr(line, "benefit_class", "STANDARD")
    basis = getattr(line, "compensatory_basis", "NONE")
    sentences: list[str] = []
    if benefit == "COMPANY":
        sentences.append("Company benefit. This is not an Odisha statutory entitlement.")
    elif benefit == "STATUTORY":
        sentences.append("Statutory entitlement for a covered Odisha private establishment.")
    if method == "FORMULA":
        sentences.append(
            f"Eligible when at least {line.minimum_qualifying_days} qualifying days are counted in the preceding year."
        )
        sentences.append(
            f"Entitlement: {line.credit_days} day for every {line.qualifying_days_per_credit} days actually worked."
        )
        sentences.append("Deemed-work days can count toward eligibility and do not earn extra leave.")
        if line.joining_year_rule == "TWO_THIRDS_REMAINDER":
            sentences.append("Joining after 1 January uses two-thirds of the remaining calendar year.")
    elif method == "ELIGIBILITY":
        sentences.append(f"Maximum {line.annual_entitlement} days in the policy year.")
        if line.minimum_service_months:
            sentences.append(
                f"Available after {line.minimum_service_months} months of continuous employment from the joining date."
            )
    if line.carry_forward and line.max_accumulation is not None:
        sentences.append(f"Carry forward up to {line.max_accumulation} days for adult employees.")
    if line.adolescent_max_accumulation is not None:
        sentences.append(f"Carry forward up to {line.adolescent_max_accumulation} days for employees under 18.")
    if line.exclude_boundary_holidays:
        sentences.append("Holidays during or at either end of leave are not counted.")
    if line.document_required:
        sentences.append("A supporting document is required.")
    if basis == "STATUTORY_WEEKLY_REST":
        sentences.append(
            f"If the weekly holiday is denied, compensatory leave is due within {line.compensatory_expiry_months} "
            "calendar months of that weekly holiday."
        )
    elif basis == "COMPANY_COMP_OFF":
        expiry = line.compensatory_expiry_months
        when = f" HR expiry is {expiry} calendar months." if expiry else " HR sets the expiry."
        sentences.append("Company Comp-Off is separate from statutory weekly-rest compensation." + when)
    if getattr(line, "backdate_requires_authorization", False):
        sentences.append("Past dates require HR authorization.")
    limit = getattr(line, "max_backdate_days", None)
    if limit == 0:
        sentences.append("Past dates are not allowed.")
    elif isinstance(limit, int) and limit > 0:
        sentences.append(f"Past dates are allowed up to {limit} calendar days.")
    return sentences


def backdate_rejection(
    *,
    today: date,
    start: date,
    end: date,
    max_backdate_days: int | None,
    requires_authorization: bool,
    hr_authorized: bool,
) -> str | None:
    """A message when the dates are earlier than the policy line allows. None means the dates are allowed."""
    if requires_authorization and hr_authorized:
        return None
    if requires_authorization and (start < today or end < today):
        return "Past dates for this leave type require HR authorization."
    if max_backdate_days is None:
        return None
    earliest = today - timedelta(days=max_backdate_days)
    if start >= earliest and end >= earliest:
        return None
    if max_backdate_days == 0:
        return "This leave type cannot start before today."
    label = earliest.strftime("%d-%b-%Y")
    return f"This leave type can start at most {max_backdate_days} calendar days before today ({label})."


def carry_forward_limit(
    *,
    adult_limit: Decimal | None,
    adolescent_limit: Decimal | None,
    age_years: int | None,
) -> Decimal | None:
    """Adults use the adult limit. An unknown age uses the adult limit. Under 18 uses the adolescent limit."""
    if age_years is not None and age_years < 18 and adolescent_limit is not None:
        return adolescent_limit
    return adult_limit
