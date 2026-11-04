"""TA/DA report: distance priority, vehicle rates and payable totals. Trip rows are not modified."""

from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy.orm import Session

from trishul_api.auth import CurrentUser
from trishul_api.common.errors import NotFound
from trishul_api.db.models import Vehicle
from trishul_api.modules.hr.tada.calculation import (
    DEFAULT_BIKE_RATE,
    applicable_distance_km,
    apply_decision,
    approval_and_settlement,
    is_payable,
    money_for_km,
    rate_for_vehicle,
    ta_amount,
)
from trishul_api.modules.hr.tada.repository import BIKE_RATE_REGISTRATION, CAR_RATE_REGISTRATION, TadaRepository
from trishul_api.modules.hr.tada.schemas import (
    TadaBulkResult,
    TadaBulkSkip,
    TadaDecisionCreate,
    TadaEmployeeItem,
    TadaEmployeeQuery,
    TadaEmployeeReport,
    TadaEmployeeSummary,
    TadaRates,
    TadaRatesUpdate,
    TadaReport,
    TadaReportQuery,
    TadaSettlementCreate,
    TadaSummary,
    TadaTripDetail,
    TadaTripItem,
)

_NOTE = (
    "Payable TA includes Completed and Auto closed trips only. "
    "trk.trip has no approval or payroll-processed flag, and expense claim lines reference svc.trip, "
    "so this report does not mark a trip as paid."
)
_EMPLOYEE_NOTE = (
    "Payable kilometres are completed and auto-closed own-bike and own-car trips. "
    "Approval and payroll settlement are stored separately from the trip. "
    "Additional allowance is the current monthly salary component, not another trip payment."
)
_ALLOWANCE_NOTE = (
    "These amounts are the employee's current monthly salary components. "
    "They are not added to the trip TA."
)


