"""Imports a BYD service export into svc.service_call, keyed on the C4C Ticket ID (oem_call_id).

A ticket already in our system is updated; a new ticket is inserted - so re-uploading the next-stage
file (orders after requests) never creates a duplicate. Rows whose customer or machine isn't in our
masters are still imported: the call links to a placeholder customer, keeps the BYD names in
external_account_name / external_product_id, and is flagged needs_master_linking for later cleanup.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from trishul_api.auth import CurrentUser
from trishul_api.common.errors import ApiError, NotFound
from trishul_api.common.numbering import next_document_no
from trishul_api.db.models import (
    Branch,
    BydCallImport,
    Customer,
    Employee,
    LookupType,
    LookupValue,
    MachineUnit,
    Principal,
    ServiceCall,
)
from trishul_api.db.models.generated.svc import ServiceCallCurrentStatus, ServiceCallPriority
from trishul_api.modules.service.imports.parser import BydCallRow, SourceKind, parse_byd_export
from trishul_api.modules.service.imports.schemas import (
    BydImportPreview,
    BydImportResult,
    BydImportRow,
    BydImportSummary,
)

# Legal-form and connective words dropped when matching a customer name, so
# "SBB Construction Pvt. Ltd." and "SBB CONSTRUCTION PRIVATE LIMITED" match.
_LEGAL_NOISE = frozenset(
    {"PVT", "PRIVATE", "LTD", "LIMITED", "LLP", "LLC", "INC", "CORP", "CORPORATION", "CO", "COMPANY", "AND", "THE"}
)


def _normalize_name(name: str) -> str:
    """A canonical form for loose name matching: upper-cased, punctuation and legal-form words removed."""
    text = re.sub(r"\bM/?S\b\.?", " ", name.upper())  # drop a leading "M/s" / "MS"
    text = re.sub(r"[^A-Z0-9]+", " ", text)
    return " ".join(token for token in text.split() if token not in _LEGAL_NOISE)


_DEFAULT_PRINCIPAL_CODE = "TATA_HITACHI"
_CALL_SOURCE_CODE = "OEM_CUSTOMER_CARE_PER_BRAND"
_UNLINKED_CUSTOMER_CODE = "BYD-UNLINKED"
_UNLINKED_CUSTOMER_NAME = "Unidentified (BYD import)"
_PLACEHOLDER_PHONE = "0000000000"
_PRIORITIES: dict[str, ServiceCallPriority] = {"critical": "Critical", "high": "High", "normal": "Normal", "low": "Low"}


@dataclass
class _Resolution:
    action: str
    customer_id: int | None
    customer_matched: bool
    machine_id: int | None
    machine_matched: bool
    machine_expected: bool  # the row named a machine (so an unmatched one needs linking)
    engineer_id: int | None
    engineer_matched: bool
    call_type_lookup_id: int
    status: ServiceCallCurrentStatus
    priority: ServiceCallPriority
    messages: list[str] = field(default_factory=list)

    @property
    def needs_linking(self) -> bool:
        return not self.customer_matched or (self.machine_expected and not self.machine_matched)


@dataclass
class _Context:
    company_id: int
    branch_id: int
    principal_id: int
    call_source_lookup_id: int
    # caches, filled lazily
    customer_index: dict[str, int | None] | None = None  # normalized name -> id (None = ambiguous)
    machines: dict[str, int | None] = field(default_factory=dict)
    call_types: dict[str, int | None] = field(default_factory=dict)
    engineers: dict[str, int] | None = None


class BydImportService:
    def __init__(self, db: Session, actor: CurrentUser) -> None:
        self._db = db
        self._actor = actor
        self._placeholder_id: int | None = None  # the BYD-UNLINKED customer, set in _context

    def preview(self, content: bytes, file_name: str, branch_id: int, principal_id: int | None) -> BydImportPreview:
        kind, rows = parse_byd_export(content)
        ctx = self._context(branch_id, principal_id)
        seen: set[str] = set()
        outcomes: list[BydImportRow] = []
        for row in rows:
            outcomes.append(self._preview_row(row, ctx, seen))
        return BydImportPreview(summary=self._summary(kind, file_name, outcomes), rows=outcomes)

    def apply(self, content: bytes, file_name: str, branch_id: int, principal_id: int | None) -> BydImportResult:
        kind, rows = parse_byd_export(content)
        ctx = self._context(branch_id, principal_id)
        batch = BydCallImport(
            company_id=ctx.company_id,
            branch_id=ctx.branch_id,
            principal_id=ctx.principal_id,
            file_name=file_name[:260],
            source_kind=kind,
            imported_by_user_id=self._actor.id,
        )
        self._db.add(batch)
        self._db.flush()

        outcomes = [self._apply_row(row, ctx, kind, batch.id) for row in rows]
        summary = self._summary(kind, file_name, outcomes)
        batch.total_rows = summary.total
        batch.inserted_count = summary.inserts
        batch.updated_count = summary.updates
        batch.unlinked_count = summary.needs_linking
        batch.failed_count = summary.skips
        self._db.commit()
        return BydImportResult(batch_id=batch.id, summary=summary, rows=outcomes)

    # ------------------------------------------------------------------ per-row

    def _preview_row(self, row: BydCallRow, ctx: _Context, seen: set[str]) -> BydImportRow:
        if not row.c4c_ticket_id:
            return _skip(row, "No C4C Ticket ID; the row cannot be identified.")
        existing = self._find_call(ctx, row.c4c_ticket_id)
        res = self._resolve(row, ctx)
        if existing is not None or row.c4c_ticket_id in seen:
            res.action = "update"
            # For an update, what matters is whether the call is still unlinked AFTER the update,
            # not whether this file's name happened to match - the existing link is kept.
            needs = self._update_needs_linking(existing, res) if existing is not None else res.needs_linking
            call_no = existing.call_no if existing is not None else None
        else:
            res.action = "insert"
            seen.add(row.c4c_ticket_id)
            needs = res.needs_linking
            call_no = None
        return _outcome(row, res, call_no, needs)

    def _apply_row(self, row: BydCallRow, ctx: _Context, kind: SourceKind, batch_id: int) -> BydImportRow:
        if not row.c4c_ticket_id:
            return _skip(row, "No C4C Ticket ID; the row cannot be identified.")
        res = self._resolve(row, ctx)
        existing = self._find_call(ctx, row.c4c_ticket_id)
        if existing is not None:
            res.action = "update"
            self._update_call(existing, row, res, batch_id)
            call = existing
            needs = call.needs_master_linking
        else:
            res.action = "insert"
            call = self._insert_call(row, res, ctx, batch_id)
            needs = res.needs_linking
        self._db.flush()  # so a repeated ticket later in the file updates this call
        return _outcome(row, res, call.call_no, needs)

    def _update_needs_linking(self, call: ServiceCall, res: _Resolution) -> bool:
        """Will the existing call still lack a real customer or machine after this update?"""
        customer_unlinked = self._placeholder_id is not None and call.customer_id == self._placeholder_id
        has_machine = call.machine_unit_id is not None or res.machine_id is not None
        machine_unlinked = res.machine_expected and not has_machine
        return customer_unlinked or machine_unlinked

    # ------------------------------------------------------------------ resolve

    def _resolve(self, row: BydCallRow, ctx: _Context) -> _Resolution:
        messages: list[str] = []
        customer_id, customer_matched = self._match_customer(ctx, row.account)
        if not customer_matched and row.account:
            messages.append(f"Customer '{row.account}' not found; linked to the placeholder for later linking.")
        machine_id = self._match_machine(ctx, row.registered_product_id)
        machine_matched = machine_id is not None
        if not machine_matched and row.registered_product_id:
            messages.append(f"Machine '{row.registered_product_id}' not found; left unlinked.")
        engineer_id = self._match_engineer(ctx, row.engineer_name)
        engineer_matched = engineer_id is not None
        if row.engineer_name and not engineer_matched:
            messages.append(f"Engineer '{row.engineer_name}' not found; not assigned.")

        return _Resolution(
            action="insert",
            customer_id=customer_id,
            customer_matched=customer_matched,
            machine_id=machine_id,
            machine_matched=machine_matched,
            machine_expected=bool(row.registered_product_id),
            engineer_id=engineer_id,
            engineer_matched=engineer_matched,
            call_type_lookup_id=self._call_type_lookup_id(ctx, row),
            status=self._status(row, engineer_matched),
            priority=_PRIORITIES.get((row.priority or "").strip().lower(), "Normal"),
            messages=messages,
        )

    def _match_customer(self, ctx: _Context, account: str | None) -> tuple[int | None, bool]:
        if not account:
            return None, False
        key = _normalize_name(account)
        if not key:
            return None, False
        if ctx.customer_index is None:
            ctx.customer_index = {}
            for cid, name in self._db.execute(
                select(Customer.id, Customer.name).where(Customer.company_id == ctx.company_id, Customer.is_active)
            ):
                normalized = _normalize_name(name)
                if not normalized:
                    continue
                if normalized not in ctx.customer_index:
                    ctx.customer_index[normalized] = cid
                elif ctx.customer_index[normalized] != cid:
                    ctx.customer_index[normalized] = None  # two customers share a name: don't guess
        matched = ctx.customer_index.get(key)
        return (matched, True) if matched is not None else (None, False)

    def _match_machine(self, ctx: _Context, product_id: str | None) -> int | None:
        if not product_id:
            return None
        key = product_id.strip()
        if key not in ctx.machines:
            ctx.machines[key] = self._db.scalars(
                select(MachineUnit.id)
                .where(
                    (MachineUnit.oem_registered_product_id == key) | (MachineUnit.serial_number == key),
                    MachineUnit.is_active,
                )
                .limit(1)
            ).first()
        return ctx.machines[key]

    def _match_engineer(self, ctx: _Context, name: str | None) -> int | None:
        if not name:
            return None
        if ctx.engineers is None:
            ctx.engineers = {}
            for emp_id, first, last in self._db.execute(
                select(Employee.id, Employee.first_name, Employee.last_name).where(Employee.is_active)
            ):
                full = " ".join(part for part in (first, last) if part).strip().lower()
                ctx.engineers.setdefault(full, emp_id)
        return ctx.engineers.get(name.strip().lower())

    def _call_type_lookup_id(self, ctx: _Context, row: BydCallRow) -> int:
        code = _call_type_code(row)
        for candidate in (code, "BREAKDOWN"):
            if candidate not in ctx.call_types:
                ctx.call_types[candidate] = self._lookup_id("CALL_TYPE", candidate)
            found = ctx.call_types[candidate]
            if found is not None:
                return found
        raise ApiError("No 'Call type' lookup values are set up. Ask an administrator to add them.")

    # ------------------------------------------------------------------ write

    def _insert_call(self, row: BydCallRow, res: _Resolution, ctx: _Context, batch_id: int) -> ServiceCall:
        customer_id = res.customer_id if res.customer_matched else self._placeholder_customer_id(ctx)
        call = ServiceCall(
            company_id=ctx.company_id,
            branch_id=ctx.branch_id,
            principal_id=ctx.principal_id,
            call_no=next_document_no(
                self._db,
                company_id=ctx.company_id,
                document_type="SERVICE_CALL",
                branch_id=ctx.branch_id,
                principal_id=ctx.principal_id,
            ),
            call_source_lookup_id=ctx.call_source_lookup_id,
            call_type_lookup_id=res.call_type_lookup_id,
            complaint_description=(row.subject or "(no subject)")[:2000],
            customer_id=customer_id,
            caller_name=row.caller_name[:100] if row.caller_name else None,
            caller_phone=(row.caller_phone or _PLACEHOLDER_PHONE)[:15],
            machine_unit_id=res.machine_id,
            is_machine_down=row.is_breakdown,
            coverage_type="Warranty" if row.is_warranty else None,
            priority=res.priority,
            received_at=row.received_at or _now(),
            received_by_user_id=self._actor.id,
            source_reference=row.external_reference[:150] if row.external_reference else None,
            current_status=res.status,
            assigned_engineer_id=res.engineer_id,
            oem_call_id=row.c4c_ticket_id,
            sla_due_at=row.sla_due_at,
            import_batch_id=batch_id,
            external_account_name=(row.account[:200] if row.account and not res.customer_matched else None),
            external_product_id=(
                row.registered_product_id[:40] if row.registered_product_id and not res.machine_matched else None
            ),
            needs_master_linking=res.needs_linking,
            created_by_user_id=self._actor.id,
        )
        self._db.add(call)
        return call

    def _update_call(self, call: ServiceCall, row: BydCallRow, res: _Resolution, batch_id: int) -> None:
        call.priority = res.priority
        call.is_machine_down = row.is_breakdown
        if row.sla_due_at is not None:
            call.sla_due_at = row.sla_due_at
        if row.external_reference:
            call.source_reference = row.external_reference[:150]
        if res.engineer_id is not None:
            call.assigned_engineer_id = res.engineer_id
        # Advance the status without moving it backwards; honour a cancellation at any point.
        if res.status == "Cancelled":
            call.current_status = "Cancelled"
        elif call.current_status == "Logged" and res.status == "Assigned":
            call.current_status = "Assigned"
        # Fill a link that was missing before, and recompute the flag.
        if call.machine_unit_id is None and res.machine_id is not None:
            call.machine_unit_id = res.machine_id
            call.external_product_id = None
        if res.customer_matched and call.customer_id == self._placeholder_id:
            call.customer_id = res.customer_id  # type: ignore[assignment]
            call.external_account_name = None
        still_placeholder = call.customer_id == self._placeholder_id
        call.needs_master_linking = still_placeholder or (
            call.machine_unit_id is None and bool(row.registered_product_id)
        )
        call.import_batch_id = batch_id
        call.updated_at = _now()
        call.updated_by_user_id = self._actor.id

    # ------------------------------------------------------------------ context / helpers

    def _context(self, branch_id: int, principal_id: int | None) -> _Context:
        branch = self._db.get(Branch, branch_id)
        if branch is None or not branch.is_active:
            raise NotFound("Branch not found.")
        principal = self._resolve_principal(principal_id)
        source_lookup_id = self._lookup_id("CALL_SOURCE", _CALL_SOURCE_CODE)
        if source_lookup_id is None:
            raise ApiError(f"The '{_CALL_SOURCE_CODE}' call-source lookup is not set up.")
        self._placeholder_id = self._db.scalars(
            select(Customer.id).where(
                Customer.company_id == branch.company_id, Customer.code == _UNLINKED_CUSTOMER_CODE
            )
        ).first()
        return _Context(
            company_id=branch.company_id,
            branch_id=branch.id,
            principal_id=principal.id,
            call_source_lookup_id=source_lookup_id,
        )

    def _resolve_principal(self, principal_id: int | None) -> Principal:
        if principal_id is not None:
            principal = self._db.get(Principal, principal_id)
            if principal is None or not principal.is_active:
                raise NotFound("Brand not found.")
            return principal
        principal = self._db.scalars(
            select(Principal).where(Principal.code == _DEFAULT_PRINCIPAL_CODE, Principal.is_active).limit(1)
        ).first()
        if principal is None:
            raise ApiError(f"The default brand '{_DEFAULT_PRINCIPAL_CODE}' is not set up. Choose a brand to import.")
        return principal

    def _find_call(self, ctx: _Context, ticket: str) -> ServiceCall | None:
        return self._db.scalars(
            select(ServiceCall)
            .where(
                ServiceCall.oem_call_id == ticket,
                ServiceCall.company_id == ctx.company_id,
                ServiceCall.principal_id == ctx.principal_id,
            )
            .order_by(ServiceCall.id)
            .limit(1)
        ).first()

    def _placeholder_customer_id(self, ctx: _Context) -> int:
        if self._placeholder_id is not None:
            return self._placeholder_id
        customer = Customer(
            company_id=ctx.company_id,
            code=_UNLINKED_CUSTOMER_CODE,
            name=_UNLINKED_CUSTOMER_NAME,
            customer_type="Company",
            primary_phone=_PLACEHOLDER_PHONE,
            created_by_user_id=self._actor.id,
        )
        self._db.add(customer)
        self._db.flush()
        self._placeholder_id = customer.id
        return customer.id

    def _lookup_id(self, type_code: str, value_code: str) -> int | None:
        return self._db.scalars(
            select(LookupValue.id)
            .join(LookupType, LookupType.id == LookupValue.lookup_type_id)
            .where(LookupType.code == type_code, LookupValue.code == value_code, LookupValue.is_active)
            .limit(1)
        ).first()

    @staticmethod
    def _status(row: BydCallRow, engineer_matched: bool) -> ServiceCallCurrentStatus:
        if row.is_cancelled:
            return "Cancelled"
        return "Assigned" if engineer_matched else "Logged"

    @staticmethod
    def _summary(kind: str, file_name: str, outcomes: list[BydImportRow]) -> BydImportSummary:
        return BydImportSummary(
            source_kind=kind,
            file_name=file_name,
            total=len(outcomes),
            inserts=sum(o.action == "insert" for o in outcomes),
            updates=sum(o.action == "update" for o in outcomes),
            skips=sum(o.action == "skip" for o in outcomes),
            needs_linking=sum(o.needs_linking for o in outcomes),
        )


def _call_type_code(row: BydCallRow) -> str:
    text = " ".join(part for part in (row.call_type_text, row.subject) if part).lower()
    if row.is_breakdown:
        return "BREAKDOWN"
    if any(word in text for word in ("service", "hrs", "hour", "month")):
        return "PERIODIC_SERVICE"
    if any(word in text for word in ("install", "commission", "erection")):
        return "INSTALLATION"
    if "inspect" in text:
        return "INSPECTION"
    return "BREAKDOWN"


def _outcome(row: BydCallRow, res: _Resolution, call_no: str | None, needs_linking: bool) -> BydImportRow:
    return BydImportRow(
        row_number=row.row_number,
        c4c_ticket_id=row.c4c_ticket_id,
        external_reference=row.external_reference,
        subject=row.subject,
        account=row.account,
        action=res.action,
        call_no=call_no,
        customer_matched=res.customer_matched,
        machine_matched=res.machine_matched,
        engineer_matched=res.engineer_matched,
        needs_linking=needs_linking,
        messages=res.messages,
    )


def _skip(row: BydCallRow, message: str) -> BydImportRow:
    return BydImportRow(
        row_number=row.row_number,
        c4c_ticket_id=row.c4c_ticket_id,
        external_reference=row.external_reference,
        subject=row.subject,
        account=row.account,
        action="skip",
        call_no=None,
        customer_matched=False,
        machine_matched=False,
        engineer_matched=False,
        needs_linking=False,
        messages=[message],
    )


def _now() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)
