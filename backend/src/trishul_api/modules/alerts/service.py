"""Alert Master (rule management) and each user's alert inbox.

A rule's parameters are validated against its type in the catalogue, and its recipients against what the type
supports (record-based recipients only where the record has them). The rule code is unique. Deactivating a rule
resolves its open alerts so they leave everyone's inbox.
"""

import json
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from trishul_api.auth import CurrentUser, RequestScope
from trishul_api.common.concurrency import check_row_version
from trishul_api.common.errors import AlreadyExists, ApiError, NotFound
from trishul_api.db.models import (
    Alert,
    AlertRecipient,
    AlertRule,
    AlertRuleRecipient,
    AppUser,
    Branch,
    Company,
    Principal,
    Role,
)
from trishul_api.modules.alerts import catalogue
from trishul_api.modules.alerts.engine import AlertEngine, resolve_rule_alerts, rule_parameters, rule_scope
from trishul_api.modules.alerts.recipients import RecipientSpec
from trishul_api.modules.alerts.repository import AlertRepository
from trishul_api.modules.alerts.schemas import (
    AlertParamDef,
    AlertRecipientIn,
    AlertRuleCreate,
    AlertRuleDetail,
    AlertRuleFormOptions,
    AlertRuleTestMatch,
    AlertRuleTestResult,
    AlertRuleUpdate,
    AlertTypeItem,
    MyAlertItem,
    MyAlertSummary,
)

_TEST_LIMIT = 50
_RULE_RECIPIENTS = ("Role", "User")


def _now() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def alert_types() -> list[AlertTypeItem]:
    return [
        AlertTypeItem(
            code=t.code,
            name=t.name,
            description=t.description,
            module=t.module,
            trigger=t.trigger,
            entity_type=t.entity_type,
            params=[
                AlertParamDef(
                    key=p.key,
                    label=p.label,
                    kind=p.kind,
                    required=p.required,
                    default=p.default,
                    min=p.min,
                    max=p.max,
                    unit=p.unit,
                    options=list(p.options),
                    help=p.help,
                )
                for p in t.params
            ],
            recipient_types=[*_RULE_RECIPIENTS, *t.dynamic_recipients],
        )
        for t in catalogue.CATALOGUE.values()
    ]


