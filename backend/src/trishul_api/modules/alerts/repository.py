from collections import defaultdict
from typing import Any

from sqlalchemy import ColumnElement, Select, func, or_, select
from sqlalchemy.orm import Session, aliased

from trishul_api.common.paging import SortColumns, order_by_sort, paginate
from trishul_api.common.schemas import ApiModel, Page, UtcDateTime
from trishul_api.db.models import (
    Alert,
    AlertRecipient,
    AlertRule,
    AlertRuleRecipient,
    AppUser,
    Branch,
    Employee,
    Principal,
    Role,
)
from trishul_api.modules.alerts import catalogue
from trishul_api.modules.alerts.recipients import SYSTEM_USERNAME
from trishul_api.modules.alerts.schemas import (
    AlertRecipientItem,
    AlertRuleListItem,
    AlertRuleQuery,
    MyAlertItem,
    MyAlertQuery,
    MyAlertSummary,
    NamedOption,
)

_RULE_SORT: SortColumns = {
    "code": AlertRule.code,
    "name": AlertRule.name,
    "alertType": AlertRule.alert_type,
    "severity": AlertRule.severity,
    "lastRunAt": AlertRule.last_run_at,
}

_USER_NAME: ColumnElement[str] = func.coalesce(
    func.nullif(func.concat_ws(" ", Employee.first_name, Employee.last_name), ""), AppUser.username
)


class _RuleRow(ApiModel):
    id: int
    code: str
    name: str
    alert_type: str
    severity: str
    principal_name: str | None
    branch_name: str | None
    open_alert_count: int
    is_active: bool
    last_run_at: UtcDateTime | None


def _open_count() -> ColumnElement[int]:
    return (
        select(func.count(Alert.id))
        .where(Alert.alert_rule_id == AlertRule.id, Alert.status != "Resolved")
        .correlate(AlertRule)
        .scalar_subquery()
    )


def _rule_select() -> Select[*tuple[Any, ...]]:
    return (
        select(
            AlertRule.id,
            AlertRule.code,
            AlertRule.name,
            AlertRule.alert_type,
            AlertRule.severity,
            Principal.name.label("principal_name"),
            Branch.name.label("branch_name"),
            _open_count().label("open_alert_count"),
            AlertRule.is_active,
            AlertRule.last_run_at,
        )
        .outerjoin(Principal, Principal.id == AlertRule.principal_id)
        .outerjoin(Branch, Branch.id == AlertRule.branch_id)
    )


class AlertRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    # ------------------------------------------------------------------ rules

    def search_rules(self, query: AlertRuleQuery) -> Page[AlertRuleListItem]:
        statement = _rule_select()
        if query.status != "all":
            statement = statement.where(AlertRule.is_active == (query.status == "active"))
        if query.alert_type is not None:
            statement = statement.where(AlertRule.alert_type == query.alert_type)
        if query.search:
            term = query.search.strip()
            statement = statement.where(
                or_(AlertRule.code.contains(term, autoescape=True), AlertRule.name.contains(term, autoescape=True))
            )
        statement = order_by_sort(statement, query.sort, _RULE_SORT, default="name", tiebreaker=AlertRule.id.asc())
        page = paginate(self._session, statement, query, _RuleRow)
        recipients = self.recipients([row.id for row in page.items])
        return Page(
            items=[self.list_item(row.model_dump(), recipients.get(row.id, [])) for row in page.items],
            total=page.total,
            page=page.page,
            page_size=page.page_size,
        )

    def rule_row(self, rule_id: int) -> dict[str, Any]:
        return dict(self._session.execute(_rule_select().where(AlertRule.id == rule_id)).mappings().one())

    @staticmethod
    def list_item(row: dict[str, Any], recipients: list[AlertRecipientItem]) -> AlertRuleListItem:
        alert_type = catalogue.get_type(row["alert_type"])
        return AlertRuleListItem.model_validate(
            row
            | {
                "alert_type_name": alert_type.name,
                "trigger": alert_type.trigger,
                "recipient_summary": ", ".join(_recipient_label(r) for r in recipients) or "Nobody",
            }
        )

    def recipients(self, rule_ids: list[int]) -> dict[int, list[AlertRecipientItem]]:
        if not rule_ids:
            return {}
        rows = self._session.execute(
            select(
                AlertRuleRecipient.alert_rule_id,
                AlertRuleRecipient.recipient_type,
                AlertRuleRecipient.role_id,
                Role.name.label("role_name"),
                AlertRuleRecipient.app_user_id,
                _USER_NAME.label("user_name"),
            )
            .outerjoin(Role, Role.id == AlertRuleRecipient.role_id)
            .outerjoin(AppUser, AppUser.id == AlertRuleRecipient.app_user_id)
            .outerjoin(Employee, Employee.id == AppUser.employee_id)
            .where(AlertRuleRecipient.alert_rule_id.in_(rule_ids))
            .order_by(AlertRuleRecipient.id)
        ).mappings()
        result: dict[int, list[AlertRecipientItem]] = defaultdict(list)
        for row in rows:
            item = AlertRecipientItem.model_validate(row)
            # A user picked by id shows their name; a role or record-based recipient has none.
            result[row["alert_rule_id"]].append(
                item if row["app_user_id"] else item.model_copy(update={"user_name": None})
            )
        return result

    def code_owner(self, code: str) -> int | None:
        return self._session.scalar(select(AlertRule.id).where(AlertRule.code == code).limit(1))

    def replace_recipients(self, rule_id: int, recipients: list[AlertRuleRecipient]) -> None:
        for old in self._session.scalars(select(AlertRuleRecipient).where(AlertRuleRecipient.alert_rule_id == rule_id)):
            self._session.delete(old)
        self._session.flush()
        for recipient in recipients:
            recipient.alert_rule_id = rule_id
            self._session.add(recipient)

    def missing(self, model: type[Any], ids: list[int]) -> set[int]:
        wanted = {i for i in ids if i is not None}
        if not wanted:
            return set()
        statement = select(model.id).where(model.id.in_(wanted))
        if hasattr(model, "is_active"):
            statement = statement.where(model.is_active)
        return wanted - set(self._session.scalars(statement))

    # ------------------------------------------------------------------ form options

    def roles(self) -> list[NamedOption]:
        rows = self._session.execute(select(Role.id, Role.name).where(Role.is_active).order_by(Role.name)).mappings()
        return [NamedOption.model_validate(r) for r in rows]

    def users(self) -> list[NamedOption]:
        rows = self._session.execute(
            select(AppUser.id, _USER_NAME.label("name"))
            .outerjoin(Employee, Employee.id == AppUser.employee_id)
            .where(AppUser.is_active, ~AppUser.is_locked, AppUser.username != SYSTEM_USERNAME)
            .order_by(_USER_NAME)
        ).mappings()
        return [NamedOption.model_validate(r) for r in rows]

    def principals(self) -> list[NamedOption]:
        rows = self._session.execute(
            select(Principal.id, Principal.name).where(Principal.is_active).order_by(Principal.name)
        ).mappings()
        return [NamedOption.model_validate(r) for r in rows]

    def branches(self) -> list[NamedOption]:
        rows = self._session.execute(
            select(Branch.id, Branch.name).where(Branch.is_active).order_by(Branch.name)
        ).mappings()
        return [NamedOption.model_validate(r) for r in rows]

    # ------------------------------------------------------------------ my alerts

    def my_alerts(self, user_id: int, query: MyAlertQuery) -> Page[MyAlertItem]:
        statement = _my_select(user_id)
        if query.status == "open":
            statement = statement.where(Alert.status != "Resolved")
        if query.unread_only:
            statement = statement.where(AlertRecipient.read_at.is_(None))
        if query.search:
            term = query.search.strip()
            statement = statement.where(
                or_(Alert.title.contains(term, autoescape=True), Alert.message.contains(term, autoescape=True))
            )
        statement = statement.order_by(Alert.raised_at.desc(), Alert.id.desc())
        return paginate(self._session, statement, query, MyAlertItem)

    def my_item(self, user_id: int, alert_id: int) -> MyAlertItem:
        row = self._session.execute(_my_select(user_id).where(Alert.id == alert_id)).mappings().one()
        return MyAlertItem.model_validate(row)

    def my_summary(self, user_id: int) -> MyAlertSummary:
        base = (
            select(func.count(Alert.id))
            .join(AlertRecipient, AlertRecipient.alert_id == Alert.id)
            .where(AlertRecipient.app_user_id == user_id, Alert.status != "Resolved")
        )
        unread = self._session.scalar(base.where(AlertRecipient.read_at.is_(None))) or 0
        return MyAlertSummary(unread=unread, open=self._session.scalar(base) or 0)

    def my_entry(self, user_id: int, alert_id: int) -> tuple[Alert, AlertRecipient] | None:
        row = self._session.execute(
            select(Alert, AlertRecipient)
            .join(AlertRecipient, AlertRecipient.alert_id == Alert.id)
            .where(Alert.id == alert_id, AlertRecipient.app_user_id == user_id)
        ).first()
        return (row[0], row[1]) if row is not None else None


def _my_select(user_id: int) -> Select[*tuple[Any, ...]]:
    """Columns of MyAlertItem for one recipient's alerts."""
    acknowledged_by = aliased(AppUser)
    acknowledged_employee = aliased(Employee)
    ack_name = func.coalesce(
        func.nullif(func.concat_ws(" ", acknowledged_employee.first_name, acknowledged_employee.last_name), ""),
        acknowledged_by.username,
    )
    return (
        select(
            Alert.id,
            Alert.alert_type,
            AlertRule.name.label("rule_name"),
            Alert.severity,
            Alert.title,
            Alert.message,
            Alert.entity_type,
            Alert.entity_id,
            Alert.status,
            Alert.raised_at,
            AlertRecipient.read_at,
            Alert.acknowledged_at,
            ack_name.label("acknowledged_by_name"),
            Alert.resolved_at,
            Alert.resolution_note,
        )
        .join(AlertRecipient, AlertRecipient.alert_id == Alert.id)
        .join(AlertRule, AlertRule.id == Alert.alert_rule_id)
        .outerjoin(acknowledged_by, acknowledged_by.id == Alert.acknowledged_by_user_id)
        .outerjoin(acknowledged_employee, acknowledged_employee.id == acknowledged_by.employee_id)
        .where(AlertRecipient.app_user_id == user_id)
    )


def _recipient_label(r: AlertRecipientItem) -> str:
    if r.recipient_type == "Role":
        return r.role_name or "Role"
    if r.recipient_type == "User":
        return r.user_name or "User"
    return r.recipient_type
