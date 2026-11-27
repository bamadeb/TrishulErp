"""TTPL leave arithmetic helpers used by entitlement and day-count rules."""

from datetime import date
from decimal import Decimal

from trishul_api.modules.hr.leave.calculation import (
    is_medical_emergency,
    opening_carry,
    pro_rata_annual,
)


def test_pro_rata_full_year_when_joined_before_year() -> None:
    credited = pro_rata_annual(
        Decimal("6.0"),
        joining=date(2024, 6, 1),
        year_start=date(2026, 1, 1),
        year_end=date(2026, 12, 31),
    )
    assert credited == Decimal("6.0")


def test_pro_rata_mid_year_joining() -> None:
    # Joined 1 July → 6 remaining months inclusive → 6 * 6/12 = 3.0
    credited = pro_rata_annual(
        Decimal("6.0"),
        joining=date(2026, 7, 1),
        year_start=date(2026, 1, 1),
        year_end=date(2026, 12, 31),
    )
    assert credited == Decimal("3.0")


def test_pro_rata_null_joining_is_full() -> None:
    credited = pro_rata_annual(
        Decimal("15.0"),
        joining=None,
        year_start=date(2026, 1, 1),
        year_end=date(2026, 12, 31),
    )
    assert credited == Decimal("15.0")


def test_opening_carry_caps_at_carry_forward_max_and_accumulation() -> None:
    assert opening_carry(
        Decimal("20.0"),
        carry_forward=True,
        carry_forward_max=Decimal("15.0"),
        max_accumulation=Decimal("30.0"),
    ) == Decimal("15.0")
    assert opening_carry(
        Decimal("40.0"),
        carry_forward=True,
        carry_forward_max=Decimal("15.0"),
        max_accumulation=Decimal("10.0"),
    ) == Decimal("10.0")
    assert opening_carry(Decimal("8.0"), carry_forward=False, carry_forward_max=Decimal("15.0"), max_accumulation=None) == Decimal(
        "0.0"
    )


def test_medical_emergency_reason_tokens() -> None:
    assert is_medical_emergency("Medical emergency — fever")
    assert is_medical_emergency("Sudden hospitalization")
    assert not is_medical_emergency("Family function")
    assert not is_medical_emergency(None)
