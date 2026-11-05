"""Reads trk.trip with employee master data. Trip rows are not updated."""

from datetime import UTC, datetime
from decimal import Decimal
from typing import Any, cast

from sqlalchemy import and_, case, func, or_, select
from sqlalchemy.orm import Session, aliased
from sqlalchemy.sql import Select
from sqlalchemy.sql.selectable import Join

from trishul_api.common.paging import SortColumns, order_by_sort
from trishul_api.db.models import (
    Branch,
    Company,
    CustomerSite,
    Designation,
    Employee,
    SalaryComponent,
    SalaryStructure,
    SalaryStructureLine,
    ServiceCall,
    ServiceVisit,
    StatusHistory,
    TrackableActivity,
    TrkTrip,
    Vehicle,
)
from trishul_api.modules.hr.tada.calculation import PAYABLE_STATUSES
from trishul_api.modules.hr.tada.schemas import TadaAllowance, TadaEmployeeQuery, TadaReportQuery

BIKE_RATE_REGISTRATION = "TA-RATE-BIKE"
CAR_RATE_REGISTRATION = "TA-RATE-CAR"

_ALLOWANCE_CODES = frozenset({"HRA", "SPECIAL", "SPA", "OTHER", "CONV", "CONVEYANCE", "PROMOTION", "PROMO"})


def applicable_distance_sql() -> Any:
    """Adjusted kilometres only when the flag is set; otherwise map, then GPS."""
    adjusted = and_(TrkTrip.is_distance_adjusted == True, TrkTrip.adjusted_distance_km.is_not(None))  # noqa: E712
    return case(
        (adjusted, TrkTrip.adjusted_distance_km),
        (TrkTrip.map_distance_km.is_not(None), TrkTrip.map_distance_km),
        else_=TrkTrip.gps_distance_km,
    )


class TadaRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def add(self, obj: object) -> None:
        self._session.add(obj)

    def flush(self) -> None:
        self._session.flush()

    def rate_vehicle(self, registration: str) -> Vehicle | None:
        return self._session.scalar(select(Vehicle).where(Vehicle.registration_number == registration))

    def list_rows(
        self, query: TadaReportQuery, start: datetime, end: datetime, *, bike_rate: Decimal, car_rate: Decimal | None
    ) -> tuple[list[dict[str, Any]], int]:
        distance = applicable_distance_sql()
        statement = self._select(distance).where(*self._filters(query, start, end))
        total = self._session.scalar(select(func.count()).select_from(statement.order_by(None).subquery())) or 0
        rate = case(
            (TrkTrip.vehicle_type == "Own bike", bike_rate),
            (TrkTrip.vehicle_type == "Own car", car_rate),
            else_=None,
        )
        columns: SortColumns = {
            "startAt": TrkTrip.start_at,
            "employeeCode": Employee.employee_code,
            "status": TrkTrip.status,
            "applicableDistance": distance,
            "taAmount": distance * rate,
        }
        ordered = order_by_sort(statement, query.sort, columns, default="-startAt", tiebreaker=TrkTrip.id.desc())
        rows = self._session.execute(
            ordered.offset((query.page - 1) * query.page_size).limit(query.page_size)
        ).mappings()
        return [dict(row) for row in rows], int(total)

    def summary(
        self, query: TadaReportQuery, start: datetime, end: datetime
    ) -> tuple[int, int, Decimal, list[tuple[Any, Any, Any]]]:
        distance = applicable_distance_sql()
        filters = self._filters(query, start, end)
        joined = TrkTrip.__table__.join(Employee.__table__, Employee.id == TrkTrip.employee_id)
        engineers, trips, kilometres = self._session.execute(
            select(
                func.count(func.distinct(TrkTrip.employee_id)),
                func.count(TrkTrip.id),
                func.coalesce(func.sum(distance), 0),
            )
            .select_from(joined)
            .where(*filters)
        ).one()
        grouped = self._session.execute(
            select(TrkTrip.vehicle_type, TrkTrip.status, func.coalesce(func.sum(distance), 0))
            .select_from(joined)
            .where(*filters)
            .group_by(TrkTrip.vehicle_type, TrkTrip.status)
        ).all()
        return int(engineers or 0), int(trips or 0), Decimal(str(kilometres)), list(grouped)

    def commit(self) -> None:
        self._session.commit()

    def employee_page(
        self, query: TadaEmployeeQuery, start: datetime, end: datetime, month: str
    ) -> tuple[list[dict[str, Any]], int, Decimal, Decimal, Decimal, Decimal]:
        filtered = self._filtered_employees(query, start, end, month)
        engineers, trips, bike_km, car_km, travel_km = self._session.execute(
            select(
                func.count(),
                func.coalesce(func.sum(filtered.c.total_trips), 0),
                func.coalesce(func.sum(filtered.c.bike_km), 0),
                func.coalesce(func.sum(filtered.c.car_km), 0),
                func.coalesce(func.sum(filtered.c.travel_km), 0),
            ).select_from(filtered)
        ).one()
        columns: SortColumns = {
            "employeeCode": filtered.c.employee_code,
            "totalTrips": filtered.c.total_trips,
            "bikeKm": filtered.c.bike_km,
            "carKm": filtered.c.car_km,
            "totalKm": filtered.c.bike_km + filtered.c.car_km,
        }
        ordered = order_by_sort(
            select(filtered), query.sort, columns, default="employeeCode", tiebreaker=filtered.c.employee_id.asc()
        )
        rows = self._session.execute(
            ordered.offset((query.page - 1) * query.page_size).limit(query.page_size)
        ).mappings()
        return (
            [dict(row) for row in rows],
            int(engineers or 0),
            Decimal(str(trips or 0)),
            Decimal(str(bike_km or 0)),
            Decimal(str(car_km or 0)),
            Decimal(str(travel_km or 0)),
        )

    def filtered_employee_ids(self, query: TadaEmployeeQuery, start: datetime, end: datetime, month: str) -> list[int]:
        filtered = self._filtered_employees(query, start, end, month)
        rows = self._session.execute(select(filtered.c.employee_id)).all()
        return [int(row[0]) for row in rows]

    def _filtered_employees(self, query: TadaEmployeeQuery, start: datetime, end: datetime, month: str) -> Any:
        grouped = self._employee_groups(query, start, end).subquery()
        latest = self._latest_decisions(month)
        decision = latest.c.to_status
        statement = select(
            grouped.c.employee_id,
            grouped.c.employee_code,
            grouped.c.first_name,
            grouped.c.last_name,
            grouped.c.designation,
            grouped.c.total_trips,
            grouped.c.bike_km,
            grouped.c.car_km,
            grouped.c.travel_km,
            decision.label("decision"),
        ).select_from(grouped.outerjoin(latest, latest.c.entity_id == grouped.c.employee_id))
        return self._decision_filters(statement, query, decision).subquery()

    def payable_employees(self, employee_ids: list[int], start: datetime, end: datetime) -> set[int]:
        if not employee_ids:
            return set()
        rows = self._session.execute(
            select(TrkTrip.employee_id)
            .where(
                TrkTrip.employee_id.in_(employee_ids),
                TrkTrip.is_active == True,  # noqa: E712
                TrkTrip.start_at >= start,
                TrkTrip.start_at < end,
                TrkTrip.status.in_(tuple(PAYABLE_STATUSES)),
                TrkTrip.vehicle_type.in_(("Own bike", "Own car")),
            )
            .distinct()
        ).all()
        return {int(row[0]) for row in rows}

    def current_decisions(self, month: str, employee_ids: list[int]) -> dict[int, str]:
        if not employee_ids:
            return {}
        latest = self._latest_decisions(month)
        rows = self._session.execute(
            select(latest.c.entity_id, latest.c.to_status).where(latest.c.entity_id.in_(employee_ids))
        ).all()
        return {int(employee_id): str(status) for employee_id, status in rows}

    def employee_codes(self, employee_ids: list[int]) -> dict[int, str]:
        if not employee_ids:
            return {}
        rows = self._session.execute(
            select(Employee.id, Employee.employee_code).where(Employee.id.in_(employee_ids))
        ).all()
        return {int(employee_id): str(code) for employee_id, code in rows}

    def record_decision(
        self, *, month: str, employee_id: int, from_status: str, to_status: str, actor_id: int, remarks: str
    ) -> None:
        self._session.add(
            StatusHistory(
                entity_type=f"tada-{month}",
                entity_id=employee_id,
                from_status=from_status,
                to_status=to_status,
                changed_by_user_id=actor_id,
                changed_at=datetime.now(UTC).replace(tzinfo=None),
                remarks=remarks,
            )
        )

    def allowance_amounts(self, employee_ids: list[int], on: datetime) -> dict[int, Decimal]:
        if not employee_ids:
            return {}
        day = on.date()
        rows = self._session.execute(
            select(
                SalaryStructure.employee_id,
                SalaryComponent.code,
                SalaryComponent.name,
                SalaryStructureLine.monthly_amount,
            )
            .join(SalaryStructureLine, SalaryStructureLine.salary_component_id == SalaryComponent.id)
            .join(SalaryStructure, SalaryStructure.id == SalaryStructureLine.salary_structure_id)
            .where(
                SalaryStructure.employee_id.in_(employee_ids),
                SalaryStructure.is_active == True,  # noqa: E712
                SalaryComponent.is_active == True,  # noqa: E712
                SalaryStructure.effective_from <= day,
                or_(SalaryStructure.effective_to.is_(None), SalaryStructure.effective_to >= day),
            )
        ).all()
        totals: dict[int, Decimal] = {}
        for employee_id, code, name, amount in rows:
            if amount is None or not _is_separate_allowance(code, name):
                continue
            totals[int(employee_id)] = totals.get(int(employee_id), Decimal("0.00")) + Decimal(amount)
        return totals

    def _employee_groups(self, query: TadaReportQuery, start: datetime, end: datetime) -> Select[Any]:
        distance = applicable_distance_sql()
        payable = TrkTrip.status.in_(tuple(PAYABLE_STATUSES))
        bike = func.coalesce(
            func.sum(case((and_(payable, TrkTrip.vehicle_type == "Own bike"), distance), else_=0)), 0
        )
        car = func.coalesce(
            func.sum(case((and_(payable, TrkTrip.vehicle_type == "Own car"), distance), else_=0)), 0
        )
        statement = (
            select(
                Employee.id.label("employee_id"),
                Employee.employee_code,
                Employee.first_name,
                Employee.last_name,
                Designation.name.label("designation"),
                func.count(TrkTrip.id).label("total_trips"),
                bike.label("bike_km"),
                car.label("car_km"),
                func.coalesce(func.sum(distance), 0).label("travel_km"),
            )
            .select_from(
                TrkTrip.__table__.join(Employee.__table__, Employee.id == TrkTrip.employee_id).outerjoin(
                    Designation.__table__, Designation.id == Employee.designation_id
                )
            )
            .where(*self._filters(query, start, end))
            .group_by(
                Employee.id, Employee.employee_code, Employee.first_name, Employee.last_name, Designation.name
            )
        )
        return cast(Select[Any], statement)

    def _latest_decisions(self, month: str) -> Any:
        ranked = (
            select(
                StatusHistory.entity_id,
                StatusHistory.to_status,
                func.row_number()
                .over(partition_by=StatusHistory.entity_id, order_by=StatusHistory.id.desc())
                .label("rn"),
            )
            .where(StatusHistory.entity_type == f"tada-{month}")
            .subquery()
        )
        return select(ranked.c.entity_id, ranked.c.to_status).where(ranked.c.rn == 1).subquery()

    def _decision_filters(self, statement: Any, query: TadaEmployeeQuery, decision: Any) -> Any:
        if query.approval_status == "Pending":
            statement = statement.where(or_(decision.is_(None), decision == "Pending"))
        elif query.approval_status == "Approved":
            statement = statement.where(decision.in_(("Approved", "Sent")))
        elif query.approval_status == "Rejected":
            statement = statement.where(decision == "Rejected")
        if query.settlement_status == "Sent":
            statement = statement.where(decision == "Sent")
        elif query.settlement_status == "Open":
            statement = statement.where(or_(decision.is_(None), decision != "Sent"))
        return statement

    def get_row(self, trip_id: int) -> dict[str, Any] | None:
        statement = self._select(applicable_distance_sql()).where(
            TrkTrip.id == trip_id,
            TrkTrip.is_active == True,  # noqa: E712
        )
        row = self._session.execute(statement).mappings().first()
        return dict(row) if row else None

    def monthly_allowances(self, employee_id: int, on: datetime) -> list[TadaAllowance]:
        day = on.date()
        rows = self._session.execute(
            select(SalaryComponent.code, SalaryComponent.name, SalaryStructureLine.monthly_amount)
            .join(SalaryStructureLine, SalaryStructureLine.salary_component_id == SalaryComponent.id)
            .join(SalaryStructure, SalaryStructure.id == SalaryStructureLine.salary_structure_id)
            .where(
                SalaryStructure.employee_id == employee_id,
                SalaryStructure.is_active == True,  # noqa: E712
                SalaryComponent.is_active == True,  # noqa: E712
                SalaryStructure.effective_from <= day,
                or_(SalaryStructure.effective_to.is_(None), SalaryStructure.effective_to >= day),
            )
        ).all()
        return [
            TadaAllowance(code=code, name=name, monthly_amount=amount)
            for code, name, amount in rows
            if _is_separate_allowance(code, name)
        ]

    def _select(self, distance: Any) -> Select[Any]:
        call_direct = aliased(ServiceCall)
        visit = aliased(ServiceVisit)
        call_via_visit = aliased(ServiceCall)
        site_direct = aliased(CustomerSite)
        site_via_visit = aliased(CustomerSite)
        travel_to = func.coalesce(site_direct.site_name, site_via_visit.site_name, TrackableActivity.title, "")
        statement = select(
            TrkTrip.id,
            TrkTrip.employee_id,
            Employee.employee_code,
            Employee.first_name,
            Employee.last_name,
            Designation.name.label("designation"),
            func.coalesce(Company.trade_name, Company.legal_name).label("company_name"),
            Branch.name.label("branch_name"),
            TrkTrip.trip_type,
            TrkTrip.start_at,
            TrkTrip.end_at,
            TrkTrip.vehicle_type,
            TrkTrip.gps_distance_km,
            TrkTrip.map_distance_km,
            TrkTrip.adjusted_distance_km,
            TrkTrip.is_distance_adjusted,
            distance.label("applicable_distance_km"),
            TrkTrip.status,
            TrkTrip.start_latitude,
            TrkTrip.start_longitude,
            TrkTrip.end_latitude,
            TrkTrip.end_longitude,
            TrkTrip.duration_minutes,
            TrkTrip.route_polyline,
            travel_to.label("site_name"),
        ).select_from(self._places(call_direct, visit, call_via_visit, site_direct, site_via_visit))
        return cast(Select[Any], statement)

    def _places(
        self,
        call_direct: Any,
        visit: Any,
        call_via_visit: Any,
        site_direct: Any,
        site_via_visit: Any,
    ) -> Join:
        return (
            TrkTrip.__table__.join(Employee.__table__, Employee.id == TrkTrip.employee_id)
            .join(Company.__table__, Company.id == Employee.company_id)
            .join(Branch.__table__, Branch.id == Employee.branch_id)
            .outerjoin(Designation.__table__, Designation.id == Employee.designation_id)
            .outerjoin(TrackableActivity.__table__, TrackableActivity.id == TrkTrip.trackable_activity_id)
            .outerjoin(
                call_direct,
                and_(
                    TrackableActivity.source_schema == "svc",
                    TrackableActivity.source_table == "service_call",
                    TrackableActivity.source_id == call_direct.id,
                ),
            )
            .outerjoin(
                visit,
                and_(
                    TrackableActivity.source_schema == "svc",
                    TrackableActivity.source_table == "service_visit",
                    TrackableActivity.source_id == visit.id,
                ),
            )
            .outerjoin(call_via_visit, call_via_visit.id == visit.service_call_id)
            .outerjoin(site_direct, site_direct.id == call_direct.customer_site_id)
            .outerjoin(site_via_visit, site_via_visit.id == call_via_visit.customer_site_id)
        )

    def _filters(self, query: TadaReportQuery, start: datetime, end: datetime) -> list[Any]:
        clauses: list[Any] = [
            TrkTrip.is_active == True,  # noqa: E712
            TrkTrip.start_at >= start,
            TrkTrip.start_at < end,
        ]
        if query.company_id is not None:
            clauses.append(Employee.company_id == query.company_id)
        if query.branch_id is not None:
            clauses.append(Employee.branch_id == query.branch_id)
        if query.employee_id is not None:
            clauses.append(TrkTrip.employee_id == query.employee_id)
        if query.designation_id is not None:
            clauses.append(Employee.designation_id == query.designation_id)
        if query.department_id is not None:
            clauses.append(Employee.department_id == query.department_id)
        if query.vehicle_type is not None:
            clauses.append(TrkTrip.vehicle_type == query.vehicle_type)
        if query.status is not None:
            clauses.append(TrkTrip.status == query.status)
        if query.search:
            like = f"%{query.search.strip()}%"
            clauses.append(
                or_(
                    Employee.employee_code.ilike(like),
                    Employee.first_name.ilike(like),
                    Employee.last_name.ilike(like),
                )
            )
        return clauses


def _is_separate_allowance(code: str, name: str) -> bool:
    token = f"{code} {name}".upper()
    if any(part in token for part in ("HRA", "CONVEYANCE", "PROMOTION")):
        return True
    if "SPECIAL" in token and "ALLOWANCE" in token:
        return True
    if "OTHER" in token and "ALLOWANCE" in token:
        return True
    return code.upper() in _ALLOWANCE_CODES
