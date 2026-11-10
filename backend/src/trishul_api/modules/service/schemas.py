import datetime as dt
from typing import Literal

from pydantic import Field

from trishul_api.common.schemas import ApiModel, InputModel, PageQuery, RowVersion, UtcDateTime
from trishul_api.db.models import ServiceCallCoverageType, ServiceCallCurrentStatus, ServiceCallPriority
from trishul_api.modules.service.contracts.schemas import MachineAsc

# Value lists come from the svc.service_call CHECK constraints, through the generated models.
CallStatus = ServiceCallCurrentStatus
CallPriority = ServiceCallPriority
CoverageType = ServiceCallCoverageType
CallCover = Literal["ASC + Warranty", "ASC", "Warranty", "Chargeable", "Goodwill", "Not covered", "Unknown"]
Availability = Literal["Available", "Half-day leave", "Holiday", "On leave"]

# A phone / landline: digits with optional +, spaces, hyphens or brackets. The column holds 15 chars.
_PHONE_PATTERN = r"^[0-9+\-() ]{6,15}$"


class ServiceCallQuery(PageQuery):
    status: list[CallStatus] = Field(default_factory=list)
    priority: list[CallPriority] = Field(default_factory=list)
    visit_date: dt.date | None = Field(None, description="Only calls with a visit planned (not started) that day.")


class CallEngineer(ApiModel):
    """An engineer on a call."""

    id: int
    name: str


class ServiceCallListItem(ApiModel):
    """A row of the call register."""

    id: int
    call_no: str
    received_at: UtcDateTime
    principal_code: str
    customer_id: int
    customer_name: str
    machine_unit_id: int | None
    machine_serial_no: str | None
    machine_model: str | None
    complaint_description: str
    priority: CallPriority
    is_machine_down: bool
    is_asc_priority: bool
    coverage_type: CoverageType | None
    current_status: CallStatus
    assigned_engineer_id: int | None
    assigned_engineer_name: str | None = Field(description="The lead engineer.")
    support_engineers: list[CallEngineer] = Field(default_factory=list)
    oem_call_id: str | None
    sla_due_at: UtcDateTime | None
    row_version: RowVersion
    is_trip_ongoing: bool = Field(False, description="A trip of this call has been started and not yet stopped.")
    planned_visit_date: dt.date | None = Field(
        None, description="Earliest day a visit of the call is planned for and not yet started."
    )


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


class ServiceCallStatusChange(InputModel):
    """Move a call to another status. The server checks the user may make that move."""

    status: CallStatus
    remarks: str | None = Field(None, max_length=500)


class CallStatusLogItem(ApiModel):
    """One row of a call's status history."""

    id: int
    from_status: str | None
    to_status: str
    changed_at: UtcDateTime
    changed_by_name: str | None
    remarks: str | None


class ServiceCallTriageUpdate(InputModel):
    """A team lead's quick triage from the call list: link the real customer and machine, change the
    engineers and/or change priority. Only the fields sent are changed; send engineerId null to unassign
    everyone and machineUnitId null to take the machine off the call."""

    priority: CallPriority | None = None
    engineer_id: int | None = Field(None, description="The lead engineer.")
    support_engineer_ids: list[int] = Field(
        default_factory=list, max_length=20, description="Everyone else on the call; replaces the current list."
    )
    customer_id: int | None = None
    machine_unit_id: int | None = Field(None, description="Must be registered to the call's customer.")
    visit_date: dt.date | None = Field(None, description="Plan the lead engineer's visit for this day.")


class UnassignedCallQuery(PageQuery):
    priority: list[CallPriority] = Field(default_factory=list)


class UnassignedCallItem(ApiModel):
    """A call waiting for an engineer, with what the team lead weighs up: how urgent, who pays, and where."""

    id: int
    call_no: str
    received_at: UtcDateTime
    principal_code: str
    branch_name: str | None
    customer_name: str
    location: str | None = Field(description="The site's address, or else the customer's billing address.")
    machine_unit_id: int | None
    machine_serial_no: str | None
    machine_model: str | None
    machine_warranty_end_date: dt.date | None
    complaint_description: str
    priority: CallPriority
    is_machine_down: bool
    is_asc_priority: bool
    coverage_type: CoverageType | None
    cover: CallCover = Field("Unknown", description="Unknown: no machine is linked, so cover can't be worked out.")
    sla_due_at: UtcDateTime | None
    row_version: RowVersion


