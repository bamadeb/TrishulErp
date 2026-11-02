"""SLA targets for service calls. svc.sla_rule is the single source of truth for SLA times.

A call is matched to the most specific active rule of its company: a rule may name a brand, a call type and
a priority, and a blank field matches anything. More named fields win; ties go to the lowest id. The call's
due time is its received time plus the rule's resolution_hours, stored on svc.service_call.sla_due_at when
the call is logged. Calls imported from an OEM keep the due time the OEM sets.

The rule's alert_before_minutes is how early the SLA alert warns ("Due soon"). Clock type "Working hours" is
not modelled yet (no shift/holiday calendar), so it is treated as calendar hours.
"""

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from trishul_api.db.models import SlaRule

# Used when the matched rule has no alert_before_minutes (or the due time came from an OEM file).
DEFAULT_WARN_BEFORE_MINUTES = 60


@dataclass(frozen=True)
class SlaTarget:
    rule_id: int
    resolution_hours: float
    warn_before_minutes: int


def active_rules(db: Session, company_id: int | None = None) -> list[SlaRule]:
    statement = select(SlaRule).where(SlaRule.is_active).order_by(SlaRule.id)
    if company_id is not None:
        statement = statement.where(SlaRule.company_id == company_id)
    return list(db.scalars(statement))


def match_rule(
    rules: Iterable[SlaRule],
    *,
    company_id: int,
    principal_id: int | None,
    call_type_lookup_id: int | None,
    priority: str | None,
) -> SlaTarget | None:
    """The most specific rule that fits the call, or None."""
    best: tuple[int, int, SlaRule] | None = None
    for rule in rules:
        if rule.company_id != company_id:
            continue
        fields = (
            (rule.principal_id, principal_id),
            (rule.call_type_lookup_id, call_type_lookup_id),
            (rule.priority, priority),
        )
        if any(wanted is not None and wanted != actual for wanted, actual in fields):
            continue
        specificity = sum(wanted is not None for wanted, _ in fields)
        if best is None or (specificity, -rule.id) > (best[0], best[1]):
            best = (specificity, -rule.id, rule)
    if best is None:
        return None
    rule = best[2]
    return SlaTarget(
        rule_id=rule.id,
        resolution_hours=float(rule.resolution_hours),
        warn_before_minutes=rule.alert_before_minutes
        if rule.alert_before_minutes is not None
        else DEFAULT_WARN_BEFORE_MINUTES,
    )


def due_at(received_at: datetime, target: SlaTarget | None) -> datetime | None:
    return received_at + timedelta(hours=target.resolution_hours) if target is not None else None
