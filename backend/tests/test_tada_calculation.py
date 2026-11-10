"""Distance priority and payable TA, without a database."""

from decimal import Decimal

from trishul_api.modules.hr.tada.calculation import (
    applicable_distance_km,
    apply_decision,
    approval_and_settlement,
    is_payable,
    money_for_km,
    rate_for_vehicle,
    ta_amount,
)


def test_adjusted_distance_wins_only_when_flagged() -> None:
    distance = applicable_distance_km(
        is_distance_adjusted=True,
        adjusted_distance_km=Decimal("12.5"),
        map_distance_km=Decimal("10"),
        gps_distance_km=Decimal("9"),
    )
    assert distance == Decimal("12.5")


def test_map_distance_is_used_when_the_adjustment_flag_is_off() -> None:
    distance = applicable_distance_km(
        is_distance_adjusted=False,
        adjusted_distance_km=Decimal("12.5"),
        map_distance_km=Decimal("10"),
        gps_distance_km=Decimal("9"),
    )
    assert distance == Decimal("10")


def test_gps_distance_is_the_last_resort() -> None:
    distance = applicable_distance_km(
        is_distance_adjusted=False,
        adjusted_distance_km=None,
        map_distance_km=None,
        gps_distance_km=Decimal("9"),
    )
    assert distance == Decimal("9")


def test_flagged_adjustment_without_a_value_falls_through() -> None:
    distance = applicable_distance_km(
        is_distance_adjusted=True,
        adjusted_distance_km=None,
        map_distance_km=Decimal("8"),
        gps_distance_km=Decimal("7"),
    )
    assert distance == Decimal("8")


def test_only_finished_trips_are_payable() -> None:
    assert is_payable("Completed")
    assert is_payable("Auto closed")
    assert not is_payable("In progress")


def test_ta_uses_the_configured_rate_and_skips_other_vehicles() -> None:
    bike = rate_for_vehicle("Own bike", bike_rate=Decimal("2.50"), car_rate=Decimal("5.50"))
    car = rate_for_vehicle("Own car", bike_rate=Decimal("2.50"), car_rate=Decimal("5.50"))
    company = rate_for_vehicle("Company vehicle", bike_rate=Decimal("2.50"), car_rate=Decimal("5.50"))
    assert ta_amount(Decimal("10"), bike) == Decimal("25.00")
    assert ta_amount(Decimal("10"), car) == Decimal("55.00")
    assert company is None
    assert ta_amount(Decimal("10"), None) is None
    assert ta_amount(None, bike) is None


def test_employee_money_uses_bike_and_car_kilometres_only() -> None:
    bike, car, total = money_for_km(
        Decimal("10"), Decimal("4"), bike_rate=Decimal("2.50"), car_rate=Decimal("5.50")
    )
    assert bike == Decimal("25.00")
    assert car == Decimal("22.00")
    assert total == Decimal("47.00")


def test_approval_and_settlement_stay_separate() -> None:
    assert approval_and_settlement(None) == ("Pending", "Open")
    assert approval_and_settlement("Approved") == ("Approved", "Open")
    assert approval_and_settlement("Rejected") == ("Rejected", "Open")
    assert approval_and_settlement("Sent") == ("Approved", "Sent")
    assert approval_and_settlement("Paid") == ("Approved", "Paid")


def test_only_pending_rows_can_be_approved_and_only_approved_rows_can_be_sent() -> None:
    assert apply_decision("Pending", "Approved") == "Approved"
    assert apply_decision("Pending", "Rejected") == "Rejected"
    assert apply_decision("Approved", "Sent") == "Sent"
    assert apply_decision("Approved", "Rejected") is None
    assert apply_decision("Rejected", "Approved") is None
    assert apply_decision("Sent", "Rejected") is None
    assert apply_decision("Pending", "Sent") is None
    assert apply_decision("Approved", "Paid") == "Paid"
    assert apply_decision("Sent", "Paid") == "Paid"
    assert apply_decision("Pending", "Paid") is None
    assert apply_decision("Paid", "Sent") is None
