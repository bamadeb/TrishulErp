from typing import Annotated

from fastapi import APIRouter, Depends, Path, Query, Response

from trishul_api.auth import CurrentUserDep, DbSession, ScopeDep, require_permission
from trishul_api.common.concurrency import if_match_row_version
from trishul_api.common.errors import CONCURRENCY_RESPONSES, NOT_FOUND_RESPONSE
from trishul_api.common.schemas import Page
from trishul_api.modules.alerts.repository import AlertRepository
from trishul_api.modules.alerts.schemas import (
    AlertRuleCreate,
    AlertRuleDetail,
    AlertRuleFormOptions,
    AlertRuleListItem,
    AlertRuleQuery,
    AlertRuleTestResult,
    AlertRuleUpdate,
    AlertTypeItem,
    MyAlertItem,
    MyAlertQuery,
    MyAlertSummary,
)
from trishul_api.modules.alerts.service import AlertRuleService, MyAlertService, alert_types

router = APIRouter(prefix="/core", tags=["alerts"])

CAN_VIEW_RULES = Depends(require_permission("core.alert.rule.view", "core.alert.rule.manage"))
CAN_MANAGE_RULES = Depends(require_permission("core.alert.rule.manage"))
# Every role has core.alert.view (migration 0010); each user only ever sees their own alerts.
CAN_SEE_MY_ALERTS = Depends(require_permission("core.alert.view"))

RuleId = Annotated[int, Path(alias="alertRuleId", gt=0)]
AlertId = Annotated[int, Path(alias="alertId", gt=0)]


def get_alert_repository(db: DbSession) -> AlertRepository:
    return AlertRepository(db)


AlertRepo = Annotated[AlertRepository, Depends(get_alert_repository)]


# ------------------------------------------------------------------ catalogue + Alert Master


@router.get("/alert-types", summary="The alert type catalogue and each type's settings", dependencies=[CAN_VIEW_RULES])
def list_alert_types() -> list[AlertTypeItem]:
    return alert_types()


@router.get("/alert-rules", summary="Alert rules, filtered and paged", dependencies=[CAN_VIEW_RULES])
def list_alert_rules(query: Annotated[AlertRuleQuery, Query()], repo: AlertRepo) -> Page[AlertRuleListItem]:
    return repo.search_rules(query)


# Declared before /alert-rules/{alertRuleId} so "form-options" is not parsed as an id.
@router.get(
    "/alert-rules/form-options", summary="Dropdown values for the alert rule form", dependencies=[CAN_MANAGE_RULES]
)
def get_alert_rule_form_options(actor: CurrentUserDep, db: DbSession) -> AlertRuleFormOptions:
    return AlertRuleService(db, actor).form_options()


@router.get(
    "/alert-rules/{alertRuleId}", summary="One alert rule", dependencies=[CAN_VIEW_RULES], responses=NOT_FOUND_RESPONSE
)
def get_alert_rule(rule_id: RuleId, actor: CurrentUserDep, db: DbSession) -> AlertRuleDetail:
    return AlertRuleService(db, actor).get(rule_id)


@router.post("/alert-rules", summary="Add an alert rule", status_code=201, dependencies=[CAN_MANAGE_RULES])
def create_alert_rule(
    data: AlertRuleCreate, actor: CurrentUserDep, scope: ScopeDep, db: DbSession, response: Response
) -> AlertRuleDetail:
    created = AlertRuleService(db, actor).create(scope, data)
    response.headers["Location"] = f"alert-rules/{created.id}"
    return created


@router.patch(
    "/alert-rules/{alertRuleId}",
    summary="Change an alert rule",
    dependencies=[CAN_MANAGE_RULES],
    responses={**NOT_FOUND_RESPONSE, **CONCURRENCY_RESPONSES},
)
def update_alert_rule(
    rule_id: RuleId,
    data: AlertRuleUpdate,
    actor: CurrentUserDep,
    db: DbSession,
    row_version: Annotated[bytes, Depends(if_match_row_version)],
) -> AlertRuleDetail:
    return AlertRuleService(db, actor).update(rule_id, row_version, data)


@router.post(
    "/alert-rules/{alertRuleId}/deactivate",
    summary="Switch an alert rule off (its open alerts are resolved)",
    dependencies=[CAN_MANAGE_RULES],
    responses=NOT_FOUND_RESPONSE,
)
def deactivate_alert_rule(rule_id: RuleId, actor: CurrentUserDep, db: DbSession) -> AlertRuleDetail:
    return AlertRuleService(db, actor).deactivate(rule_id)


@router.post(
    "/alert-rules/{alertRuleId}/activate",
    summary="Switch an alert rule on",
    dependencies=[CAN_MANAGE_RULES],
    responses=NOT_FOUND_RESPONSE,
)
def activate_alert_rule(rule_id: RuleId, actor: CurrentUserDep, db: DbSession) -> AlertRuleDetail:
    return AlertRuleService(db, actor).activate(rule_id)


@router.post(
    "/alert-rules/{alertRuleId}/test",
    summary="Dry run: what the saved rule matches now and who would be told (nothing is raised)",
    dependencies=[CAN_VIEW_RULES],
    responses=NOT_FOUND_RESPONSE,
)
def test_alert_rule(rule_id: RuleId, actor: CurrentUserDep, db: DbSession) -> AlertRuleTestResult:
    return AlertRuleService(db, actor).test(rule_id)


# ------------------------------------------------------------------ my alerts (web and mobile)


@router.get("/my-alerts", summary="My alerts, newest first", dependencies=[CAN_SEE_MY_ALERTS])
def list_my_alerts(
    query: Annotated[MyAlertQuery, Query()], actor: CurrentUserDep, repo: AlertRepo
) -> Page[MyAlertItem]:
    return repo.my_alerts(actor.id, query)


@router.get(
    "/my-alerts/summary", summary="Unread and open alert counts (for the bell)", dependencies=[CAN_SEE_MY_ALERTS]
)
def get_my_alert_summary(actor: CurrentUserDep, db: DbSession) -> MyAlertSummary:
    return MyAlertService(db, actor).summary()


@router.post(
    "/my-alerts/{alertId}/read",
    summary="Mark one of my alerts as read",
    dependencies=[CAN_SEE_MY_ALERTS],
    responses=NOT_FOUND_RESPONSE,
)
def read_my_alert(alert_id: AlertId, actor: CurrentUserDep, db: DbSession) -> MyAlertItem:
    return MyAlertService(db, actor).mark_read(alert_id)


@router.post(
    "/my-alerts/{alertId}/acknowledge",
    summary="Acknowledge an alert (for everyone who received it)",
    dependencies=[CAN_SEE_MY_ALERTS],
    responses=NOT_FOUND_RESPONSE,
)
def acknowledge_my_alert(alert_id: AlertId, actor: CurrentUserDep, db: DbSession) -> MyAlertItem:
    return MyAlertService(db, actor).acknowledge(alert_id)
