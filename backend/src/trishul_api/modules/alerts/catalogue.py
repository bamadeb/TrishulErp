"""The alert type catalogue: what can be alerted on, and which settings each type takes.

Types live in code, not in the database: each one is a tested query, and an Alert Master rule only picks a type
and fills in its parameters. Adding a type means adding it here, to conditions.py, and to the
CK_core_alert_rule_alert_type / CK_core_alert_alert_type constraints (a migration).

Parameter values are stored on core.alert_rule.parameters as JSON with the keys below (camelCase, the same
keys the Angular form uses).
"""

from dataclasses import dataclass, field
from typing import Any, Literal, get_args

from trishul_api.common.errors import ApiError
from trishul_api.db.models.generated.svc import ServiceCallCurrentStatus, ServiceCallPriority
from trishul_api.modules.service.access import FINISHED_STATUSES

ParamKind = Literal["integer", "multiselect", "boolean"]
TriggerKind = Literal["Scheduled", "Event"]
EntityType = Literal["svc.service_call", "core.machine_unit", "svc.service_contract"]

# Recipients that come from the record itself rather than from the rule.
CALL_RECIPIENTS = ("Assigned engineer", "Call logged by")

PRIORITIES: tuple[str, ...] = get_args(ServiceCallPriority)
OPEN_STATUSES: tuple[str, ...] = tuple(s for s in get_args(ServiceCallCurrentStatus) if s not in FINISHED_STATUSES)
SLA_STAGES = ("Due soon", "Breached")
COVERAGE_KINDS = ("Warranty", "AMC")


@dataclass(frozen=True)
class ParamDef:
    key: str
    label: str
    kind: ParamKind
    required: bool = False
    default: Any = None
    min: int | None = None
    max: int | None = None
    unit: str | None = None
    options: tuple[str, ...] = ()
    help: str | None = None


@dataclass(frozen=True)
class AlertTypeDef:
    code: str
    name: str
    description: str
    module: str
    trigger: TriggerKind
    entity_type: EntityType
    params: tuple[ParamDef, ...] = ()
    dynamic_recipients: tuple[str, ...] = field(default=())


_PRIORITY_FILTER = ParamDef(
    "priorities", "Only these priorities", "multiselect", options=PRIORITIES, help="Leave empty for every priority."
)