class TadaService:
    def __init__(self, session: Session) -> None:
        self._trips = TadaRepository(session)

    def report(self, query: TadaReportQuery) -> TadaReport:
        start, end, month = _month_window(query.month)
        rates = self.rates()
        rows, total = self._trips.list_rows(query, start, end, bike_rate=rates.bike_per_km, car_rate=rates.car_per_km)
        engineers, trips, kilometres, grouped = self._trips.summary(query, start, end)
        bike, car = _allowances(grouped, rates)
        return TadaReport(
            items=[self._item(row, rates) for row in rows],
            total=total,
            page=query.page,
            page_size=query.page_size,
            summary=TadaSummary(
                service_engineers=engineers,
                trips=trips,
                travel_km=kilometres.quantize(Decimal("0.001")),
                bike_allowance=bike,
                car_allowance=car,
                total_ta_payable=(bike + car).quantize(Decimal("0.01")),
                month=month,
                note=_NOTE,
            ),
            rates=rates,
        )

    def employees(self, query: TadaEmployeeQuery) -> TadaEmployeeReport:
        start, end, month = _month_window(query.month)
        rates = self.rates()
        rows, engineers, trips, bike_km, car_km, travel_km = self._trips.employee_page(query, start, end, month)
        previous = _shift_month(month, -1)
        previous_start, previous_end, _ = _month_window(previous)
        _, previous_engineers, previous_trips, previous_bike, previous_car, previous_travel = self._trips.employee_page(
            query, previous_start, previous_end, previous
        )
        bike_pay, car_pay, ta = money_for_km(
            bike_km, car_km, bike_rate=rates.bike_per_km, car_rate=rates.car_per_km
        )
        previous_bike_pay, previous_car_pay, previous_ta = money_for_km(
            previous_bike, previous_car, bike_rate=rates.bike_per_km, car_rate=rates.car_per_km
        )
        page_ids = [int(row["employee_id"]) for row in rows]
        allowances = self._trips.allowance_amounts(page_ids, start)
        filtered_ids = self._trips.filtered_employee_ids(query, start, end, month)
        extra = _allowance_total(self._trips.allowance_amounts(filtered_ids, start))
        previous_extra = _allowance_total(
            self._trips.allowance_amounts(
                self._trips.filtered_employee_ids(query, previous_start, previous_end, previous), previous_start
            )
        )
        return TadaEmployeeReport(
            items=[self._employee(row, rates, allowances) for row in rows],
            total=engineers,
            page=query.page,
            page_size=query.page_size,
            summary=TadaEmployeeSummary(
                service_engineers=engineers,
                trips=int(trips),
                travel_km=travel_km.quantize(Decimal("0.001")),
                bike_allowance=bike_pay,
                car_allowance=car_pay,
                total_ta_payable=(ta + extra).quantize(Decimal("0.01")),
                month=month,
                note=_EMPLOYEE_NOTE,
                previous_service_engineers=previous_engineers,
                previous_trips=int(previous_trips),
                previous_travel_km=previous_travel.quantize(Decimal("0.001")),
                previous_bike_allowance=previous_bike_pay,
                previous_car_allowance=previous_car_pay,
                previous_total_payable=(previous_ta + previous_extra).quantize(Decimal("0.01")),
            ),
            rates=rates,
        )

    def employee_trips(self, employee_id: int, month: str) -> list[TadaTripItem]:
        return self.report(
            TadaReportQuery(employee_id=employee_id, month=month, page=1, page_size=200, sort="startAt")
        ).items

    def decide(self, data: TadaDecisionCreate, actor: CurrentUser) -> TadaBulkResult:
        return self._change_state(data.payroll_month, data.employee_ids, data.decision, actor, data.decision)

    def send_to_payroll(self, data: TadaSettlementCreate, actor: CurrentUser) -> TadaBulkResult:
        return self._change_state(data.payroll_month, data.employee_ids, "Sent", actor, "Sent to payroll")

    def _change_state(
        self, month: str, employee_ids: list[int], action: str, actor: CurrentUser, label: str
    ) -> TadaBulkResult:
        start, end, month = _month_window(month)
        codes = self._trips.employee_codes(employee_ids)
        payable = self._trips.payable_employees(employee_ids, start, end)
        current = self._trips.current_decisions(month, employee_ids)
        skipped: list[TadaBulkSkip] = []
        updated = 0
        for employee_id in employee_ids:
            code = codes.get(employee_id, str(employee_id))
            if employee_id not in codes:
                skipped.append(TadaBulkSkip(employee_id=employee_id, employee_code=code, reason="Employee not found."))
                continue
            if employee_id not in payable:
                skipped.append(
                    TadaBulkSkip(
                        employee_id=employee_id,
                        employee_code=code,
                        reason="No completed own-bike or own-car trip in this month.",
                    )
                )
                continue
            state = current.get(employee_id, "Pending")
            nxt = apply_decision(state, action)
            if nxt is None:
                skipped.append(TadaBulkSkip(employee_id=employee_id, employee_code=code, reason=_skip_reason(state)))
                continue
            self._trips.record_decision(
                month=month,
                employee_id=employee_id,
                from_status=state,
                to_status=nxt,
                actor_id=actor.id,
                remarks=label,
            )
            updated += 1
        if updated:
            self._trips.commit()
        return TadaBulkResult(updated=updated, skipped=skipped)

    def trip(self, trip_id: int) -> TadaTripDetail:
        row = self._trips.get_row(trip_id)
        if row is None:
            raise NotFound("Trip not found.")
        rates = self.rates()
        item = self._item(row, rates)
        started = row["start_at"]
        assert isinstance(started, datetime)
        return TadaTripDetail(
            **item.model_dump(),
            start_latitude=row["start_latitude"],
            start_longitude=row["start_longitude"],
            end_latitude=row["end_latitude"],
            end_longitude=row["end_longitude"],
            duration_minutes=row["duration_minutes"],
            route_polyline=row["route_polyline"],
            allowances=self._trips.monthly_allowances(int(row["employee_id"]), started),
            allowance_note=_ALLOWANCE_NOTE,
        )

    def rates(self) -> TadaRates:
        bike = self._trips.rate_vehicle(BIKE_RATE_REGISTRATION)
        car = self._trips.rate_vehicle(CAR_RATE_REGISTRATION)
        bike_rate = bike.rate_per_km if bike and bike.rate_per_km is not None else None
        car_rate = car.rate_per_km if car and car.rate_per_km is not None else None
        return TadaRates(
            bike_per_km=bike_rate if bike_rate is not None else DEFAULT_BIKE_RATE,
            car_per_km=car_rate,
            bike_configured=bike_rate is not None,
            car_configured=car_rate is not None,
        )

    def save_rates(self, data: TadaRatesUpdate, actor: CurrentUser) -> TadaRates:
        self._save_rate(BIKE_RATE_REGISTRATION, "Bike", data.bike_per_km, actor)
        self._save_rate(CAR_RATE_REGISTRATION, "Car", data.car_per_km, actor)
        self._trips.flush()
        self._trips.commit()
        return self.rates()

    def _save_rate(self, registration: str, vehicle_type: str, rate: Decimal, actor: CurrentUser) -> None:
        row = self._trips.rate_vehicle(registration)
        if row is None:
            self._trips.add(
                Vehicle(
                    registration_number=registration,
                    vehicle_type=vehicle_type,
                    ownership="Company",
                    rate_per_km=rate,
                    is_active=True,
                    created_by_user_id=actor.id,
                )
            )
            return
        row.rate_per_km = rate
        row.updated_by_user_id = actor.id

    def _item(self, row: dict[str, Any], rates: TadaRates) -> TadaTripItem:
        distance = applicable_distance_km(
            is_distance_adjusted=bool(row["is_distance_adjusted"]),
            adjusted_distance_km=_decimal(row["adjusted_distance_km"]),
            map_distance_km=_decimal(row["map_distance_km"]),
            gps_distance_km=_decimal(row["gps_distance_km"]),
        )
        vehicle = row["vehicle_type"]
        rate = rate_for_vehicle(
            str(vehicle) if vehicle is not None else None,
            bike_rate=rates.bike_per_km,
            car_rate=rates.car_per_km,
        )
        status = str(row["status"])
        payable = is_payable(status)
        amount = ta_amount(distance, rate)
        travel_from, travel_to = _places(str(row["trip_type"]), str(row["branch_name"]), str(row["site_name"] or ""))
        started = row["start_at"]
        assert isinstance(started, datetime)
        last_name = row["last_name"]
        name = str(row["first_name"])
        if last_name:
            name = f"{name} {last_name}"
        return TadaTripItem(
            id=int(row["id"]),
            employee_code=str(row["employee_code"]),
            employee_name=name,
            designation=str(row["designation"]) if row["designation"] else None,
            company_name=str(row["company_name"]),
            branch_name=str(row["branch_name"]),
            trip_date=started.date().isoformat(),
            trip_type=row["trip_type"],
            start_at=started,
            end_at=row["end_at"] if isinstance(row["end_at"], datetime) else None,
            travel_from=travel_from,
            travel_to=travel_to,
            vehicle_type=vehicle,
            gps_distance_km=_decimal(row["gps_distance_km"]),
            map_distance_km=_decimal(row["map_distance_km"]),
            adjusted_distance_km=_decimal(row["adjusted_distance_km"]),
            is_distance_adjusted=bool(row["is_distance_adjusted"]),
            applicable_distance_km=distance,
            rate_per_km=rate,
            ta_amount=amount,
            status=row["status"],
            payable=payable,
        )

    def _employee(self, row: dict[str, Any], rates: TadaRates, allowances: dict[int, Decimal]) -> TadaEmployeeItem:
        bike_km = _decimal(row["bike_km"]) or Decimal("0")
        car_km = _decimal(row["car_km"]) or Decimal("0")
        _, _, ta = money_for_km(bike_km, car_km, bike_rate=rates.bike_per_km, car_rate=rates.car_per_km)
        extra = allowances.get(int(row["employee_id"]), Decimal("0.00")).quantize(Decimal("0.01"))
        approval, settlement = approval_and_settlement(str(row["decision"]) if row["decision"] else None)
        last_name = row["last_name"]
        name = str(row["first_name"])
        if last_name:
            name = f"{name} {last_name}"
        return TadaEmployeeItem(
            employee_id=int(row["employee_id"]),
            employee_code=str(row["employee_code"]),
            employee_name=name,
            designation=str(row["designation"]) if row["designation"] else None,
            total_trips=int(row["total_trips"]),
            bike_km=bike_km.quantize(Decimal("0.001")),
            car_km=car_km.quantize(Decimal("0.001")),
            total_km=(bike_km + car_km).quantize(Decimal("0.001")),
            ta_amount=ta,
            additional_allowance=extra,
            total_payable=(ta + extra).quantize(Decimal("0.01")),
            approval_status=approval,
            settlement_status=settlement,
        )


