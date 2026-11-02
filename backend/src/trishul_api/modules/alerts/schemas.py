from typing import Any, Literal

from pydantic import Field

from trishul_api.common.schemas import ApiModel, InputModel, PageQuery, RowVersion, UtcDateTime
from trishul_api.db.models.generated.core import (
    AlertEntityType,
    AlertRuleAlertType,
    AlertRuleRecipientRecipientType,
    AlertRuleReraisePolicy,
    AlertRuleSeverity,
    AlertStatus,
)

# ------------------------------------------------------------------ catalogue


class AlertParamDef(ApiModel):
    key: str
    label: str
    kind: Literal["integer", "multiselect", "boolean"]
    required: bool
    default: Any = None
    min: int | None = None
    max: int | None = None
    unit: str | None = None
    options: list[str] = Field(default_factory=list)
    help: str | None = None


class AlertTypeItem(ApiModel):
    """One entry of the alert type catalogue: what a rule can alert on and the settings it takes."""

    code: AlertRuleAlertType
    name: str
    description: str
    module: str
    trigger: Literal["Scheduled", "Event"]
    entity_type: AlertEntityType
    params: list[AlertParamDef]
    recipient_types: list[AlertRuleRecipientRecipientType] = Field(
        description="Recipient kinds this type supports; record-based ones only where the record has them."
    )


# ------------------------------------------------------------------ Alert Master (rules)

AlertRuleStatusFilter = Literal["active", "inactive", "all"]


class AlertRuleQuery(PageQuery):
    status: AlertRuleStatusFilter = "all"
    alert_type: AlertRuleAlertType | None = None


class AlertRecipientIn(InputModel):
    recipient_type: AlertRuleRecipientRecipientType
    role_id: int | None = Field(None, description="For 'Role'.")
    app_user_id: int | None = Field(None, description="For 'User'.")


class AlertRecipientItem(ApiModel):
    recipient_type: AlertRuleRecipientRecipientType
    role_id: int | None
    role_name: str | None
    app_user_id: int | None
    user_name: str | None


class AlertRuleListItem(ApiModel):
    id: int
    code: str
    name: str
    alert_type: AlertRuleAlertType
    alert_type_name: str
    trigger: Literal["Scheduled", "Event"]
    severity: AlertRuleSeverity
    principal_name: str | None
    branch_name: str | None
    recipient_summary: str
    open_alert_count: int
    is_active: bool
    last_run_at: UtcDateTime | None


class AlertRuleDetail(AlertRuleListItem):
    description: str | None
    principal_id: int | None
    branch_id: int | None
    parameters: dict[str, Any]
    reraise_policy: AlertRuleReraisePolicy
    cooldown_minutes: int
    recipients: list[AlertRecipientItem]
    row_version: RowVersion


class AlertRuleCreate(InputModel):
    code: str = Field(min_length=1, max_length=40, description="Unique across all rules.")
    name: str = Field(min_length=1, max_length=150)
    description: str | None = Field(None, max_length=500)
    alert_type: AlertRuleAlertType
    principal_id: int | None = Field(None, description="Brand; blank = every brand.")
    branch_id: int | None = Field(None, description="Branch; blank = every branch.")
    severity: AlertRuleSeverity = "Warning"
    parameters: dict[str, Any] = Field(
        default_factory=dict, description="Settings of the alert type (see alert-types)."
    )
    reraise_policy: AlertRuleReraisePolicy = Field(
        "After resolution",
        description="Never: one alert per record, ever. After resolution: again when the condition returns.",
    )
    cooldown_minutes: int = Field(0, ge=0, le=43200, description="Quiet time after a resolution before re-raising.")
    recipients: list[AlertRecipientIn] = Field(min_length=1, max_length=50)


class AlertRuleUpdate(InputModel):
    """Only the fields sent are changed; recipients, when sent, replace the whole list."""

    code: str | None = Field(None, min_length=1, max_length=40)
    name: str | None = Field(None, min_length=1, max_length=150)
    description: str | None = Field(None, max_length=500)
    principal_id: int | None = None
    branch_id: int | None = None
    severity: AlertRuleSeverity | None = None
    parameters: dict[str, Any] | None = None
    reraise_policy: AlertRuleReraisePolicy | None = None
    cooldown_minutes: int | None = Field(None, ge=0, le=43200)
    recipients: list[AlertRecipientIn] | None = Field(None, min_length=1, max_length=50)


class AlertRuleTestMatch(ApiModel):
    entity_type: AlertEntityType
    entity_id: int
    title: str
    message: str
    recipients: list[str]


class AlertRuleTestResult(ApiModel):
    """A dry run of a saved rule: what matches now and who would be told. Nothing is raised or sent."""

    total: int
    matches: list[AlertRuleTestMatch]
    note: str | None = None


class NamedOption(ApiModel):
    id: int
    name: str


class AlertRuleFormOptions(ApiModel):
    alert_types: list[AlertTypeItem]
    roles: list[NamedOption]
    users: list[NamedOption]
    principals: list[NamedOption]
    branches: list[NamedOption]


# ------------------------------------------------------------------ my alerts (web inbox + mobile)

MyAlertStatusFilter = Literal["open", "all"]


class MyAlertQuery(PageQuery):
    status: MyAlertStatusFilter = Field("open", description="open = not yet resolved.")
    unread_only: bool = False


class MyAlertItem(ApiModel):
    id: int
    alert_type: AlertRuleAlertType
    rule_name: str
    severity: AlertRuleSeverity
    title: str
    message: str
    entity_type: AlertEntityType
    entity_id: int
    status: AlertStatus
    raised_at: UtcDateTime
    read_at: UtcDateTime | None
    acknowledged_at: UtcDateTime | None
    acknowledged_by_name: str | None
    resolved_at: UtcDateTime | None
    resolution_note: str | None


class MyAlertSummary(ApiModel):
    """For the bell: unread alerts that are not resolved yet, and all open ones."""

    unread: int
    open: int
