"""The alert engine: raises alerts for matching records, without duplicates, and resolves cleared ones.

Duplicate prevention. An alert is identified by its rule and a dedupe key naming the business record (and,
where it matters, the stage: e.g. "svc.service_call:42:breached"). While an alert with that rule + key is
open (Open or Acknowledged), no other is raised; the filtered unique index UX_core_alert_rule_open_key
enforces this in the database too. Once it is resolved, the rule's re-raise policy decides:

* Never             the same rule never alerts on the same key again.
* After resolution  it may alert again when the condition comes back, but not within cooldown_minutes of the
                    last resolution.

Automatic resolution. Each run of a scheduled rule lists the records that match now; an open alert whose key is
not in that list is resolved ("Condition cleared"). An event alert (call reopened) is resolved once the call is
finished again. A deactivated rule's open alerts are resolved by the rule service.

The engine never commits; callers do (the request for an event, the job runner per rule for scheduled runs).
"""

import json
import logging
from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from trishul_api.db.models import Alert, AlertRecipient, AlertRule, AlertRuleRecipient, SlaEvent
from trishul_api.modules.alerts import catalogue, conditions
from trishul_api.modules.alerts.conditions import Candidate, Scope
from trishul_api.modules.alerts.recipients import RecipientResolver, RecipientSpec

log = logging.getLogger(__name__)


def utcnow() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


@dataclass
class RuleRun:
    rule_id: int
    raised: int = 0
    resolved: int = 0
    error: str | None = None


@dataclass
class RunSummary:
    rules: list[RuleRun] = field(default_factory=list)

    @property
    def raised(self) -> int:
        return sum(r.raised for r in self.rules)

    @property
    def resolved(self) -> int:
        return sum(r.resolved for r in self.rules)


def rule_scope(rule: AlertRule) -> Scope:
    return Scope(company_id=rule.company_id, principal_id=rule.principal_id, branch_id=rule.branch_id)


def rule_parameters(rule: AlertRule) -> dict[str, Any]:
    """The stored parameters, re-validated (defaults filled in) against the catalogue."""
    return catalogue.validate_parameters(catalogue.get_type(rule.alert_type), json.loads(rule.parameters or "{}"))


