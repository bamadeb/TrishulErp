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
    if method == "FIXED" and benefit == "COMPANY" and getattr(line, "accrual_frequency", None) == "Yearly":
        sentences.append(f"Annual entitlement: {line.annual_entitlement} days (pro-rata in the joining year).")
    if line.carry_forward and line.max_accumulation is not None:
        sentences.append(f"Maximum accumulated balance {line.max_accumulation} days for adult employees.")
    if line.adolescent_max_accumulation is not None:
        sentences.append(f"Carry forward up to {line.adolescent_max_accumulation} days for employees under 18.")
    if line.exclude_boundary_holidays:
        sentences.append("Sundays and public holidays during leave are excluded from deduction.")
        sentences.append("Leave may be prefixed or suffixed to holidays or weekly offs.")
    else:
        if method == "FIXED" and getattr(line, "annual_entitlement", None):
            sentences.append("Intervening holidays and weekly offs during leave count as leave.")
            sentences.append("Leave cannot be prefixed or suffixed to holidays or weekly offs.")
    if line.document_required:
        sentences.append("A supporting document is required.")
    if basis == "STATUTORY_WEEKLY_REST":
        sentences.append(
            f"If the weekly holiday is denied, compensatory leave is due within {line.compensatory_expiry_months} "
            "calendar months of that weekly holiday."
        )
    elif basis == "COMPANY_COMP_OFF":
        expiry = line.compensatory_expiry_months
        when = f" Must be availed within {expiry} calendar months or it expires." if expiry else " HR sets the expiry."
        sentences.append(
            "Compensatory Off requires prior management authorization and HOD/Reporting Manager certification."
            + when
        )
    if getattr(line, "backdate_requires_authorization", False):
        sentences.append("Past dates require HR authorization.")
    limit = getattr(line, "max_backdate_days", None)
    if limit == 0:
        sentences.append("Past dates are not allowed, except medical emergency on the next working day.")
    elif isinstance(limit, int) and limit > 0:
        sentences.append(f"Past dates are allowed up to {limit} calendar days (medical emergency / next working day).")
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


def pro_rata_annual(
    entitlement: Decimal,
    *,
    joining: date | None,
    year_start: date,
    year_end: date,
) -> Decimal:
    """Credit a fixed annual entitlement for the portion of the policy year remaining after joining.

    Joining on or before the year start earns the full entitlement. Joining after the year end earns none.
    Mid-year joining uses remaining calendar months inclusive of the joining month, rounded to 0.1.
    """
    if entitlement <= _ZERO:
        return _ZERO
    if joining is None or joining <= year_start:
        return entitlement.quantize(_STEP)
    if joining > year_end:
        return _ZERO
    months = (year_end.year - joining.year) * 12 + (year_end.month - joining.month) + 1
    if months <= 0:
        return _ZERO
    return (entitlement * Decimal(months) / Decimal(12)).quantize(_STEP)


def opening_carry(
    prior_closing: Decimal,
    *,
    carry_forward: bool,
    carry_forward_max: Decimal | None,
    max_accumulation: Decimal | None,
) -> Decimal:
    """Opening balance for a new policy year after applying carry-forward and accumulation caps."""
    if not carry_forward or prior_closing <= _ZERO:
        return _ZERO
    carried = prior_closing
    if carry_forward_max is not None:
        carried = min(carried, carry_forward_max)
    if max_accumulation is not None:
        carried = min(carried, max_accumulation)
    return carried.quantize(_STEP)


def is_medical_emergency(reason: str | None) -> bool:
    """True when the leave reason indicates a medical emergency (next-working-day application)."""
    text = (reason or "").strip().lower()
    if not text:
        return False
    tokens = ("medical", "emergency", "hospitalisation", "hospitalization", "illness", "accident")
    return any(token in text for token in tokens)
