"""Distance and TA rules for service-engineer trips. Pure functions: no database access."""

from decimal import Decimal
from typing import Literal

# Trip codes now live in trk master tables. These are the values the TA rules understand.
TrkTripStatus = Literal["In progress", "Completed", "Auto closed"]
TrkTripVehicleType = Literal["Own bike", "Own car", "Company vehicle", "Public transport"]

PAYABLE_STATUSES: frozenset[TrkTripStatus] = frozenset({"Completed", "Auto closed"})
"""Finished trips. trk.trip has no approval status, so these are the payable ones."""

BIKE_VEHICLE: TrkTripVehicleType = "Own bike"
CAR_VEHICLE: TrkTripVehicleType = "Own car"
DEFAULT_BIKE_RATE = Decimal("2.50")
"""Spec default used only when HR has not saved a bike rate. The car rate is never defaulted."""

MONEY = Decimal("0.01")
DISTANCE = Decimal("0.001")


def applicable_distance_km(
    *,
    is_distance_adjusted: bool,
    adjusted_distance_km: Decimal | None,
    map_distance_km: Decimal | None,
    gps_distance_km: Decimal | None,
) -> Decimal | None:
    """Adjusted distance wins only when the adjustment flag is set. Map, then GPS, otherwise.

    Stored GPS and map values are never replaced by this result.
    """
    if is_distance_adjusted and adjusted_distance_km is not None:
        return Decimal(adjusted_distance_km)
    if map_distance_km is not None:
        return Decimal(map_distance_km)
    if gps_distance_km is not None:
        return Decimal(gps_distance_km)
    return None


def rate_for_vehicle(
    vehicle_type: str | None,
    *,
    bike_rate: Decimal | None,
    car_rate: Decimal | None,
) -> Decimal | None:
    """Own bike and own car use the configured rates. Other vehicle types are not km reimbursements."""
    if vehicle_type == BIKE_VEHICLE:
        return bike_rate
    if vehicle_type == CAR_VEHICLE:
        return car_rate
    return None


def ta_amount(distance_km: Decimal | None, rate_per_km: Decimal | None) -> Decimal | None:
    if distance_km is None or rate_per_km is None:
        return None
    return (distance_km * rate_per_km).quantize(MONEY)


def is_payable(status: str) -> bool:
    return status in PAYABLE_STATUSES


def apply_decision(current: str, action: str) -> str | None:
    """Next approval or settlement status. Trip completion is not part of this state.

    Pending can be approved or rejected. Only an approved row can be sent to payroll.
    """
    if action == "Approved" and current == "Pending":
        return "Approved"
    if action == "Rejected" and current == "Pending":
        return "Rejected"
    if action == "Sent" and current == "Approved":
        return "Sent"
    if action == "Paid" and current in {"Approved", "Sent"}:
        return "Paid"
    return None


def approval_and_settlement(decision: str | None) -> tuple[str, str]:
    """Split the stored decision into the two statuses the screen shows."""
    if decision == "Approved":
        return "Approved", "Open"
    if decision == "Rejected":
        return "Rejected", "Open"
    if decision == "Sent":
        return "Approved", "Sent"
    if decision == "Paid":
        return "Approved", "Paid"
    return "Pending", "Open"


def money_for_km(
    bike_km: Decimal,
    car_km: Decimal,
    *,
    bike_rate: Decimal | None,
    car_rate: Decimal | None,
) -> tuple[Decimal, Decimal, Decimal]:
    bike = ta_amount(bike_km, bike_rate) or Decimal("0.00")
    car = ta_amount(car_km, car_rate) or Decimal("0.00")
    return bike, car, (bike + car).quantize(MONEY)
