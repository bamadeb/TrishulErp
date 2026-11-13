"""Parts requests: raised from the mobile app against a service call, reviewed by the office.

Each requested part is one svc.service_part_request row:

    Requested  the engineer asked for it (channel App). An SVC_PART_REQUEST alert goes to the reviewers.
    Quoted     the office put it on a draft sales quotation (quotation_id).
    Rejected   the office won't supply it (review_note says why).

Once no part of a call is still Requested, the call's open part-request alerts are resolved.
"""

import logging
from collections.abc import Iterable
from datetime import UTC, datetime, time, timedelta
from decimal import Decimal
from typing import Any

from sqlalchemy import Select, func, or_, select
from sqlalchemy.orm import Session, aliased

from trishul_api.auth import CurrentUser, RequestScope
from trishul_api.common.errors import ApiError, Conflict, NotFound
from trishul_api.common.schemas import Page
from trishul_api.db.models import (
    AppUser,
    Branch,
    Customer,
    Employee,
    Item,
    Location,
    LotBalance,
    Principal,
    Quotation,
    ServiceCall,
    ServicePartRequest,
    ServiceVisit,
    Uom,
)
from trishul_api.modules.alerts.engine import AlertEngine
from trishul_api.modules.sal.customer_service import CustomerAccountService
from trishul_api.modules.sal.quotation_schemas import QuotationCreate
from trishul_api.modules.sal.quotation_service import QuotationService
from trishul_api.modules.service.access import FINISHED_STATUSES
from trishul_api.modules.service.assignment import assignees
from trishul_api.modules.service.parts.schemas import (
    PartAvailability,
    PartRequestCall,
    PartRequestCreate,
    PartRequestDraftLine,
    PartRequestListItem,
    PartRequestOut,
    PartRequestQuery,
    PartRequestQuotationCreate,
    PartRequestQuotationDraft,
    PartRequestQuotationOut,
    PartRequestReject,
    WarehouseStock,
)
from trishul_api.modules.service.reports.service import can_read

log = logging.getLogger(__name__)

# Who may raise a request: an engineer on the call, or the team lead who assigns it.
CAN_REQUEST_PARTS = "svc.part_request.create"
# Who sees every request and quotes or rejects them (the office / warehouse).
CAN_REVIEW_PARTS = "svc.part_request.review"
ALERT_TYPE = "SVC_PART_REQUEST"
_DEFAULT_GST = Decimal(18)
_SORTS = {"createdAt": ServicePartRequest.id, "callNo": ServiceCall.call_no, "status": ServicePartRequest.status}


def _now() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


