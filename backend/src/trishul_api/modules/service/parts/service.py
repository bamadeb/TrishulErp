"""Parts requests raised from the mobile app against a service call.

Each requested part is one svc.service_part_request row in status Requested (channel App). The office
reviews them later and turns them into a sales quotation (quotation_id); that step is not built yet.
"""

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from trishul_api.auth import CurrentUser
from trishul_api.common.errors import ApiError, NotFound
from trishul_api.db.models import Item, ServiceCall, ServicePartRequest, ServiceVisit, Uom
from trishul_api.modules.service.access import FINISHED_STATUSES
from trishul_api.modules.service.assignment import assignees
from trishul_api.modules.service.parts.schemas import PartRequestCreate, PartRequestOut
from trishul_api.modules.service.reports.service import can_read

# Who may raise a request: an engineer on the call, or the team lead who assigns it.
CAN_REQUEST_PARTS = "svc.part_request.create"


def _now() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


class PartRequestService:
    def __init__(self, db: Session, actor: CurrentUser) -> None:
        self._db = db
        self._actor = actor

    def create(self, call_id: int, data: PartRequestCreate) -> list[PartRequestOut]:
        call = self._writable_call(call_id)
        if call.current_status in FINISHED_STATUSES:
            raise ApiError(f"This call is {call.current_status}; parts can no longer be requested on it.")
        if data.service_visit_id is not None:
            visit = self._db.get(ServiceVisit, data.service_visit_id)
            if visit is None or not visit.is_active or visit.service_call_id != call.id:
                raise ApiError(
                    "That visit is not part of this call.", errors={"serviceVisitId": ["Not a visit of this call."]}
                )

        items = self._items({p.item_id for p in data.parts if p.item_id is not None}, call, data)
        unit_of = {
            index: part.uom_id or (items[part.item_id].uom_id if part.item_id is not None else None)
            for index, part in enumerate(data.parts)
        }
        uoms = self._uoms({u for u in unit_of.values() if u is not None})

        now = _now()
        rows: list[ServicePartRequest] = []
        for index, part in enumerate(data.parts):
            item = items.get(part.item_id) if part.item_id is not None else None
            row = ServicePartRequest(
                service_call_id=call.id,
                service_visit_id=data.service_visit_id,
                item_id=item.id if item else None,
                part_description=part.part_description or (item.description if item else None),
                quantity=part.quantity,
                uom_id=unit_of[index],
                is_chargeable=part.is_chargeable,
                status="Requested",
                request_channel="App",
                requested_by_employee_id=self._actor.employee_id,
                required_by_date=data.required_by_date,
                created_at=now,
                created_by_user_id=self._actor.id,
                is_active=True,
            )
            self._db.add(row)
            rows.append(row)
        self._db.commit()
        return [self._out(row, call, items.get(row.item_id) if row.item_id else None, uoms) for row in rows]

    # ------------------------------------------------------------------ checks

    def _writable_call(self, call_id: int) -> ServiceCall:
        call = self._db.get(ServiceCall, call_id)
        if call is None or not can_read(self._db, self._actor, call):
            raise NotFound("Service call not found.")
        on_call = self._actor.employee_id is not None and self._actor.employee_id in assignees(self._db, call)
        if not (on_call or self._actor.can("svc.call.assign")):
            raise NotFound("Service call not found, or not assigned to you.")
        return call

    def _items(self, ids: set[int], call: ServiceCall, data: PartRequestCreate) -> dict[int, Item]:
        if not ids:
            return {}
        found = {i.id: i for i in self._db.scalars(select(Item).where(Item.id.in_(ids)))}
        errors: dict[str, list[str]] = {}
        for index, part in enumerate(data.parts):
            if part.item_id is None:
                continue
            item = found.get(part.item_id)
            if item is None or not item.is_active:
                errors[f"parts[{index}].itemId"] = ["No such item, or it is inactive."]
            elif item.principal_id is not None and item.principal_id != call.principal_id:
                errors[f"parts[{index}].itemId"] = ["This part belongs to another brand than the call's machine."]
        if errors:
            raise ApiError("Some of the parts can't be requested on this call.", errors=errors)
        return found

    def _uoms(self, ids: set[int]) -> dict[int, Uom]:
        if not ids:
            return {}
        found = {u.id: u for u in self._db.scalars(select(Uom).where(Uom.id.in_(ids)))}
        missing = sorted(i for i in ids if i not in found or not found[i].is_active)
        if missing:
            raise ApiError(
                "Unknown unit of measure.", errors={"uomId": [f"No active unit with id {i}." for i in missing]}
            )
        return found

    # ------------------------------------------------------------------ output

    @staticmethod
    def _out(row: ServicePartRequest, call: ServiceCall, item: Item | None, uoms: dict[int, Uom]) -> PartRequestOut:
        uom = uoms.get(row.uom_id) if row.uom_id is not None else None
        return PartRequestOut(
            id=row.id,
            service_call_id=row.service_call_id,
            call_no=call.call_no,
            service_visit_id=row.service_visit_id,
            item_id=row.item_id,
            item_code=item.item_code if item else None,
            oem_part_number=item.oem_part_number if item else None,
            part_description=row.part_description,
            quantity=row.quantity,
            uom_id=row.uom_id,
            uom_code=uom.code if uom else None,
            is_chargeable=row.is_chargeable,
            status=row.status,
            request_channel=row.request_channel,
            requested_by_employee_id=row.requested_by_employee_id,
            required_by_date=row.required_by_date,
            created_at=row.created_at,
        )
