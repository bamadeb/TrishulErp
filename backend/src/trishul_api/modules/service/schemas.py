from pydantic import Field

from trishul_api.common.schemas import ApiModel, InputModel, PageQuery, RowVersion, UtcDateTime
from trishul_api.db.models import ServiceCallCoverageType, ServiceCallCurrentStatus, ServiceCallPriority

# Value lists come from the svc.service_call CHECK constraints, through the generated models.
CallStatus = ServiceCallCurrentStatus
CallPriority = ServiceCallPriority
CoverageType = ServiceCallCoverageType

# A phone / landline: digits with optional +, spaces, hyphens or brackets. The column holds 15 chars.
_PHONE_PATTERN = r"^[0-9+\-() ]{6,15}$"


class ServiceCallQuery(PageQuery):
    status: list[CallStatus] = Field(default_factory=list)
    priority: list[CallPriority] = Field(default_factory=list)


class ServiceCallListItem(ApiModel):
    """A row of the call register."""

    id: int
    call_no: str
    received_at: UtcDateTime
    principal_code: str
    customer_name: str
    machine_serial_no: str | None
    machine_model: str | None
    complaint_description: str
    priority: CallPriority
    is_machine_down: bool
    is_asc_priority: bool
    coverage_type: CoverageType | None
    current_status: CallStatus
    assigned_engineer_name: str | None
    oem_call_id: str | None
    sla_due_at: UtcDateTime | None
    row_version: RowVersion


class ServiceCallCreate(InputModel):
    """Log a new service call (office). call_no, status (Logged) and received_by are set by the server;
    branch and brand default to the ones selected in the app (the X-Branch-Id / X-Principal-Id headers)."""

    customer_id: int
    machine_unit_id: int | None = None
    branch_id: int | None = Field(None, description="Defaults to the selected branch.")
    principal_id: int | None = Field(None, description="Brand; defaults to the selected brand.")
    call_type_lookup_id: int = Field(description="A value of the CALL_TYPE lookup.")
    call_source_lookup_id: int = Field(description="A value of the CALL_SOURCE lookup.")
    priority: CallPriority = "Normal"
    complaint_description: str = Field(min_length=1, max_length=2000)
    caller_name: str | None = Field(None, max_length=100)
    caller_phone: str = Field(pattern=_PHONE_PATTERN, max_length=15)
    is_machine_down: bool = False
    received_at: UtcDateTime | None = Field(None, description="Defaults to now.")


class ServiceCallTriageUpdate(InputModel):
    """A team lead's quick triage from the call list: reassign an engineer and/or change priority.
    Only the fields sent are changed; send engineerId null to unassign."""

    priority: CallPriority | None = None
    engineer_id: int | None = None


class MachineOptionQuery(ApiModel):
    search: str | None = Field(None, max_length=60)
    customer_id: int | None = None
    limit: int = Field(20, ge=1, le=50)


class MachineUnitOption(ApiModel):
    id: int
    serial_number: str
    model_name: str | None
    customer_name: str | None


class EngineerOptionQuery(ApiModel):
    search: str | None = Field(None, max_length=60)
    limit: int = Field(50, ge=1, le=100)


class EngineerOption(ApiModel):
    id: int
    name: str
    employee_code: str


class AssignedServiceCallQuery(PageQuery):
    """Filter for the mobile 'my calls' list. No engineer or branch parameter: the engineer is the
    signed-in user and the branch / brand come from the context headers, so the client cannot widen
    the result to other people's calls."""

    status: list[CallStatus] = Field(default_factory=list)


class AssignedServiceCallListItem(ApiModel):
    """A service call assigned to the signed-in engineer, with the site location the trip screen needs."""

    id: int
    call_no: str
    received_at: UtcDateTime
    principal_code: str
    customer_name: str
    site_name: str | None
    site_address: str | None
    site_latitude: float | None
    site_longitude: float | None
    machine_serial_no: str | None
    machine_model: str | None
    complaint_description: str
    priority: CallPriority
    is_machine_down: bool
    is_asc_priority: bool
    coverage_type: CoverageType | None
    current_status: CallStatus
    caller_name: str | None
    caller_phone: str
    sla_due_at: UtcDateTime | None
    row_version: RowVersion
