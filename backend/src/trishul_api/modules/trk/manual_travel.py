"""Manual travel: kilometres entered by hand for vehicles that have no GPS trip (Bus, Train, Other).

Separate from the GPS trip workflow on purpose (no start/stop, no trail), but linked the same way: to a
service call and to the engineer. Supporting tickets are documents of the common document module,
registered below as the 'trk.manual_travel' target.
"""

from datetime import UTC, date, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from trishul_api.auth import CurrentUser
from trishul_api.common.concurrency import check_row_version
from trishul_api.common.errors import ApiError, Forbidden, NotFound
from trishul_api.db.models import Attachment, Employee, ServiceCall, TrkManualTravel
from trishul_api.modules.core.documents import storage
from trishul_api.modules.core.documents.registry import DocumentTarget, register_target
from trishul_api.modules.service.assignment import assignees
from trishul_api.modules.trk.master_service import InvalidMasterValue, TripMasterService
from trishul_api.modules.trk.schemas import ManualTravelInput, ManualTravelOut, ManualTravelUpdate

ENTITY_TYPE = "trk.manual_travel"
REVIEW_PERMISSIONS = ("trk.trip.view.team", "trk.trip.adjust")
# An engineer in India records travel on the day or the next morning; allow one day ahead of UTC.
_FUTURE_TOLERANCE = timedelta(days=1)
_MAX_AGE = timedelta(days=90)


def _reviews(user: CurrentUser) -> bool:
    return user.can(*REVIEW_PERMISSIONS)


def _visible(db: Session, user: CurrentUser, travel_id: int) -> TrkManualTravel | None:
    row = db.get(TrkManualTravel, travel_id)
    if row is None or not row.is_active:
        return None
    if row.employee_id == user.employee_id and user.employee_id is not None:
        return row
    if _reviews(user):
        call = db.get(ServiceCall, row.service_call_id)
        if call is not None and user.can_use_branch(call.branch_id):
            return row
    return None


def _can_view(db: Session, user: CurrentUser, travel_id: int) -> bool:
    return _visible(db, user, travel_id) is not None


def _can_edit(db: Session, user: CurrentUser, travel_id: int) -> bool:
    row = _visible(db, user, travel_id)
    return (
        row is not None
        and user.employee_id is not None
        and row.employee_id == user.employee_id
        and user.can("trk.trip.manage")
    )


register_target(DocumentTarget(entity_type=ENTITY_TYPE, can_view=_can_view, can_edit=_can_edit))


