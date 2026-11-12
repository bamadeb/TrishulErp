"""The condition behind each alert type: which business records match a rule right now.

A scheduled type returns every record that currently meets its condition. The engine raises an alert for new
matches and resolves open alerts whose record no longer matches, so "automatic resolution" is the same query
looked at the other way. The event type (call reopened) builds its record when the event happens; its open
alerts are resolved once the call is finished again.

Every query is narrowed to the rule's company and, if set, its brand and branch. Times are naive UTC, as stored.
"""

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Any

from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session

from trishul_api.db.models import (
    CallStatusLog,
    Customer,
    Item,
    MachineModel,
    MachineUnit,
    ServiceCall,
    ServiceContract,
    ServicePartRequest,
)
from trishul_api.modules.alerts.catalogue import OPEN_STATUSES
from trishul_api.modules.service import sla
from trishul_api.modules.service.access import FINISHED_STATUSES

_FINISHED = tuple(sorted(FINISHED_STATUSES))


@dataclass(frozen=True)
class Scope:
    company_id: int
    principal_id: int | None = None
    branch_id: int | None = None


@dataclass(frozen=True)
class Candidate:
    """A business record that matches a rule: what the alert says, and who it is about."""

    entity_type: str
    entity_id: int
    dedupe_key: str
    company_id: int
    principal_id: int | None
    branch_id: int | None
    title: str
    message: str
    assigned_engineer_id: int | None = None
    logged_by_user_id: int | None = None
    sla_rule_id: int | None = None
    sla_event_type: str | None = None  # svc.sla_event: Warning / Breached


# ------------------------------------------------------------------ service calls


def _last_change() -> Any:
    """When each call last changed status (svc.call_status_log)."""
    return (
        select(CallStatusLog.service_call_id, func.max(CallStatusLog.changed_at).label("changed_at"))
        .group_by(CallStatusLog.service_call_id)
        .subquery()
    )


def _calls(scope: Scope, params: dict[str, Any]) -> Select[*tuple[Any, ...]]:
    """Open calls in the rule's scope, with the columns every call alert needs."""
    last = _last_change()
    statement = (
        select(
            ServiceCall.id,
            ServiceCall.call_no,
            ServiceCall.company_id,
            ServiceCall.principal_id,
            ServiceCall.branch_id,
            ServiceCall.assigned_engineer_id,
            ServiceCall.received_by_user_id,
            ServiceCall.received_at,
            ServiceCall.priority,
            ServiceCall.current_status,
            ServiceCall.call_type_lookup_id,
            ServiceCall.sla_due_at,
            ServiceCall.reopen_count,
            func.coalesce(last.c.changed_at, ServiceCall.received_at).label("status_since"),
            Customer.name.label("customer_name"),
        )
        .join(Customer, Customer.id == ServiceCall.customer_id)
        .outerjoin(last, last.c.service_call_id == ServiceCall.id)
        .where(
            ServiceCall.is_active,
            ServiceCall.current_status.not_in(_FINISHED),
            ServiceCall.company_id == scope.company_id,
        )
    )
    if scope.principal_id is not None:
        statement = statement.where(ServiceCall.principal_id == scope.principal_id)
    if scope.branch_id is not None:
        statement = statement.where(ServiceCall.branch_id == scope.branch_id)
    if params.get("priorities"):
        statement = statement.where(ServiceCall.priority.in_(params["priorities"]))
    return statement.order_by(ServiceCall.id)


def _call_candidate(row: Any, key_suffix: str, title: str, message: str, **extra: Any) -> Candidate:
    return Candidate(
        entity_type="svc.service_call",
        entity_id=row.id,
        dedupe_key=f"svc.service_call:{row.id}{key_suffix}",
        company_id=row.company_id,
        principal_id=row.principal_id,
        branch_id=row.branch_id,
        title=title,
        message=message,
        assigned_engineer_id=row.assigned_engineer_id,
        logged_by_user_id=row.received_by_user_id,
        **extra,
    )


