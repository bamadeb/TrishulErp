import datetime as dt
from decimal import Decimal
from typing import Literal

from pydantic import Field

from trishul_api.common.schemas import MOBILE_PATTERN, ApiModel, InputModel, RowVersion, UtcDateTime
from trishul_api.db.models import ServiceVisitNextAction, ServiceVisitStatus, ServiceVisitVisitPurpose
from trishul_api.db.models.generated.svc import ChecklistTemplateItemResponseType

NextAction = ServiceVisitNextAction
ResponseType = ChecklistTemplateItemResponseType
ReportStatus = Literal["Draft", "Submitted"]


# ---------------------------------------------------------------- the report of a visit


class ChecklistAnswer(ApiModel):
    """One inspection question of a report and the engineer's answer."""

    id: int
    template_item_id: int | None
    item_text: str
    response_type: ResponseType
    is_mandatory: bool
    is_ok: bool | None = Field(None, description="For 'OK Not OK' questions: true = OK, false = Not OK.")
    response_value: str | None = Field(None, description="For Number and Text questions.")
    remarks: str | None
    photo_document_id: int | None = Field(None, description="Photo of this check point (see /core/documents).")


class ReportAttachment(ApiModel):
    """A photo or file attached to a report (download with GET /core/documents/{id}/content)."""

    id: int
    file_name: str
    category: str
    content_type: str | None
    file_size_bytes: int | None
    uploaded_at: UtcDateTime


class ServiceReportListItem(ApiModel):
    """One row of the service report search."""

    id: int
    report_no: str
    status: ReportStatus
    service_call_id: int
    service_visit_id: int
    call_no: str
    customer_name: str | None
    visit_no: int
    engineer_name: str | None
    next_action: NextAction | None
    submitted_at: UtcDateTime | None
    updated_at: UtcDateTime | None


class ServiceReportOut(ApiModel):
    """The service report of one visit: inspection checklist, findings, work done and customer sign-off."""

    id: int
    report_no: str
    status: ReportStatus
    service_visit_id: int
    service_call_id: int
    call_no: str
    visit_no: int
    visit_purpose: ServiceVisitVisitPurpose
    visit_status: ServiceVisitStatus
    engineer_name: str | None
    engineer_code: str | None
    engineer_mobile: str | None
    customer_name: str | None
    checklist_name: str | None = Field(None, description="The checklist template the questions were copied from.")
    inspection_note: str | None = Field(None, description="The checklist's guidance note for the engineer.")
    attachments: list[ReportAttachment]
    service_started_at: UtcDateTime | None
    service_ended_at: UtcDateTime | None
    hmr_reading: Decimal | None
    machine_condition_lookup_id: int | None
    machine_condition: str | None
    complaint_observed: str | None
    findings: str | None
    failure_code_lookup_id: int | None
    failure_code: str | None
    action_taken: str | None
    is_parts_required: bool
    labour_hours: Decimal | None
    recommendations: str | None
    customer_signed_name: str | None
    customer_signed_mobile: str | None
    customer_signature_document_id: int | None
    next_action: NextAction | None
    submitted_at: UtcDateTime | None
    can_edit: bool = Field(description="False once submitted, or for someone who is not on the call.")
    checklist: list[ChecklistAnswer]
    row_version: RowVersion


class ReportOutcome(ApiModel):
    """A way a visit can end (the "Outcome of this visit" dropdown) and what it does to the call."""

    value: NextAction
    label: str
    description: str
    call_becomes: str = Field(description="The status the call moves to when the report is submitted.")
    requires_visit_date: bool = Field(description="True when the next visit date must be given (Revisit).")


class ChecklistAnswerInput(InputModel):
    id: int = Field(gt=0, description="The id of the report's question (ChecklistAnswer.id).")
    is_ok: bool | None = None
    response_value: str | None = Field(None, max_length=200)
    remarks: str | None = Field(None, max_length=300)