class AlertRuleService:
    def __init__(self, db: Session, actor: CurrentUser) -> None:
        self._db = db
        self._actor = actor
        self._repo = AlertRepository(db)

    def get(self, rule_id: int) -> AlertRuleDetail:
        self._require(rule_id)
        return self._detail(rule_id)

    def form_options(self) -> AlertRuleFormOptions:
        return AlertRuleFormOptions(
            alert_types=alert_types(),
            roles=self._repo.roles(),
            users=self._repo.users(),
            principals=self._repo.principals(),
            branches=self._repo.branches(),
        )

    def create(self, scope: RequestScope, data: AlertRuleCreate) -> AlertRuleDetail:
        alert_type = catalogue.get_type(data.alert_type)
        code = data.code.strip()
        self._check_unique_code(code, None)
        parameters = catalogue.validate_parameters(alert_type, data.parameters)
        self._check_scope(data.principal_id, data.branch_id)
        recipients = self._recipients(alert_type, data.recipients)
        rule = AlertRule(
            company_id=self._company_id(scope),
            code=code,
            name=data.name.strip(),
            description=data.description,
            alert_type=data.alert_type,
            principal_id=data.principal_id,
            branch_id=data.branch_id,
            severity=data.severity,
            parameters=json.dumps(parameters),
            reraise_policy=data.reraise_policy,
            cooldown_minutes=data.cooldown_minutes,
            created_by_user_id=self._actor.id,
        )
        self._db.add(rule)
        rule_id = self._save(rule, recipients)
        return self._detail(rule_id)

    def update(self, rule_id: int, expected_row_version: bytes, data: AlertRuleUpdate) -> AlertRuleDetail:
        rule = self._require(rule_id)
        check_row_version(rule.row_version, expected_row_version)
        alert_type = catalogue.get_type(rule.alert_type)
        changed = data.model_fields_set
        for field in ("name", "severity", "reraise_policy", "cooldown_minutes", "code", "recipients", "parameters"):
            if field in changed and getattr(data, field) is None:
                raise ApiError("A value is required.", errors={_camel(field): ["Required."]})
        if "code" in changed and data.code:
            code = data.code.strip()
            self._check_unique_code(code, rule.id)
            rule.code = code
        if "name" in changed and data.name:
            rule.name = data.name.strip()
        if "description" in changed:
            rule.description = data.description
        if "parameters" in changed:
            rule.parameters = json.dumps(catalogue.validate_parameters(alert_type, data.parameters))
        if {"principal_id", "branch_id"} & changed:
            principal_id = data.principal_id if "principal_id" in changed else rule.principal_id
            branch_id = data.branch_id if "branch_id" in changed else rule.branch_id
            self._check_scope(principal_id, branch_id)
            rule.principal_id, rule.branch_id = principal_id, branch_id
        for field in ("severity", "reraise_policy", "cooldown_minutes"):
            if field in changed:
                setattr(rule, field, getattr(data, field))
        recipients = (
            self._recipients(alert_type, data.recipients) if "recipients" in changed and data.recipients else None
        )
        rule.updated_at = _now()
        rule.updated_by_user_id = self._actor.id
        self._save(rule, recipients)
        return self._detail(rule_id)

    def deactivate(self, rule_id: int) -> AlertRuleDetail:
        rule = self._require(rule_id)
        if rule.is_active:
            rule.is_active = False
            rule.updated_at = _now()
            rule.updated_by_user_id = self._actor.id
            resolve_rule_alerts(self._db, rule.id, "Rule deactivated")
            self._db.commit()
        return self._detail(rule_id)

    def activate(self, rule_id: int) -> AlertRuleDetail:
        rule = self._require(rule_id)
        if not rule.is_active:
            rule_parameters(rule)  # refuse to switch on a rule whose stored settings are no longer valid
            rule.is_active = True
            rule.updated_at = _now()
            rule.updated_by_user_id = self._actor.id
            self._db.commit()
        return self._detail(rule_id)

    def test(self, rule_id: int) -> AlertRuleTestResult:
        """Dry run of the saved rule with the signed-in user's view of the data. Writes nothing."""
        rule = self._require(rule_id)
        specs = [
            RecipientSpec(r.recipient_type, r.role_id, r.app_user_id)
            for r in self._db.scalars(select(AlertRuleRecipient).where(AlertRuleRecipient.alert_rule_id == rule.id))
        ]
        matches, total = AlertEngine(self._db).preview(
            rule.alert_type, rule_scope(rule), rule_parameters(rule), specs, _TEST_LIMIT
        )
        note = None
        if catalogue.get_type(rule.alert_type).trigger == "Event":
            note = "This alert is raised when the event happens. Shown here: records in that state now."
        elif total > _TEST_LIMIT:
            note = f"Showing the first {_TEST_LIMIT} of {total} matches."
        return AlertRuleTestResult(
            total=total,
            matches=[
                AlertRuleTestMatch(
                    entity_type=c.entity_type,
                    entity_id=c.entity_id,
                    title=c.title,
                    message=c.message,
                    recipients=names,
                )
                for c, names in matches
            ],
            note=note,
        )

    # ------------------------------------------------------------------ helpers

    def _require(self, rule_id: int) -> AlertRule:
        rule = self._db.get(AlertRule, rule_id)
        if rule is None:
            raise NotFound("Alert rule not found.")
        return rule

    def _detail(self, rule_id: int) -> AlertRuleDetail:
        rule = self._require(rule_id)
        recipients = self._repo.recipients([rule_id]).get(rule_id, [])
        item = self._repo.list_item(self._repo.rule_row(rule_id), recipients)
        return AlertRuleDetail.model_validate(
            item.model_dump()
            | {
                "description": rule.description,
                "principal_id": rule.principal_id,
                "branch_id": rule.branch_id,
                "parameters": json.loads(rule.parameters or "{}"),
                "reraise_policy": rule.reraise_policy,
                "cooldown_minutes": rule.cooldown_minutes,
                "recipients": recipients,
                "row_version": rule.row_version,
            }
        )

    def _save(self, rule: AlertRule, recipients: list[AlertRuleRecipient] | None) -> int:
        try:
            self._db.flush()
            rule_id = rule.id
            if recipients is not None:
                self._repo.replace_recipients(rule_id, recipients)
            self._db.commit()
        except IntegrityError as error:
            self._db.rollback()
            raise AlreadyExists("Another alert rule already has this code.") from error
        return rule_id

    def _check_unique_code(self, code: str, rule_id: int | None) -> None:
        owner = self._repo.code_owner(code)
        if owner is not None and owner != rule_id:
            raise AlreadyExists(f"Alert rule code '{code}' is already in use.")

    def _check_scope(self, principal_id: int | None, branch_id: int | None) -> None:
        errors: dict[str, list[str]] = {}
        if principal_id is not None and self._repo.missing(Principal, [principal_id]):
            errors["principalId"] = [f"Unknown or inactive brand {principal_id}"]
        if branch_id is not None and self._repo.missing(Branch, [branch_id]):
            errors["branchId"] = [f"Unknown or inactive branch {branch_id}"]
        if errors:
            raise ApiError("Some of the selected values don't exist.", errors=errors)

    def _recipients(
        self, alert_type: catalogue.AlertTypeDef, items: list[AlertRecipientIn]
    ) -> list[AlertRuleRecipient]:
        allowed = {*_RULE_RECIPIENTS, *alert_type.dynamic_recipients}
        errors: dict[str, list[str]] = {}
        seen: set[tuple[str, int | None, int | None]] = set()
        result: list[AlertRuleRecipient] = []
        for index, item in enumerate(items):
            name = f"recipients.{index}"
            if item.recipient_type not in allowed:
                errors[name] = [f"'{item.recipient_type}' is not available for this alert type."]
                continue
            role_id = item.role_id if item.recipient_type == "Role" else None
            user_id = item.app_user_id if item.recipient_type == "User" else None
            if item.recipient_type == "Role" and (role_id is None or self._repo.missing(Role, [role_id])):
                errors[name] = ["Choose a valid role."]
                continue
            if item.recipient_type == "User" and (user_id is None or self._repo.missing(AppUser, [user_id])):
                errors[name] = ["Choose a valid user."]
                continue
            key = (item.recipient_type, role_id, user_id)
            if key in seen:
                continue  # the same recipient twice is just one recipient
            seen.add(key)
            result.append(
                AlertRuleRecipient(
                    recipient_type=item.recipient_type,
                    role_id=role_id,
                    app_user_id=user_id,
                    channel="In-app",
                    created_by_user_id=self._actor.id,
                )
            )
        if errors:
            raise ApiError("Some recipients are not valid.", errors=errors)
        return result

    def _company_id(self, scope: RequestScope) -> int:
        branch_id = scope.branch_id or self._actor.default_branch_id
        if branch_id is not None:
            company_id = self._db.scalar(select(Branch.company_id).where(Branch.id == branch_id))
            if company_id is not None:
                return company_id
        company_id = self._db.scalar(select(Company.id).where(Company.is_active).order_by(Company.id).limit(1))
        if company_id is None:
            raise ApiError("No company is set up yet.")
        return company_id