def _allowance_total(amounts: dict[int, Decimal]) -> Decimal:
    return sum(amounts.values(), Decimal("0.00")).quantize(Decimal("0.01"))


def _allowances(grouped: list[tuple[object, object, object]], rates: TadaRates) -> tuple[Decimal, Decimal]:
    bike = Decimal("0.00")
    car = Decimal("0.00")
    for vehicle, status, kilometres in grouped:
        if not is_payable(str(status)):
            continue
        amount = ta_amount(
            Decimal(str(kilometres)),
            rate_for_vehicle(
                str(vehicle) if vehicle is not None else None,
                bike_rate=rates.bike_per_km,
                car_rate=rates.car_per_km,
            ),
        )
        if vehicle == "Own bike" and amount is not None:
            bike += amount
        elif vehicle == "Own car" and amount is not None:
            car += amount
    return bike.quantize(Decimal("0.01")), car.quantize(Decimal("0.01"))


def _skip_reason(current: str) -> str:
    if current == "Sent":
        return "Already sent to payroll."
    if current == "Approved":
        return "Already approved."
    if current == "Rejected":
        return "Already rejected."
    return "This employee cannot be updated."


def _shift_month(month: str, delta: int) -> str:
    year, mon = (int(part) for part in month.split("-"))
    mon += delta
    while mon < 1:
        mon += 12
        year -= 1
    while mon > 12:
        mon -= 12
        year += 1
    return f"{year:04d}-{mon:02d}"


def _places(trip_type: str, branch_name: str, site_name: str) -> tuple[str, str]:
    site = site_name.strip() or "Site not recorded"
    office = branch_name.strip() or "Branch"
    if trip_type == "Return":
        return site, office
    return office, site


def _month_window(month: str | None) -> tuple[datetime, datetime, str]:
    if month is None:
        today = datetime.now(UTC)
        month = f"{today.year:04d}-{today.month:02d}"
    year, mon = (int(part) for part in month.split("-"))
    start = datetime(year, mon, 1)
    end = datetime(year + 1, 1, 1) if mon == 12 else datetime(year, mon + 1, 1)
    return start, end, month


def _decimal(value: object) -> Decimal | None:
    if value is None:
        return None
    return Decimal(str(value))
