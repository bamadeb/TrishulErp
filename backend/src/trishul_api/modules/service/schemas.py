from pydantic import Field

from trishul_api.common.schemas import ApiModel, PageQuery, RowVersion, UtcDateTime
from trishul_api.db.models import ServiceCallCoverageType, ServiceCallCurrentStatus, ServiceCallPriority

# Value lists come from the svc.service_call CHECK constraints, through the generated models.
CallStatus = ServiceCallCurrentStatus
CallPriority = ServiceCallPriority
CoverageType = ServiceCallCoverageType


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