def _duration(delta: timedelta) -> str:
    minutes = max(int(delta.total_seconds() // 60), 0)
    days, rest = divmod(minutes, 24 * 60)
    hours, mins = divmod(rest, 60)
    if days:
        return f"{days} d {hours} h" if hours else f"{days} d"
    if hours:
        return f"{hours} h {mins} min" if mins else f"{hours} h"
    return f"{mins} min"


def call_unassigned(db: Session, scope: Scope, params: dict[str, Any], now: datetime) -> list[Candidate]:
    cutoff = now - timedelta(minutes=params["afterMinutes"])
    statement = _calls(scope, params).where(
        ServiceCall.assigned_engineer_id.is_(None), ServiceCall.received_at <= cutoff
    )
    if params.get("machineDownOnly"):
        statement = statement.where(ServiceCall.is_machine_down)
    return [
        _call_candidate(
            row,
            "",
            f"{row.call_no} not assigned",
            f"{row.call_no} for {row.customer_name} ({row.priority}) has no engineer "
            f"{_duration(now - row.received_at)} after it was logged.",
        )
        for row in db.execute(statement)
    ]


def sla_due(db: Session, scope: Scope, params: dict[str, Any], now: datetime) -> list[Candidate]:
    stages = set(params["stages"])
    rules = sla.active_rules(db, scope.company_id)
    found: list[Candidate] = []
    for row in db.execute(_calls(scope, params).where(ServiceCall.sla_due_at.is_not(None))):
        target = sla.match_rule(
            rules,
            company_id=row.company_id,
            principal_id=row.principal_id,
            call_type_lookup_id=row.call_type_lookup_id,
            priority=row.priority,
        )
        warn = target.warn_before_minutes if target else sla.DEFAULT_WARN_BEFORE_MINUTES
        due: datetime = row.sla_due_at
        due_text = due.strftime("%d %b %Y %H:%M") + " UTC"
        rule_id = target.rule_id if target else None
        if now >= due:
            if "Breached" in stages:
                found.append(
                    _call_candidate(
                        row,
                        ":breached",
                        f"SLA breached: {row.call_no}",
                        f"{row.call_no} for {row.customer_name} passed its SLA due time ({due_text}) "
                        f"{_duration(now - due)} ago. Status: {row.current_status}.",
                        sla_rule_id=rule_id,
                        sla_event_type="Breached",
                    )
                )
        elif now >= due - timedelta(minutes=warn) and "Due soon" in stages:
            found.append(
                _call_candidate(
                    row,
                    ":due-soon",
                    f"SLA due soon: {row.call_no}",
                    f"{row.call_no} for {row.customer_name} is due by {due_text} "
                    f"(in {_duration(due - now)}). Status: {row.current_status}.",
                    sla_rule_id=rule_id,
                    sla_event_type="Warning",
                )
            )
    return found


def status_stale(db: Session, scope: Scope, params: dict[str, Any], now: datetime) -> list[Candidate]:
    cutoff = now - timedelta(hours=params["afterHours"])
    statuses = params.get("statuses") or list(OPEN_STATUSES)
    statement = _calls(scope, params).where(ServiceCall.current_status.in_(statuses))
    found = []
    for row in db.execute(statement):
        if row.status_since > cutoff:
            continue
        found.append(
            _call_candidate(
                row,
                f":{row.current_status}",
                f"{row.call_no} stuck in {row.current_status}",
                f"{row.call_no} for {row.customer_name} has been '{row.current_status}' for "
                f"{_duration(now - row.status_since)}.",
            )
        )
    return found


def awaiting_parts(db: Session, scope: Scope, params: dict[str, Any], now: datetime) -> list[Candidate]:
    cutoff = now - timedelta(days=params["afterDays"])
    statement = _calls(scope, params).where(ServiceCall.current_status == "Awaiting parts")
    return [
        _call_candidate(
            row,
            "",
            f"{row.call_no} waiting for parts",
            f"{row.call_no} for {row.customer_name} has been waiting for parts for "
            f"{_duration(now - row.status_since)}.",
        )
        for row in db.execute(statement)
        if row.status_since <= cutoff
    ]


def call_reopened(db: Session, scope: Scope, params: dict[str, Any], call_id: int | None = None) -> list[Candidate]:
    """The reopened call (event), or for a Test Rule preview every call currently in 'Reopened'."""
    statement = _calls(scope, params)
    statement = (
        statement.where(ServiceCall.id == call_id)
        if call_id is not None
        else statement.where(ServiceCall.current_status == "Reopened")
    )
    return [
        _call_candidate(
            row,
            f":reopen-{row.reopen_count or 0}",
            f"{row.call_no} reopened",
            f"{row.call_no} for {row.customer_name} was reopened"
            + (f" (reopen no. {row.reopen_count})." if row.reopen_count else "."),
        )
        for row in db.execute(statement)
    ]


def part_requested(
    db: Session, scope: Scope, params: dict[str, Any], call_id: int | None = None, first_request_id: int | None = None
) -> list[Candidate]:
    """The parts just requested on a call (event: the request's rows from first_request_id on), or for a Test
    Rule preview every open call with parts still waiting for review."""
    statement = _calls(scope, params)
    if call_id is not None:
        statement = statement.where(ServiceCall.id == call_id)
    rows = list(db.execute(statement))
    if not rows:
        return []
    parts = (
        select(
            ServicePartRequest.id,
            ServicePartRequest.service_call_id,
            ServicePartRequest.quantity,
            ServicePartRequest.part_description,
            Item.item_code,
        )
        .outerjoin(Item, Item.id == ServicePartRequest.item_id)
        .where(
            ServicePartRequest.service_call_id.in_([r.id for r in rows]),
            ServicePartRequest.is_active,
            ServicePartRequest.status == "Requested",
        )
        .order_by(ServicePartRequest.id)
    )
    if first_request_id is not None:
        parts = parts.where(ServicePartRequest.id >= first_request_id)
    by_call: dict[int, list[Any]] = {}
    for part in db.execute(parts):
        by_call.setdefault(part.service_call_id, []).append(part)
    found: list[Candidate] = []
    for row in rows:
        requested = by_call.get(row.id)
        if not requested:
            continue
        names = [f"{p.item_code or p.part_description} x {p.quantity.normalize():f}" for p in requested[:5]]
        more = f" and {len(requested) - 5} more" if len(requested) > 5 else ""
        count = f"{len(requested)} part{'s' if len(requested) != 1 else ''}"
        found.append(
            _call_candidate(
                row,
                f":parts-{requested[0].id}",
                f"Parts requested on {row.call_no}",
                f"{count} requested on {row.call_no} for {row.customer_name}: {', '.join(names)}{more}.",
            )
        )
    return found


def calls_with_requested_parts(db: Session, call_ids: Iterable[int]) -> set[int]:
    """Of these calls, the ones with parts still waiting for review (status Requested)."""
    ids = list(call_ids)
    if not ids:
        return set()
    return set(
        db.scalars(
            select(ServicePartRequest.service_call_id)
            .distinct()
            .where(
                ServicePartRequest.service_call_id.in_(ids),
                ServicePartRequest.is_active,
                ServicePartRequest.status == "Requested",
            )
        )
    )


def open_call_ids(db: Session, call_ids: Iterable[int]) -> set[int]:
    """Of these calls, the ones still open (an event alert on a finished call is resolved)."""
    ids = list(call_ids)
    if not ids:
        return set()
    return set(
        db.scalars(
            select(ServiceCall.id).where(
                ServiceCall.id.in_(ids), ServiceCall.is_active, ServiceCall.current_status.not_in(_FINISHED)
            )
        )
    )


# ------------------------------------------------------------------ machines and contracts


def coverage_expiry(db: Session, scope: Scope, params: dict[str, Any], now: datetime) -> list[Candidate]:
    today: date = now.date()
    last_day = today + timedelta(days=params["daysBefore"])
    found: list[Candidate] = []
    if "Warranty" in params["coverage"]:
        statement = (
            select(
                MachineUnit.id,
                MachineUnit.serial_number,
                MachineUnit.principal_id,
                MachineUnit.sold_by_branch_id,
                MachineUnit.warranty_end_date,
                MachineModel.model_name,
                Customer.name.label("customer_name"),
                Customer.company_id,
            )
            .join(MachineModel, MachineModel.id == MachineUnit.model_id)
            .join(Customer, Customer.id == MachineUnit.customer_id)
            .where(
                MachineUnit.is_active,
                MachineUnit.warranty_end_date >= today,
                MachineUnit.warranty_end_date <= last_day,
                Customer.company_id == scope.company_id,
            )
            .order_by(MachineUnit.id)
        )
        if scope.principal_id is not None:
            statement = statement.where(MachineUnit.principal_id == scope.principal_id)
        if scope.branch_id is not None:
            statement = statement.where(MachineUnit.sold_by_branch_id == scope.branch_id)
        for row in db.execute(statement):
            end: date = row.warranty_end_date
            found.append(
                Candidate(
                    entity_type="core.machine_unit",
                    entity_id=row.id,
                    dedupe_key=f"core.machine_unit:{row.id}:warranty:{end.isoformat()}",
                    company_id=row.company_id,
                    principal_id=row.principal_id,
                    branch_id=row.sold_by_branch_id,
                    title=f"Warranty ending: {row.serial_number}",
                    message=f"{row.model_name} {row.serial_number} of {row.customer_name}: warranty ends on "
                    f"{end.strftime('%d %b %Y')} ({(end - today).days} days).",
                )
            )
    if "AMC" in params["coverage"] and scope.branch_id is None:  # contracts have no branch
        contracts = (
            select(
                ServiceContract.id,
                ServiceContract.contract_no,
                ServiceContract.company_id,
                ServiceContract.principal_id,
                ServiceContract.end_date,
                Customer.name.label("customer_name"),
            )
            .join(Customer, Customer.id == ServiceContract.customer_id)
            .where(
                ServiceContract.is_active,
                ServiceContract.contract_type == "AMC",
                ServiceContract.status == "Active",
                ServiceContract.end_date >= today,
                ServiceContract.end_date <= last_day,
                ServiceContract.company_id == scope.company_id,
            )
            .order_by(ServiceContract.id)
        )
        if scope.principal_id is not None:
            contracts = contracts.where(ServiceContract.principal_id == scope.principal_id)
        for contract in db.execute(contracts):
            end = contract.end_date
            found.append(
                Candidate(
                    entity_type="svc.service_contract",
                    entity_id=contract.id,
                    dedupe_key=f"svc.service_contract:{contract.id}:amc:{end.isoformat()}",
                    company_id=contract.company_id,
                    principal_id=contract.principal_id,
                    branch_id=None,
                    title=f"AMC ending: {contract.contract_no}",
                    message=f"AMC {contract.contract_no} of {contract.customer_name} ends on "
                    f"{end.strftime('%d %b %Y')} ({(end - today).days} days).",
                )
            )
    return found


# ------------------------------------------------------------------ dispatch

_SCHEDULED = {
    "SVC_CALL_UNASSIGNED": call_unassigned,
    "SVC_SLA_DUE": sla_due,
    "SVC_STATUS_STALE": status_stale,
    "SVC_AWAITING_PARTS": awaiting_parts,
    "MACHINE_COVERAGE_EXPIRY": coverage_expiry,
}


def evaluate(db: Session, alert_type: str, scope: Scope, params: dict[str, Any], now: datetime) -> list[Candidate]:
    """Records that match a scheduled rule now (or, for the event type, a preview of current matches)."""
    if alert_type == "SVC_CALL_REOPENED":
        return call_reopened(db, scope, params)
    if alert_type == "SVC_PART_REQUEST":
        return part_requested(db, scope, params)
    return _SCHEDULED[alert_type](db, scope, params, now)
