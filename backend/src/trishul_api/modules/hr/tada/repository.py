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
    AppUser,
    Attachment,
    Branch,
    Company,
    CustomerSite,
    Designation,
    Employee,
    SalaryComponent,
    SalaryStructure,
    SalaryStructureLine,
    ServiceCall,
    ServiceReport,
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
TRIP_DECISION = "tada-trip"

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
        self, *, month: str, employee_id: int, from_status: str, to_status: str, actor_id: int, remarks: str | None
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

    def decision_history(self, month: str, employee_id: int) -> list[dict[str, Any]]:
        actor = aliased(Employee)
        rows = self._session.execute(
            select(
                StatusHistory.id,
                StatusHistory.from_status,
                StatusHistory.to_status,
                StatusHistory.remarks,
                StatusHistory.changed_at,
                StatusHistory.changed_by_user_id,
                AppUser.username,
                actor.first_name,
                actor.last_name,
            )
            .outerjoin(AppUser, AppUser.id == StatusHistory.changed_by_user_id)
            .outerjoin(actor, actor.id == AppUser.employee_id)
            .where(
                StatusHistory.entity_type == f"tada-{month}",
                StatusHistory.entity_id == employee_id,
            )
            .order_by(StatusHistory.id.desc())
        ).mappings()
        return [dict(row) for row in rows]

    def review_counts(
        self, employee_ids: list[int], start: datetime, end: datetime
    ) -> dict[int, tuple[int, int, int, int]]:
        """Pending, approved, rejected and sent trip counts for the payroll month."""
        counts = {employee_id: [0, 0, 0, 0] for employee_id in employee_ids}
        if not employee_ids:
            return {}
        trips = self._session.execute(
            select(TrkTrip.employee_id, TrkTrip.id).where(
                TrkTrip.employee_id.in_(employee_ids),
                TrkTrip.is_active == True,  # noqa: E712
                TrkTrip.start_at >= start,
                TrkTrip.start_at < end,
            )
        ).all()
        decisions = self.latest_trip_decisions([int(trip_id) for _, trip_id in trips])
        buckets = {"Pending": 0, "Approved": 1, "Rejected": 2, "Sent": 3}
        for employee_id, trip_id in trips:
            status = decisions.get(int(trip_id), "Pending")
            counts[int(employee_id)][buckets.get(status, 0)] += 1
        return {employee_id: (row[0], row[1], row[2], row[3]) for employee_id, row in counts.items()}

    def latest_trip_decisions(self, trip_ids: list[int]) -> dict[int, str]:
        if not trip_ids:
            return {}
        ranked = (
            select(
                StatusHistory.entity_id.label("trip_id"),
                StatusHistory.to_status.label("to_status"),
                func.row_number()
                .over(partition_by=StatusHistory.entity_id, order_by=StatusHistory.id.desc())
                .label("row_number"),
            )
            .where(StatusHistory.entity_type == TRIP_DECISION, StatusHistory.entity_id.in_(trip_ids))
            .subquery()
        )
        rows = self._session.execute(select(ranked.c.trip_id, ranked.c.to_status).where(ranked.c.row_number == 1)).all()
        return {int(trip_id): str(status) for trip_id, status in rows}

    def latest_trip_remarks(self, trip_ids: list[int]) -> dict[int, str | None]:
        """Latest remarks that record an approved fare. A later payroll mark does not erase it."""
        if not trip_ids:
            return {}
        rows = self._session.execute(
            select(StatusHistory.entity_id, StatusHistory.remarks)
            .where(StatusHistory.entity_type == TRIP_DECISION, StatusHistory.entity_id.in_(trip_ids))
            .order_by(StatusHistory.id.desc())
        ).all()
        found: dict[int, str | None] = {}
        for trip_id, remarks in rows:
            trip_id = int(trip_id)
            if trip_id in found:
                continue
            text = str(remarks) if remarks else ""
            if "Approved amount:" in text:
                found[trip_id] = text
        return found

    def record_trip_decision(
        self, *, trip_id: int, from_status: str, to_status: str, actor_id: int, remarks: str | None
    ) -> None:
        self._session.add(
            StatusHistory(
                entity_type=TRIP_DECISION,
                entity_id=trip_id,
                from_status=from_status,
                to_status=to_status,
                changed_by_user_id=actor_id,
                changed_at=datetime.now(UTC).replace(tzinfo=None),
                remarks=remarks,
            )
        )

    def trip_decision_history(self, employee_id: int, start: datetime, end: datetime) -> list[dict[str, Any]]:
        actor = aliased(Employee)
        call_direct = aliased(ServiceCall)
        visit = aliased(ServiceVisit)
        call_via_visit = aliased(ServiceCall)
        rows = self._session.execute(
            select(
                StatusHistory.id,
                StatusHistory.entity_id.label("trip_id"),
                StatusHistory.from_status,
                StatusHistory.to_status,
                StatusHistory.remarks,
                StatusHistory.changed_at,
                StatusHistory.changed_by_user_id,
                AppUser.username,
                actor.first_name,
                actor.last_name,
                func.coalesce(call_via_visit.call_no, call_direct.call_no).label("call_no"),
            )
            .join(TrkTrip, TrkTrip.id == StatusHistory.entity_id)
            .outerjoin(AppUser, AppUser.id == StatusHistory.changed_by_user_id)
            .outerjoin(actor, actor.id == AppUser.employee_id)
            .outerjoin(TrackableActivity, TrackableActivity.id == TrkTrip.trackable_activity_id)
            .outerjoin(
                call_direct,
                and_(
                    TrackableActivity.source_table == "service_call",
                    TrackableActivity.source_id == call_direct.id,
                ),
            )
            .outerjoin(
                visit,
                and_(
                    TrackableActivity.source_table == "service_visit",
                    TrackableActivity.source_id == visit.id,
                ),
            )
            .outerjoin(call_via_visit, call_via_visit.id == visit.service_call_id)
            .where(
                StatusHistory.entity_type == TRIP_DECISION,
                TrkTrip.employee_id == employee_id,
                TrkTrip.start_at >= start,
                TrkTrip.start_at < end,
            )
            .order_by(StatusHistory.id.desc())
        ).mappings()
        return [dict(row) for row in rows]

    def approved_trip_ids(self, employee_ids: list[int], start: datetime, end: datetime) -> list[int]:
        trips = self._session.execute(
            select(TrkTrip.id).where(
                TrkTrip.employee_id.in_(employee_ids),
                TrkTrip.is_active == True,  # noqa: E712
                TrkTrip.start_at >= start,
                TrkTrip.start_at < end,
            )
        ).all()
        trip_ids = [int(trip_id) for (trip_id,) in trips]
        return [trip_id for trip_id, status in self.latest_trip_decisions(trip_ids).items() if status == "Approved"]

    def settlement_trips(self, employee_ids: list[int], start: datetime, end: datetime) -> list[dict[str, Any]]:
        """Completed bike, car, and public-transport trips whose TA can be settled. The trip row is not changed."""
        if not employee_ids:
            return []
        rows = self._session.execute(
            select(
                TrkTrip.id,
                TrkTrip.employee_id,
                TrkTrip.vehicle_type,
                TrkTrip.status,
                TrkTrip.is_distance_adjusted,
                TrkTrip.adjusted_distance_km,
                TrkTrip.map_distance_km,
                TrkTrip.gps_distance_km,
            ).where(
                TrkTrip.employee_id.in_(employee_ids),
                TrkTrip.is_active == True,  # noqa: E712
                TrkTrip.start_at >= start,
                TrkTrip.start_at < end,
                TrkTrip.status.in_(tuple(PAYABLE_STATUSES)),
                TrkTrip.vehicle_type.in_(("Own bike", "Own car", "Public transport")),
            )
        ).mappings()
        return [dict(row) for row in rows]

    def trip_documents(self, row: dict[str, Any]) -> list[dict[str, Any]]:
        documents: list[dict[str, Any]] = []
        seen: set[int] = set()
        trip_id = int(row["id"])
        for attachment in self._attachments("trk.trip", trip_id) + self._attachments("tada-trip", trip_id):
            self._add_document(documents, seen, attachment, "Fare receipt")
        call_id = row.get("call_id")
        if call_id is not None:
            for attachment in self._attachments("svc.service_call", int(call_id)):
                self._add_document(documents, seen, attachment, "Service call")
        if row.get("source_table") == "service_visit" and row.get("source_id") is not None:
            reports = self._session.scalars(
                select(ServiceReport).where(
                    ServiceReport.service_visit_id == int(row["source_id"]),
                    ServiceReport.is_active == True,  # noqa: E712
                )
            ).all()
            for report in reports:
                for attachment_id in (
                    report.pdf_attachment_id,
                    report.customer_signature_attachment_id,
                    report.engineer_signature_attachment_id,
                ):
                    if attachment_id is None:
                        continue
                    attachment = self._session.get(Attachment, int(attachment_id))
                    if attachment is not None and attachment.is_active:
                        self._add_document(documents, seen, attachment, "Service report")
                for attachment in self._attachments("svc.service_report", int(report.id)):
                    self._add_document(documents, seen, attachment, "Service report")
        return documents

    def attachment_for_review(self, attachment_id: int) -> Attachment | None:
        attachment = self._session.get(Attachment, attachment_id)
        if attachment is None or not attachment.is_active:
            return None
        if attachment.entity_type in {"trk.trip", "tada-trip"}:
            trip = self._session.get(TrkTrip, int(attachment.entity_id))
            return attachment if trip is not None else None
        if attachment.entity_type == "svc.service_call":
            linked = self._session.scalar(
                select(TrkTrip.id)
                .join(TrackableActivity, TrackableActivity.id == TrkTrip.trackable_activity_id)
                .outerjoin(
                    ServiceVisit,
                    and_(
                        TrackableActivity.source_table == "service_visit",
                        TrackableActivity.source_id == ServiceVisit.id,
                    ),
                )
                .where(
                    or_(
                        and_(
                            TrackableActivity.source_table == "service_call",
                            TrackableActivity.source_id == attachment.entity_id,
                        ),
                        ServiceVisit.service_call_id == attachment.entity_id,
                    )
                )
                .limit(1)
            )
            return attachment if linked is not None else None
        if attachment.entity_type == "svc.service_report":
            visit_id = self._session.scalar(
                select(ServiceReport.service_visit_id).where(ServiceReport.id == attachment.entity_id)
            )
            return attachment if visit_id is not None and self._visit_has_trip(int(visit_id)) else None
        report = self._session.scalar(
            select(ServiceReport.service_visit_id).where(
                or_(
                    ServiceReport.pdf_attachment_id == attachment.id,
                    ServiceReport.customer_signature_attachment_id == attachment.id,
                    ServiceReport.engineer_signature_attachment_id == attachment.id,
                )
            )
        )
        return attachment if report is not None and self._visit_has_trip(int(report)) else None

    def _visit_has_trip(self, visit_id: int) -> bool:
        found = self._session.scalar(
            select(TrkTrip.id)
            .join(TrackableActivity, TrackableActivity.id == TrkTrip.trackable_activity_id)
            .where(TrackableActivity.source_table == "service_visit", TrackableActivity.source_id == visit_id)
            .limit(1)
        )
        return found is not None

    def _attachments(self, entity_type: str, entity_id: int) -> list[Attachment]:
        return list(
            self._session.scalars(
                select(Attachment).where(
                    Attachment.entity_type == entity_type,
                    Attachment.entity_id == entity_id,
                    Attachment.is_active == True,  # noqa: E712
                )
            ).all()
        )

    @staticmethod
    def _add_document(
        documents: list[dict[str, Any]], seen: set[int], attachment: Attachment, source: str
    ) -> None:
        if attachment.id in seen:
            return
        seen.add(int(attachment.id))
        documents.append(
            {
                "id": int(attachment.id),
                "source": source,
                "file_name": attachment.file_name,
                "content_type": attachment.content_type,
                "category": attachment.category,
                "file_size_bytes": attachment.file_size_bytes,
                "verification_status": attachment.verification_status,
            }
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
            statement = statement.where(decision.in_(("Approved", "Sent", "Paid")))
        elif query.approval_status == "Rejected":
            statement = statement.where(decision == "Rejected")
        if query.settlement_status == "Paid":
            statement = statement.where(decision == "Paid")
        elif query.settlement_status == "Sent":
            statement = statement.where(decision == "Sent")
        elif query.settlement_status == "Open":
            statement = statement.where(or_(decision.is_(None), decision.notin_(("Sent", "Paid"))))
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
            Employee.mobile.label("employee_mobile"),
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
            TrackableActivity.source_table,
            TrackableActivity.source_id,
            func.coalesce(call_via_visit.id, call_direct.id).label("call_id"),
            func.coalesce(call_via_visit.call_no, call_direct.call_no).label("call_no"),
            func.coalesce(call_via_visit.complaint_description, call_direct.complaint_description).label(
                "complaint_description"
            ),
            func.coalesce(call_via_visit.oem_call_id, call_direct.oem_call_id).label("oem_call_id"),
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
                    TrackableActivity.module_code == "SVC",
                    TrackableActivity.source_table == "service_call",
                    TrackableActivity.source_id == call_direct.id,
                ),
            )
            .outerjoin(
                visit,
                and_(
                    TrackableActivity.module_code == "SVC",
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