class ServiceReportUpdate(InputModel):
    """Only the fields sent are changed; send null to clear one."""

    hmr_reading: Decimal | None = Field(None, ge=0, max_digits=10, decimal_places=1)
    machine_condition_lookup_id: int | None = Field(None, gt=0, description="A value of the MACHINE_CONDITION lookup.")
    complaint_observed: str | None = Field(None, max_length=1000)
    findings: str | None = Field(None, max_length=2000)
    failure_code_lookup_id: int | None = Field(None, gt=0, description="A value of the FAILURE_CODE lookup.")
    action_taken: str | None = Field(None, max_length=2000)
    labour_hours: Decimal | None = Field(None, ge=0, le=999, max_digits=6, decimal_places=2)
    recommendations: str | None = Field(None, max_length=1000)
    customer_signed_name: str | None = Field(None, max_length=100)
    customer_signed_mobile: str | None = Field(None, pattern=MOBILE_PATTERN)
    checklist: list[ChecklistAnswerInput] | None = None


class ServiceReportSubmit(InputModel):
    """Finishing the visit: what happens to the call next."""

    next_action: NextAction = Field(
        description="None = work done; Parts required; Revisit (give nextVisitDate); Escalate = needs a specialist."
    )
    next_visit_date: dt.date | None = Field(None, description="Required for a Revisit.")
    customer_unavailable_reason: str | None = Field(
        None, max_length=300, description="Why the customer could not sign (instead of a customer name)."
    )


# ---------------------------------------------------------------- a call's visits


class ReportSummary(ApiModel):
    id: int
    report_no: str
    status: ReportStatus
    submitted_at: UtcDateTime | None


class CallVisit(ApiModel):
    """A visit of a service call and its report, if one was started."""

    id: int
    visit_no: int
    visit_purpose: ServiceVisitVisitPurpose
    status: ServiceVisitStatus
    engineer_name: str | None
    planned_date: dt.date | None
    service_started_at: UtcDateTime | None
    service_ended_at: UtcDateTime | None
    next_action: NextAction | None
    report: ReportSummary | None
    can_start_report: bool = Field(description="On site, no report yet, and the user may write it.")


# ---------------------------------------------------------------- checklist templates


class ChecklistItemOut(ApiModel):
    id: int
    sequence: int
    item_text: str
    response_type: ResponseType
    is_mandatory: bool


class ChecklistTemplateOut(ApiModel):
    id: int
    name: str
    principal_id: int | None
    principal_name: str | None
    machine_model_id: int | None
    machine_model_name: str | None
    call_type_lookup_id: int | None
    call_type: str | None
    is_active: bool
    inspection_note: str | None
    items: list[ChecklistItemOut]
    row_version: RowVersion


class ChecklistBrandOption(ApiModel):
    """A brand a checklist can be made for (the Brand dropdown)."""

    id: int
    name: str


class ChecklistAnswerType(ApiModel):
    """A way a question can be answered (the Answer dropdown)."""

    value: ResponseType
    label: str
    description: str


class ChecklistItemInput(InputModel):
    id: int | None = Field(
        None, gt=0, description="Send the id to keep (and edit) an existing question; omit for a new one."
    )
    item_text: str = Field(min_length=1, max_length=300)
    response_type: ResponseType = "OK Not OK"
    is_mandatory: bool = True


class ChecklistTemplateInput(InputModel):
    name: str = Field(min_length=1, max_length=120)
    principal_id: int | None = Field(None, gt=0, description="Blank = every brand.")
    machine_model_id: int | None = Field(None, gt=0, description="Blank = every model.")
    call_type_lookup_id: int | None = Field(None, gt=0, description="Blank = every call type.")
    inspection_note: str | None = Field(
        None, max_length=2000, description="Guidance for the engineer: what to look for, safety points."
    )
    items: list[ChecklistItemInput] = Field(min_length=1, max_length=60, description="In the order they are asked.")


class ChecklistTemplateUpdate(ChecklistTemplateInput):
    is_active: bool = True