class ManualTravelService:
    def __init__(self, db: Session) -> None:
        self._db = db
        self._master = TripMasterService(db)

    # ------------------------------------------------------------------ writes

    def create(self, user: CurrentUser, data: ManualTravelInput) -> ManualTravelOut:
        if user.employee_id is None:
            raise NotFound("Your account is not linked to an employee, so it cannot record travel.")
        if data.client_uuid is not None:
            existing = self._db.scalar(select(TrkManualTravel).where(TrkManualTravel.client_uuid == data.client_uuid))
            if existing is not None:  # idempotent: a retried save returns the same entry
                return self._out(existing, user)
        call = self._db.get(ServiceCall, data.service_call_id)
        if call is None or not call.is_active or user.employee_id not in assignees(self._db, call):
            raise NotFound("Service call not found, or not assigned to you.")
        self._check_values(data.vehicle_type, data.travel_date)
        row = TrkManualTravel(
            service_call_id=call.id,
            employee_id=user.employee_id,
            vehicle_type=data.vehicle_type,
            travel_date=data.travel_date,
            distance_km=data.distance_km,
            notes=data.notes,
            client_uuid=data.client_uuid,
            created_by_user_id=user.id,
        )
        self._db.add(row)
        self._db.commit()
        return self._out(row, user)

    def update(
        self, user: CurrentUser, travel_id: int, row_version: bytes, data: ManualTravelUpdate
    ) -> ManualTravelOut:
        row = self._own(user, travel_id)
        check_row_version(row.row_version, row_version)
        self._check_values(data.vehicle_type, data.travel_date)
        row.vehicle_type = data.vehicle_type
        row.travel_date = data.travel_date
        row.distance_km = data.distance_km
        row.notes = data.notes
        row.updated_by_user_id = user.id
        self._db.commit()
        return self._out(row, user)

    def delete(self, user: CurrentUser, travel_id: int, row_version: bytes) -> None:
        """Soft delete; the entry's documents go with it (their rows stay for the audit trail)."""
        row = self._own(user, travel_id)
        check_row_version(row.row_version, row_version)
        row.is_active = False
        row.updated_by_user_id = user.id
        documents = self._db.scalars(
            select(Attachment).where(
                Attachment.entity_type == ENTITY_TYPE, Attachment.entity_id == row.id, Attachment.is_active
            )
        ).all()
        for document in documents:
            document.is_active = False
            document.updated_by_user_id = user.id
        self._db.commit()
        for document in documents:
            storage.remove(document.s3_key)

    # ------------------------------------------------------------------ reads

    def get(self, user: CurrentUser, travel_id: int) -> ManualTravelOut:
        row = _visible(self._db, user, travel_id)
        if row is None:
            raise NotFound("Travel entry not found.")
        return self._out(row, user)

    def for_call(self, user: CurrentUser, call_id: int) -> list[ManualTravelOut]:
        """A call's manual travel: everyone's for a reviewer in the call's branch, otherwise your own."""
        call = self._db.get(ServiceCall, call_id)
        if call is None or not call.is_active or not user.can_use_branch(call.branch_id):
            raise NotFound("Service call not found.")
        statement = select(TrkManualTravel).where(TrkManualTravel.service_call_id == call_id, TrkManualTravel.is_active)
        if not _reviews(user):
            if user.employee_id is None:
                return []
            statement = statement.where(TrkManualTravel.employee_id == user.employee_id)
        rows = self._db.scalars(statement.order_by(TrkManualTravel.travel_date, TrkManualTravel.id)).all()
        return self._outs(rows, user)

    # ------------------------------------------------------------------ helpers

    def _own(self, user: CurrentUser, travel_id: int) -> TrkManualTravel:
        row = _visible(self._db, user, travel_id)
        if row is None:
            raise NotFound("Travel entry not found.")
        if row.employee_id != user.employee_id:
            raise Forbidden("Only the engineer who recorded this travel can change it.")
        return row

    def _check_values(self, vehicle_type: str, travel_date: date) -> None:
        errors: dict[str, list[str]] = {}
        problem = self._master.manual_vehicle_problem(vehicle_type)
        if problem:
            errors["vehicleType"] = [problem]
        today = datetime.now(UTC).date()
        if travel_date > today + _FUTURE_TOLERANCE:
            errors["travelDate"] = ["The travel date cannot be in the future."]
        elif travel_date < today - _MAX_AGE:
            errors["travelDate"] = ["The travel date is more than 90 days ago."]
        if errors:
            raise InvalidMasterValue("One or more values are not valid for this travel entry.", errors)

    def _out(self, row: TrkManualTravel, user: CurrentUser) -> ManualTravelOut:
        return self._outs([row], user)[0]

    def _outs(
        self, rows: list[TrkManualTravel] | tuple[TrkManualTravel, ...], user: CurrentUser
    ) -> list[ManualTravelOut]:
        if not rows:
            return []
        ids = [r.id for r in rows]
        counts = {
            entity_id: total
            for entity_id, total in self._db.execute(
                select(Attachment.entity_id, func.count())
                .where(Attachment.entity_type == ENTITY_TYPE, Attachment.entity_id.in_(ids), Attachment.is_active)
                .group_by(Attachment.entity_id)
            )
        }
        names = {
            e.id: " ".join(p for p in (e.first_name, e.last_name) if p) or None
            for e in self._db.scalars(select(Employee).where(Employee.id.in_({r.employee_id for r in rows})))
        }
        return [
            ManualTravelOut(
                id=r.id,
                service_call_id=r.service_call_id,
                employee_id=r.employee_id,
                employee_name=names.get(r.employee_id),
                vehicle_type=r.vehicle_type,
                travel_date=r.travel_date,
                distance_km=r.distance_km,
                notes=r.notes,
                document_count=counts.get(r.id, 0),
                can_edit=r.employee_id == user.employee_id and user.can("trk.trip.manage"),
                created_at=r.created_at,
                row_version=r.row_version,
            )
            for r in rows
        ]


__all__ = ["ENTITY_TYPE", "ApiError", "ManualTravelService"]