class MyAlertService:
    """The signed-in user's alerts. Only their own: someone else's alert is 'not found'."""

    def __init__(self, db: Session, actor: CurrentUser) -> None:
        self._db = db
        self._actor = actor
        self._repo = AlertRepository(db)

    def summary(self) -> MyAlertSummary:
        return self._repo.my_summary(self._actor.id)

    def mark_read(self, alert_id: int) -> MyAlertItem:
        _, entry = self._require(alert_id)
        if entry.read_at is None:
            entry.read_at = _now()
            self._db.commit()
        return self._repo.my_item(self._actor.id, alert_id)

    def acknowledge(self, alert_id: int) -> MyAlertItem:
        """'I'm on it': the alert is acknowledged for everyone who received it, and read for me."""
        alert, entry = self._require(alert_id)
        now = _now()
        if alert.status == "Open":
            alert.status = "Acknowledged"
            alert.acknowledged_at = now
            alert.acknowledged_by_user_id = self._actor.id
        if entry.read_at is None:
            entry.read_at = now
        self._db.commit()
        return self._repo.my_item(self._actor.id, alert_id)

    def _require(self, alert_id: int) -> tuple[Alert, AlertRecipient]:
        entry = self._repo.my_entry(self._actor.id, alert_id)
        if entry is None:
            raise NotFound("Alert not found.")
        return entry


def _camel(name: str) -> str:
    head, *rest = name.split("_")
    return head + "".join(part.title() for part in rest)