CATALOGUE: dict[str, AlertTypeDef] = {
    t.code: t
    for t in (
        AlertTypeDef(
            code="SVC_CALL_UNASSIGNED",
            name="Service call not assigned in time",
            description="A call is still not assigned to an engineer some time after it was logged.",
            module="Service",
            trigger="Scheduled",
            entity_type="svc.service_call",
            params=(
                ParamDef("afterMinutes", "Not assigned after", "integer", True, 30, 5, 10080, "minutes"),
                _PRIORITY_FILTER,
                ParamDef("machineDownOnly", "Only when the machine is down", "boolean", default=False),
            ),
            dynamic_recipients=CALL_RECIPIENTS,
        ),
        AlertTypeDef(
            code="SVC_SLA_DUE",
            name="SLA due soon or breached",
            description=(
                "The call's SLA due time is near or has passed. Due times and the warning window come from the "
                "SLA rules (svc.sla_rule), not from this alert rule."
            ),
            module="Service",
            trigger="Scheduled",
            entity_type="svc.service_call",
            params=(
                ParamDef(
                    "stages",
                    "Alert when",
                    "multiselect",
                    True,
                    list(SLA_STAGES),
                    options=SLA_STAGES,
                    help="Due soon uses the SLA rule's 'warn before' minutes.",
                ),
                _PRIORITY_FILTER,
            ),
            dynamic_recipients=CALL_RECIPIENTS,
        ),
        AlertTypeDef(
            code="SVC_STATUS_STALE",
            name="Call status unchanged too long",
            description="A call has stayed in the same status longer than the set time.",
            module="Service",
            trigger="Scheduled",
            entity_type="svc.service_call",
            params=(
                ParamDef("afterHours", "Unchanged for", "integer", True, 24, 1, 720, "hours"),
                ParamDef(
                    "statuses",
                    "Only these statuses",
                    "multiselect",
                    options=OPEN_STATUSES,
                    help="Leave empty for every open status.",
                ),
                _PRIORITY_FILTER,
            ),
            dynamic_recipients=CALL_RECIPIENTS,
        ),
        AlertTypeDef(
            code="SVC_AWAITING_PARTS",
            name="Call waiting for parts too long",
            description="A call has been in 'Awaiting parts' longer than the set time.",
            module="Service",
            trigger="Scheduled",
            entity_type="svc.service_call",
            params=(
                ParamDef("afterDays", "Waiting for", "integer", True, 3, 1, 90, "days"),
                _PRIORITY_FILTER,
            ),
            dynamic_recipients=CALL_RECIPIENTS,
        ),
        AlertTypeDef(
            code="SVC_CALL_REOPENED",
            name="Service call reopened",
            description="Raised the moment a call is reopened (every reopen).",
            module="Service",
            trigger="Event",
            entity_type="svc.service_call",
            params=(_PRIORITY_FILTER,),
            dynamic_recipients=CALL_RECIPIENTS,
        ),
        AlertTypeDef(
            code="SVC_PART_REQUEST",
            name="Parts requested on a call",
            description=(
                "Raised the moment an engineer requests parts on a call (every request). Resolved once all the "
                "requested parts are quoted or rejected."
            ),
            module="Service",
            trigger="Event",
            entity_type="svc.service_call",
            params=(_PRIORITY_FILTER,),
            dynamic_recipients=CALL_RECIPIENTS,
        ),
        AlertTypeDef(
            code="MACHINE_COVERAGE_EXPIRY",
            name="Machine warranty or AMC ending",
            description="A machine's warranty, or a customer's AMC contract, ends within the set number of days.",
            module="Service",
            trigger="Scheduled",
            entity_type="core.machine_unit",
            params=(
                ParamDef("daysBefore", "Ends within", "integer", True, 30, 1, 365, "days"),
                ParamDef("coverage", "Coverage", "multiselect", True, list(COVERAGE_KINDS), options=COVERAGE_KINDS),
            ),
        ),
    )
}


def get_type(code: str) -> AlertTypeDef:
    alert_type = CATALOGUE.get(code)
    if alert_type is None:
        raise ApiError("Unknown alert type.", errors={"alertType": [f"Unknown alert type {code}"]})
    return alert_type


def validate_parameters(alert_type: AlertTypeDef, raw: dict[str, Any] | None) -> dict[str, Any]:
    """The rule's parameters checked against the type, with defaults filled in and unknown keys refused."""
    raw = dict(raw or {})
    errors: dict[str, list[str]] = {}
    known = {p.key for p in alert_type.params}
    for key in sorted(set(raw) - known):
        errors[f"parameters.{key}"] = ["Not a setting of this alert type."]
    result: dict[str, Any] = {}
    for param in alert_type.params:
        value = raw.get(param.key, param.default)
        name = f"parameters.{param.key}"
        if param.kind == "integer":
            if value is None:
                if param.required:
                    errors[name] = ["Required."]
                continue
            if isinstance(value, bool) or not isinstance(value, int):
                errors[name] = ["Enter a whole number."]
                continue
            if (param.min is not None and value < param.min) or (param.max is not None and value > param.max):
                errors[name] = [f"Enter a number from {param.min} to {param.max}."]
                continue
            result[param.key] = value
        elif param.kind == "boolean":
            if value is None:
                value = False
            if not isinstance(value, bool):
                errors[name] = ["Must be true or false."]
                continue
            result[param.key] = value
        else:  # multiselect
            values = [] if value is None else value
            if not isinstance(values, list) or not all(isinstance(v, str) for v in values):
                errors[name] = ["Choose from the list."]
                continue
            unknown = [v for v in values if v not in param.options]
            if unknown:
                errors[name] = [f"Not a valid choice: {', '.join(unknown)}"]
                continue
            if param.required and not values:
                errors[name] = ["Choose at least one."]
                continue
            # Keep the catalogue's order and drop repeats.
            result[param.key] = [option for option in param.options if option in values]
    if errors:
        raise ApiError("Some alert settings are not valid.", errors=errors)
    return result