class AlertEngine:
    def __init__(self, db: Session, now: datetime | None = None) -> None:
        self._db = db
        self._now = now or utcnow()
        self._resolver = RecipientResolver(db)

    # ------------------------------------------------------------------ scheduled (TrishulJobs)

    def run_scheduled(self) -> RunSummary:
        """Run every active rule once: scheduled rules raise and resolve, event rules only resolve.

        Each rule is committed on its own, so one failing rule does not stop the others."""
        summary = RunSummary()
        rule_ids = list(self._db.scalars(select(AlertRule.id).where(AlertRule.is_active).order_by(AlertRule.id)))
        for rule_id in rule_ids:
            run = RuleRun(rule_id)
            try:
                rule = self._db.get(AlertRule, rule_id)
                if rule is None or not rule.is_active:
                    continue
                run.raised, run.resolved = self.run_rule(rule)
                rule.last_run_at = self._now
                self._db.commit()
            except Exception as error:  # one bad rule must not stop the rest
                self._db.rollback()
                run.error = str(error)
                log.exception("Alert rule %s failed", rule_id)
            summary.rules.append(run)
        return summary

    def run_rule(self, rule: AlertRule) -> tuple[int, int]:
        """(raised, resolved) for one rule. Does not commit."""
        alert_type = catalogue.get_type(rule.alert_type)
        if alert_type.trigger == "Event":
            return 0, self._resolve_finished_calls(rule)
        candidates = conditions.evaluate(self._db, rule.alert_type, rule_scope(rule), rule_parameters(rule), self._now)
        specs = self._specs(rule.id)
        raised = sum(1 for c in candidates if self._raise(rule, specs, c) is not None)
        resolved = self._resolve_cleared(rule, {c.dedupe_key for c in candidates})
        return raised, resolved

    # ------------------------------------------------------------------ events (in the request)

    def raise_event(self, alert_type: str, call_id: int, first_request_id: int | None = None) -> int:
        """Raise alerts for an event on a call (SVC_CALL_REOPENED, or SVC_PART_REQUEST with the first row id of
        the request just saved). Does not commit."""
        raised = 0
        rules = self._db.scalars(
            select(AlertRule).where(AlertRule.is_active, AlertRule.alert_type == alert_type).order_by(AlertRule.id)
        )
        for rule in rules:
            if alert_type == "SVC_PART_REQUEST":
                candidates = conditions.part_requested(
                    self._db, rule_scope(rule), rule_parameters(rule), call_id, first_request_id
                )
            else:
                candidates = conditions.call_reopened(self._db, rule_scope(rule), rule_parameters(rule), call_id)
            specs = self._specs(rule.id)
            raised += sum(1 for c in candidates if self._raise(rule, specs, c) is not None)
        return raised

    # ------------------------------------------------------------------ Test Rule (dry run)

    def preview(
        self, alert_type: str, scope: Scope, parameters: dict[str, Any], specs: list[RecipientSpec], limit: int
    ) -> tuple[list[tuple[Candidate, list[str]]], int]:
        """Records that would match now and who would be told, without writing anything."""
        candidates = conditions.evaluate(self._db, alert_type, scope, parameters, self._now)
        shown = []
        for candidate in candidates[:limit]:
            users = self._resolver.resolve(specs, candidate)
            names = self._resolver.names(users)
            shown.append((candidate, sorted(names.values())))
        return shown, len(candidates)

    # ------------------------------------------------------------------ helpers

    def _specs(self, rule_id: int) -> list[RecipientSpec]:
        return [
            RecipientSpec(r.recipient_type, r.role_id, r.app_user_id)
            for r in self._db.scalars(select(AlertRuleRecipient).where(AlertRuleRecipient.alert_rule_id == rule_id))
        ]

    def _may_raise(self, rule: AlertRule, key: str) -> bool:
        history = self._db.execute(
            select(Alert.status, Alert.resolved_at).where(Alert.alert_rule_id == rule.id, Alert.dedupe_key == key)
        ).all()
        if any(status != "Resolved" for status, _ in history):
            return False  # already open: never two at once
        if not history:
            return True
        if rule.reraise_policy == "Never":
            return False
        last_resolved = max((resolved for _, resolved in history if resolved is not None), default=None)
        return last_resolved is None or self._now >= last_resolved + timedelta(minutes=rule.cooldown_minutes)

    def _raise(self, rule: AlertRule, specs: list[RecipientSpec], candidate: Candidate) -> Alert | None:
        if not self._may_raise(rule, candidate.dedupe_key):
            return None
        alert = Alert(
            alert_rule_id=rule.id,
            alert_type=rule.alert_type,
            company_id=candidate.company_id,
            principal_id=candidate.principal_id,
            branch_id=candidate.branch_id,
            entity_type=candidate.entity_type,
            entity_id=candidate.entity_id,
            dedupe_key=candidate.dedupe_key,
            severity=rule.severity,
            title=candidate.title[:200],
            message=candidate.message[:1000],
            status="Open",
            raised_at=self._now,
        )
        try:
            with self._db.begin_nested():
                self._db.add(alert)
                self._db.flush()
                for user_id in sorted(self._resolver.resolve(specs, candidate)):
                    self._db.add(AlertRecipient(alert_id=alert.id, app_user_id=user_id))
                if candidate.sla_event_type is not None:
                    self._db.add(
                        SlaEvent(
                            service_call_id=candidate.entity_id,
                            sla_rule_id=candidate.sla_rule_id,
                            event_type=candidate.sla_event_type,
                            event_at=self._now,
                        )
                    )
                self._db.flush()
        except IntegrityError:
            # Raised concurrently by another run: the unique index kept the first one.
            return None
        return alert

    def _open_alerts(self, rule_id: int) -> list[Alert]:
        return list(self._db.scalars(select(Alert).where(Alert.alert_rule_id == rule_id, Alert.status != "Resolved")))

    def _resolve(self, alert: Alert, note: str) -> None:
        alert.status = "Resolved"
        alert.resolved_at = self._now
        alert.resolution_note = note

    def _resolve_cleared(self, rule: AlertRule, current_keys: set[str]) -> int:
        cleared = [a for a in self._open_alerts(rule.id) if a.dedupe_key not in current_keys]
        for alert in cleared:
            self._resolve(alert, "Condition cleared")
        return len(cleared)

    def _resolve_finished_calls(self, rule: AlertRule) -> int:
        alerts = [a for a in self._open_alerts(rule.id) if a.entity_type == "svc.service_call"]
        still_open = conditions.open_call_ids(self._db, (a.entity_id for a in alerts))
        finished = [a for a in alerts if a.entity_id not in still_open]
        for alert in finished:
            self._resolve(alert, "Call finished")
        if rule.alert_type == "SVC_PART_REQUEST":
            return len(finished) + self.resolve_reviewed_parts(a.entity_id for a in alerts if a not in finished)
        return len(finished)

    def resolve_reviewed_parts(self, call_ids: Iterable[int]) -> int:
        """Resolve the open part-request alerts of calls whose requested parts are all quoted or rejected.
        Does not commit."""
        ids = set(call_ids)
        if not ids:
            return 0
        alerts = list(
            self._db.scalars(
                select(Alert).where(
                    Alert.alert_type == "SVC_PART_REQUEST",
                    Alert.entity_type == "svc.service_call",
                    Alert.entity_id.in_(ids),
                    Alert.status != "Resolved",
                )
            )
        )
        waiting = conditions.calls_with_requested_parts(self._db, ids)
        done = [a for a in alerts if a.entity_id not in waiting]
        for alert in done:
            self._resolve(alert, "Parts reviewed")
        return len(done)


def resolve_rule_alerts(db: Session, rule_id: int, note: str, now: datetime | None = None) -> int:
    """Resolve every open alert of a rule (used when the rule is deactivated). Does not commit."""
    when = now or utcnow()
    alerts = list(db.scalars(select(Alert).where(Alert.alert_rule_id == rule_id, Alert.status != "Resolved")))
    for alert in alerts:
        alert.status = "Resolved"
        alert.resolved_at = when
        alert.resolution_note = note
    return len(alerts)