class PartRequestService:
    def __init__(self, db: Session, actor: CurrentUser) -> None:
        self._db = db
        self._actor = actor

    # ------------------------------------------------------------------ the engineer's request

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
        self._db.flush()
        self._raise_alert(call.id, min(r.id for r in rows))
        self._db.commit()
        return [self._out(row, call, items.get(row.item_id) if row.item_id else None, uoms) for row in rows]

    def of_call(self, call_id: int) -> list[PartRequestListItem]:
        """Every part requested on a call (for the engineer's app and the call screen)."""
        call = self._db.get(ServiceCall, call_id)
        if call is None or not (self._actor.can(CAN_REVIEW_PARTS) or can_read(self._db, self._actor, call)):
            raise NotFound("Service call not found.")
        if not self._actor.can_use_branch(call.branch_id):
            raise NotFound("Service call not found.")
        statement = self._listing().where(ServicePartRequest.service_call_id == call.id)
        return [self._list_item(row) for row in self._db.execute(statement.order_by(ServicePartRequest.id))]

    def availability(self, call_id: int, item_ids: list[int]) -> list[PartAvailability]:
        """Stock of the parts for this call, in every warehouse (not only the engineer's branches)."""
        call = self._db.get(ServiceCall, call_id)
        if call is None or not (self._actor.can(CAN_REVIEW_PARTS) or can_read(self._db, self._actor, call)):
            raise NotFound("Service call not found.")
        wanted = list(dict.fromkeys(item_ids))
        items = {
            i.id: i
            for i in self._db.scalars(
                select(Item).where(
                    Item.id.in_(wanted),
                    or_(Item.principal_id.is_(None), Item.principal_id == call.principal_id),
                )
            )
        }
        missing = [i for i in wanted if i not in items]
        if missing:
            raise ApiError(
                "Some items are unknown or of another brand than the call's machine.",
                errors={"itemIds": [f"No item {i} for this call." for i in missing]},
            )
        branch = self._db.get(Branch, call.branch_id)
        supplying_id = (branch.parent_warehouse_id or branch.id) if branch else None
        home = {call.branch_id, supplying_id}
        supplying = self._db.get(Branch, supplying_id) if supplying_id else None
        # The supplying warehouse can sit under another company than the call's branch
        # (Bhadrak is under Trishul, its Bhubaneswar warehouse under Trishul Tread): count both.
        companies = {call.company_id} | ({supplying.company_id} if supplying else set())
        stock = self._db.execute(
            select(
                LotBalance.item_id,
                Branch.id.label("branch_id"),
                Branch.name.label("branch_name"),
                func.sum(LotBalance.qty_on_hand).label("qty"),
            )
            .join(Location, Location.id == LotBalance.location_id)
            .join(Branch, Branch.id == Location.branch_id)
            .where(
                LotBalance.item_id.in_(wanted),
                LotBalance.qty_on_hand > 0,
                LotBalance.is_active,
                Location.is_active,
                Location.is_stock_location,
                Branch.company_id.in_(companies),
            )
            .group_by(LotBalance.item_id, Branch.id, Branch.name)
        ).all()
        uoms = {
            u.id: u.code for u in self._db.scalars(select(Uom).where(Uom.id.in_({i.uom_id for i in items.values()})))
        }
        result: list[PartAvailability] = []
        for item_id in wanted:
            item = items[item_id]
            places = sorted(
                (
                    WarehouseStock(
                        branch_id=r.branch_id,
                        branch_name=r.branch_name,
                        qty_available=r.qty,
                        supplies_call_branch=r.branch_id in home,
                    )
                    for r in stock
                    if r.item_id == item_id
                ),
                key=lambda w: (not w.supplies_call_branch, -w.qty_available, w.branch_name),
            )
            near = sum((w.qty_available for w in places if w.supplies_call_branch), Decimal(0))
            total = sum((w.qty_available for w in places), Decimal(0))
            result.append(
                PartAvailability(
                    item_id=item.id,
                    item_code=item.item_code,
                    description=item.description,
                    uom_code=uoms.get(item.uom_id, ""),
                    supplying_warehouse_id=supplying.id if supplying else None,
                    supplying_warehouse_name=supplying.name if supplying else None,
                    qty_in_supplying_warehouse=near,
                    qty_elsewhere=total - near,
                    total_available=total,
                    warehouses=places,
                )
            )
        return result

    # ------------------------------------------------------------------ the office's review

    def search(self, scope: RequestScope, query: PartRequestQuery) -> Page[PartRequestListItem]:
        statement = self._filtered(scope, query)
        total = self._db.scalar(select(func.count()).select_from(statement.order_by(None).subquery())) or 0
        key = (query.sort or "-createdAt").lstrip("-")
        column = _SORTS.get(key, ServicePartRequest.id)
        order = column.desc() if (query.sort or "-createdAt").startswith("-") else column.asc()
        # SQL Server refuses the same column twice in ORDER BY: add the id tie-breaker only for other sorts.
        ordering = [order] if column is ServicePartRequest.id else [order, ServicePartRequest.id.desc()]
        rows = self._db.execute(
            statement.order_by(*ordering).offset((query.page - 1) * query.page_size).limit(query.page_size)
        )
        return Page(
            items=[self._list_item(row) for row in rows], total=total, page=query.page, page_size=query.page_size
        )

    def calls(self, scope: RequestScope, query: PartRequestQuery) -> Page[PartRequestCall]:
        """The same filters, grouped by call (latest request first); each call with its matching parts."""
        statement = self._filtered(scope, query)
        matching = (
            statement.order_by(None)
            .with_only_columns(ServicePartRequest.service_call_id, ServicePartRequest.id)
            .subquery()
        )
        total = self._db.scalar(select(func.count(func.distinct(matching.c.service_call_id)))) or 0
        latest = func.max(matching.c.id)
        call_ids = list(
            self._db.scalars(
                select(matching.c.service_call_id)
                .group_by(matching.c.service_call_id)
                .order_by(latest.desc())
                .offset((query.page - 1) * query.page_size)
                .limit(query.page_size)
            )
        )
        grouped: dict[int, list[PartRequestListItem]] = {call_id: [] for call_id in call_ids}
        if call_ids:
            rows = self._db.execute(
                statement.where(ServicePartRequest.service_call_id.in_(call_ids)).order_by(ServicePartRequest.id)
            )
            for row in rows:
                grouped[row.ServicePartRequest.service_call_id].append(self._list_item(row))
        return Page(
            items=[self._call(parts) for parts in grouped.values() if parts],
            total=total,
            page=query.page,
            page_size=query.page_size,
        )

    def _filtered(self, scope: RequestScope, query: PartRequestQuery) -> Select[*tuple[Any, ...]]:
        statement = self._listing()
        if scope.branch_id is not None:
            statement = statement.where(ServiceCall.branch_id == scope.branch_id)
        if scope.principal_id is not None:
            statement = statement.where(ServiceCall.principal_id == scope.principal_id)
        if query.status is not None:
            statement = statement.where(ServicePartRequest.status == query.status)
        if query.branch_id is not None:
            statement = statement.where(ServiceCall.branch_id == query.branch_id)
        if query.customer_id is not None:
            statement = statement.where(ServiceCall.customer_id == query.customer_id)
        if query.service_call_id is not None:
            statement = statement.where(ServicePartRequest.service_call_id == query.service_call_id)
        if query.from_date is not None:
            statement = statement.where(ServicePartRequest.created_at >= datetime.combine(query.from_date, time.min))
        if query.to_date is not None:
            end = datetime.combine(query.to_date + timedelta(days=1), time.min)
            statement = statement.where(ServicePartRequest.created_at < end)
        if query.search:
            like = f"%{query.search}%"
            statement = statement.where(
                or_(
                    ServiceCall.call_no.ilike(like),
                    Customer.name.ilike(like),
                    Item.item_code.ilike(like),
                    Item.oem_part_number.ilike(like),
                    ServicePartRequest.part_description.ilike(like),
                )
            )
        return statement

    @staticmethod
    def _call(parts: list[PartRequestListItem]) -> PartRequestCall:
        first = parts[0]
        needed = [p.required_by_date for p in parts if p.required_by_date is not None]
        return PartRequestCall(
            service_call_id=first.service_call_id,
            call_no=first.call_no,
            call_status=first.call_status,
            branch_id=first.branch_id,
            branch_name=first.branch_name,
            principal_id=first.principal_id,
            principal_name=first.principal_name,
            customer_id=first.customer_id,
            customer_name=first.customer_name,
            last_requested_at=max(p.created_at for p in parts),
            required_by_date=min(needed) if needed else None,
            waiting=sum(1 for p in parts if p.status == "Requested"),
            requested_by=list(dict.fromkeys(p.requested_by_name for p in parts if p.requested_by_name)),
            parts=parts,
        )

    def reject(self, part_request_id: int, data: PartRequestReject) -> PartRequestListItem:
        rows, _ = self._reviewable([part_request_id])
        now = _now()
        for row in rows:
            row.status = "Rejected"
            row.review_note = data.note
            row.reviewed_by_user_id = self._actor.id
            row.reviewed_at = now
            row.updated_at = now
            row.updated_by_user_id = self._actor.id
        self._db.flush()
        self._resolve_alerts({r.service_call_id for r in rows})
        self._db.commit()
        return self._by_ids([r.id for r in rows])[0]

    def draft(self, part_request_ids: list[int]) -> PartRequestQuotationDraft:
        """The quotation the parts would make, for the user to check and change before saving it (nothing saved).
        Prices come from the price list (else MRP, else 0) and GST from the item's HSN (else 18)."""
        rows, calls = self._quotable(part_request_ids)
        first = calls[rows[0].service_call_id]
        prices = CustomerAccountService(self._db, self._actor)
        lines: list[PartRequestDraftLine] = []
        for row in rows:
            price, gst = Decimal(0), _DEFAULT_GST
            if row.item_id is not None:
                info = prices.item_info(row.item_id, first.principal_id)
                price = info.price if info.price is not None else (info.mrp or Decimal(0))
                gst = info.gst_pct if info.gst_pct is not None else _DEFAULT_GST
            lines.append(
                PartRequestDraftLine(
                    part_request_id=row.id,
                    item_id=row.item_id,
                    description=row.part_description,
                    quantity=row.quantity,
                    unit_price=price,
                    discount_pct=Decimal(0),
                    gst_pct=gst,
                )
            )
        call_nos = sorted({c.call_no for c in calls.values()})
        return PartRequestQuotationDraft(
            part_request_ids=[r.id for r in rows],
            call_nos=call_nos,
            customer_id=first.customer_id,
            principal_id=first.principal_id,
            branch_id=first.branch_id,
            remarks=f"Parts requested on service call {', '.join(call_nos)}"[:500],
            lines=lines,
        )

    def quote(self, data: PartRequestQuotationCreate) -> PartRequestQuotationOut:
        """Save the quotation the user checked; the parts it quotes become Quoted."""
        rows, calls = self._quotable(data.part_request_ids)
        first = calls[rows[0].service_call_id]
        if (data.customer_id, data.principal_id) != (first.customer_id, first.principal_id):
            raise ApiError(
                "The quotation must be for the customer and brand of the service call.",
                errors={"customerId": [f"The parts are for {first.call_no}'s customer and brand."]},
            )
        now = _now()
        # Marked first so the quotation's commit saves both, and a second reviewer quoting the same parts at
        # the same time fails on the row version instead of quoting them twice.
        for row in rows:
            row.status = "Quoted"
            row.reviewed_by_user_id = self._actor.id
            row.reviewed_at = now
            row.updated_at = now
            row.updated_by_user_id = self._actor.id
        self._db.flush()
        quotation = QuotationService(self._db, self._actor).create(
            QuotationCreate.model_validate(data.model_dump(exclude={"part_request_ids"}))
        )
        for row in rows:
            row.quotation_id = quotation.id
        self._resolve_alerts(set(calls))
        self._db.commit()
        return PartRequestQuotationOut(
            quotation_id=quotation.id, quotation_no=quotation.quotation_no, parts=self._by_ids([r.id for r in rows])
        )

    # ------------------------------------------------------------------ checks

    def _writable_call(self, call_id: int) -> ServiceCall:
        call = self._db.get(ServiceCall, call_id)
        if call is None or not can_read(self._db, self._actor, call):
            raise NotFound("Service call not found.")
        on_call = self._actor.employee_id is not None and self._actor.employee_id in assignees(self._db, call)
        if not (on_call or self._actor.can("svc.call.assign")):
            raise NotFound("Service call not found, or not assigned to you.")
        return call

    def _reviewable(self, ids: list[int]) -> tuple[list[ServicePartRequest], dict[int, ServiceCall]]:
        wanted = list(dict.fromkeys(ids))
        rows = {r.id: r for r in self._db.scalars(select(ServicePartRequest).where(ServicePartRequest.id.in_(wanted)))}
        calls = {
            c.id: c
            for c in self._db.scalars(
                select(ServiceCall).where(ServiceCall.id.in_({r.service_call_id for r in rows.values()}))
            )
        }
        missing = [
            i
            for i in wanted
            if i not in rows or not rows[i].is_active or not self._sees(calls[rows[i].service_call_id])
        ]
        if missing:
            raise NotFound(f"Part request not found: {', '.join(map(str, missing))}.")
        done = [i for i in wanted if rows[i].status != "Requested"]
        if done:
            raise Conflict(
                "Some parts were already reviewed: "
                + ", ".join(f"{i} ({rows[i].status})" for i in done)
                + ". Reload the list."
            )
        return [rows[i] for i in wanted], calls

    def _quotable(self, ids: list[int]) -> tuple[list[ServicePartRequest], dict[int, ServiceCall]]:
        """Waiting parts that fit on one quotation: one customer and brand."""
        rows, calls = self._reviewable(ids)
        first = calls[rows[0].service_call_id]
        if any((c.customer_id, c.principal_id) != (first.customer_id, first.principal_id) for c in calls.values()):
            raise ApiError(
                "One quotation is for one customer and brand; these parts are from calls that differ.",
                errors={"partRequestIds": ["Choose parts of one customer and brand."]},
            )
        return rows, calls

    def _sees(self, call: ServiceCall) -> bool:
        return self._actor.can_use_branch(call.branch_id) and self._actor.can_see_principal(call.principal_id)

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

    # ------------------------------------------------------------------ alerts

    def _raise_alert(self, call_id: int, first_request_id: int) -> None:
        """Raised in the same transaction; a failure here never blocks saving the request."""
        try:
            with self._db.begin_nested():
                AlertEngine(self._db).raise_event(ALERT_TYPE, call_id, first_request_id)
        except Exception:
            log.exception("Raising %s alerts for call %s failed", ALERT_TYPE, call_id)

    def _resolve_alerts(self, call_ids: Iterable[int]) -> None:
        try:
            with self._db.begin_nested():
                AlertEngine(self._db).resolve_reviewed_parts(call_ids)
        except Exception:
            log.exception("Resolving %s alerts failed", ALERT_TYPE)

    # ------------------------------------------------------------------ output

    def _listing(self) -> Select[*tuple[Any, ...]]:
        requester, reviewer = aliased(Employee), aliased(AppUser)
        reviewer_employee = aliased(Employee)
        statement: Select[*tuple[Any, ...]] = (
            select(
                ServicePartRequest,
                ServiceCall.call_no,
                ServiceCall.current_status.label("call_status"),
                ServiceCall.branch_id,
                ServiceCall.principal_id,
                ServiceCall.customer_id,
                Branch.name.label("branch_name"),
                Principal.name.label("principal_name"),
                Customer.name.label("customer_name"),
                Item.item_code,
                Item.oem_part_number,
                Uom.code.label("uom_code"),
                requester.first_name.label("req_first"),
                requester.last_name.label("req_last"),
                Quotation.quotation_no,
                reviewer.username.label("rev_username"),
                reviewer_employee.first_name.label("rev_first"),
                reviewer_employee.last_name.label("rev_last"),
            )
            .join(ServiceCall, ServiceCall.id == ServicePartRequest.service_call_id)
            .join(Branch, Branch.id == ServiceCall.branch_id)
            .join(Principal, Principal.id == ServiceCall.principal_id)
            .join(Customer, Customer.id == ServiceCall.customer_id)
            .outerjoin(Item, Item.id == ServicePartRequest.item_id)
            .outerjoin(Uom, Uom.id == ServicePartRequest.uom_id)
            .outerjoin(requester, requester.id == ServicePartRequest.requested_by_employee_id)
            .outerjoin(Quotation, Quotation.id == ServicePartRequest.quotation_id)
            .outerjoin(reviewer, reviewer.id == ServicePartRequest.reviewed_by_user_id)
            .outerjoin(reviewer_employee, reviewer_employee.id == reviewer.employee_id)
            .where(ServicePartRequest.is_active)
        )
        if self._actor.branch_ids is not None:
            statement = statement.where(ServiceCall.branch_id.in_(self._actor.branch_ids))
        if self._actor.principal_ids is not None:
            statement = statement.where(ServiceCall.principal_id.in_(self._actor.principal_ids))
        return statement

    def _by_ids(self, ids: list[int]) -> list[PartRequestListItem]:
        rows = self._db.execute(self._listing().where(ServicePartRequest.id.in_(ids)).order_by(ServicePartRequest.id))
        return [self._list_item(row) for row in rows]

    @staticmethod
    def _name(first: str | None, last: str | None, fallback: str | None = None) -> str | None:
        return " ".join(p for p in (first, last) if p) or fallback

    def _list_item(self, r: Any) -> PartRequestListItem:
        part: ServicePartRequest = r.ServicePartRequest
        return PartRequestListItem(
            id=part.id,
            service_call_id=part.service_call_id,
            call_no=r.call_no,
            service_visit_id=part.service_visit_id,
            item_id=part.item_id,
            item_code=r.item_code,
            oem_part_number=r.oem_part_number,
            part_description=part.part_description,
            quantity=part.quantity,
            uom_id=part.uom_id,
            uom_code=r.uom_code,
            is_chargeable=part.is_chargeable,
            status=part.status,
            request_channel=part.request_channel,
            requested_by_employee_id=part.requested_by_employee_id,
            required_by_date=part.required_by_date,
            created_at=part.created_at,
            branch_id=r.branch_id,
            branch_name=r.branch_name,
            principal_id=r.principal_id,
            principal_name=r.principal_name,
            customer_id=r.customer_id,
            customer_name=r.customer_name,
            call_status=r.call_status,
            requested_by_name=self._name(r.req_first, r.req_last),
            quotation_id=part.quotation_id,
            quotation_no=r.quotation_no,
            review_note=part.review_note,
            reviewed_at=part.reviewed_at,
            reviewed_by=self._name(r.rev_first, r.rev_last, r.rev_username),
        )

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