class EngineerWorkloadQuery(ApiModel):
    on_date: dt.date
    call_id: int | None = Field(None, description="Adds the distance to this call and puts the closest first.")


class EngineerWorkload(ApiModel):
    """An engineer on a given day, best choice first."""

    id: int
    name: str
    employee_code: str
    branch_name: str | None
    availability: Availability = "Available"
    calls_on_date: int = Field(0, description="Calls with a visit for this engineer on the day.")
    open_calls: int = Field(0, description="Unfinished calls the engineer is on, as lead or support, on any day.")
    distance_km: float | None = Field(
        None, description="From the engineer's last known position to the site; null if either is unknown."
    )
    same_branch: bool = Field(False, description="Same branch as the call.")


class MachineOptionQuery(ApiModel):
    search: str | None = Field(None, max_length=60)
    customer_id: int | None = None
    limit: int = Field(20, ge=1, le=50)


class MachineUnitOption(ApiModel):
    id: int
    serial_number: str
    model_name: str | None
    customer_name: str | None
    asc: MachineAsc | None = Field(None, description="The machine's ASC today; null when it has never had one.")


class EngineerOptionQuery(ApiModel):
    search: str | None = Field(None, max_length=60)
    limit: int = Field(50, ge=1, le=100)


class EngineerOption(ApiModel):
    id: int
    name: str
    employee_code: str


class ServiceCallDetail(ApiModel):
    """Everything the call detail page shows."""

    id: int
    call_no: str
    received_at: UtcDateTime
    branch_name: str | None
    principal_code: str
    principal_name: str | None
    customer_id: int
    customer_name: str
    customer_phone: str | None
    machine_unit_id: int | None
    machine_serial_no: str | None
    machine_model: str | None
    machine_model_code: str | None
    machine_product_line: str | None
    machine_engine_number: str | None
    machine_registration_number: str | None
    machine_warranty_end_date: dt.date | None
    machine_hmr: float | None
    machine_is_active: bool | None = Field(
        None, description="False when the machine has since been deactivated; null when no machine."
    )
    complaint_description: str
    call_type: str | None
    call_source: str | None
    priority: CallPriority
    is_machine_down: bool
    is_asc_priority: bool
    coverage_type: CoverageType | None
    current_status: CallStatus
    assigned_engineer_id: int | None
    assigned_engineer_name: str | None = Field(description="The lead engineer.")
    support_engineers: list[CallEngineer] = Field(default_factory=list)
    caller_name: str | None
    caller_phone: str
    oem_call_id: str | None
    source_reference: str | None
    sla_due_at: UtcDateTime | None
    first_response_at: UtcDateTime | None
    closed_at: UtcDateTime | None
    site_name: str | None
    site_address: str | None
    needs_master_linking: bool
    asc: MachineAsc | None = Field(None, description="The machine's ASC today; null without a machine or ASC.")
    allowed_statuses: list[CallStatus] = Field(
        default_factory=list, description="Statuses the signed-in user may move this call to."
    )
    row_version: RowVersion


class AssignedServiceCallQuery(PageQuery):
    """Filter for the mobile 'my calls' list. No engineer or branch parameter: the engineer is the
    signed-in user and the branch / brand come from the context headers, so the client cannot widen
    the result to other people's calls."""

    status: list[CallStatus] = Field(default_factory=list)
    visit_date: dt.date | None = Field(None, description="Only calls with my visit planned for this day.")
    sort: str | None = Field(
        None,
        max_length=40,
        description="Default: my planned visit date (earliest first, calls with no date last), then priority. "
        "Also visitDate, priority, receivedAt, slaDueAt, callNo; prefix with '-' for descending.",
    )


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
    planned_visit_date: dt.date | None = Field(
        None, description="The day my visit is planned for (earliest, not yet started); None = not planned yet."
    )
    row_version: RowVersion
