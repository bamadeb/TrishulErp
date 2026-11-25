"""In-app alerts for complaints (alert types CMP_COMPLAINT_RAISED and CMP_COMPLAINT_UPDATED).

Raised in the request that raises or updates the complaint, through the event rule the migration seeds (an
administrator can switch it off in Alert Master, or add roles / users who should also be told).

* Raised   -> the department's leaders (head + employees with core.complaint.manage); if it has none, the
              Super Admins, so no complaint goes unnoticed. Resolved when the complaint's status first changes.
* Updated  -> the person who raised it (not when they made the change themselves). An older update alert of the
              same complaint is resolved by the newer one, so the bell shows the latest state only.

Never commits; a failure is logged and never stops the complaint from being saved.
"""

import logging
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from trishul_api.db.models import Alert, AlertRecipient, AlertRule, AlertRuleRecipient, Complaint
from trishul_api.modules.alerts.conditions import Candidate
from trishul_api.modules.alerts.recipients import RecipientResolver, RecipientSpec
from trishul_api.modules.core.complaints.access import department_leader_user_ids, super_admin_user_ids

log = logging.getLogger(__name__)

RAISED = "CMP_COMPLAINT_RAISED"
UPDATED = "CMP_COMPLAINT_UPDATED"
ENTITY_TYPE = "core.complaint"


def _rule(db: Session, alert_type: str) -> AlertRule | None:
    return db.scalars(
        select(AlertRule).where(AlertRule.alert_type == alert_type, AlertRule.is_active).order_by(AlertRule.id)
    ).first()


def _resolve_open(db: Session, alert_type: str, complaint_id: int, note: str, now: datetime) -> None:
    for alert in db.scalars(
        select(Alert).where(
            Alert.alert_type == alert_type,
            Alert.entity_type == ENTITY_TYPE,
            Alert.entity_id == complaint_id,
            Alert.status != "Resolved",
        )
    ):
        alert.status = "Resolved"
        alert.resolved_at = now
        alert.resolution_note = note


def _raise(
    db: Session,
    rule: AlertRule,
    complaint: Complaint,
    *,
    key: str,
    title: str,
    message: str,
    users: set[int],
    now: datetime,
) -> None:
    candidate = Candidate(
        entity_type=ENTITY_TYPE,
        entity_id=complaint.id,
        dedupe_key=key,
        company_id=complaint.company_id,
        principal_id=None,
        branch_id=complaint.branch_id,
        title=title,
        message=message,
    )
    specs = [
        RecipientSpec(r.recipient_type, r.role_id, r.app_user_id)
        for r in db.scalars(select(AlertRuleRecipient).where(AlertRuleRecipient.alert_rule_id == rule.id))
    ]
    recipients = users | RecipientResolver(db).resolve(specs, candidate)
    if not recipients:
        return
    alert = Alert(
        alert_rule_id=rule.id,
        alert_type=rule.alert_type,
        company_id=complaint.company_id,
        principal_id=None,
        branch_id=complaint.branch_id,
        entity_type=ENTITY_TYPE,
        entity_id=complaint.id,
        dedupe_key=key,
        severity=rule.severity,
        title=title[:200],
        message=message[:1000],
        status="Open",
        raised_at=now,
    )
    try:
        with db.begin_nested():
            db.add(alert)
            db.flush()
            for user_id in sorted(recipients):
                db.add(AlertRecipient(alert_id=alert.id, app_user_id=user_id))
            db.flush()
    except IntegrityError:
        log.warning("Complaint alert %s for complaint %s was already raised", key, complaint.id)


def complaint_raised(
    db: Session, complaint: Complaint, *, raised_by: str, department: str, issue_type: str, now: datetime
) -> None:
    try:
        rule = _rule(db, RAISED)
        if rule is None:
            return
        users = department_leader_user_ids(db, complaint.department_id) or super_admin_user_ids(db)
        users.discard(complaint.raised_by_user_id)
        _raise(
            db,
            rule,
            complaint,
            key=f"{ENTITY_TYPE}:{complaint.id}:raised",
            title=f"New complaint {complaint.complaint_no} to {department}",
            message=f"{raised_by} raised a complaint ({issue_type}): {complaint.description}",
            users=users,
            now=now,
        )
    except Exception:  # an alert must never stop the complaint being saved
        log.exception("Raising %s for complaint %s failed", RAISED, complaint.id)


def complaint_updated(
    db: Session,
    complaint: Complaint,
    *,
    history_id: int,
    from_status: str,
    note: str | None,
    changed_by_user_id: int,
    changed_by: str,
    now: datetime,
) -> None:
    try:
        if complaint.status != "Open":
            _resolve_open(db, RAISED, complaint.id, "Complaint taken up", now)
        rule = _rule(db, UPDATED)
        if rule is None:
            return
        _resolve_open(db, UPDATED, complaint.id, "Newer update", now)
        if changed_by_user_id == complaint.raised_by_user_id:
            return
        if from_status == complaint.status:
            title = f"Note on your complaint {complaint.complaint_no}"
            message = f"{changed_by}: {note}"
        else:
            title = f"Your complaint {complaint.complaint_no} is {complaint.status}"
            message = f"{changed_by} changed the status from {from_status} to {complaint.status}."
            if note:
                message += f" Note: {note}"
        _raise(
            db,
            rule,
            complaint,
            key=f"{ENTITY_TYPE}:{complaint.id}:update:{history_id}",
            title=title,
            message=message,
            users={complaint.raised_by_user_id},
            now=now,
        )
    except Exception:
        log.exception("Raising %s for complaint %s failed", UPDATED, complaint.id)
