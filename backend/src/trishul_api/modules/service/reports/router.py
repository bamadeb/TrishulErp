from typing import Annotated, Literal

from fastapi import APIRouter, Depends, File, Path, Query, Response, UploadFile

from trishul_api.auth import CurrentUserDep, DbSession, require_permission
from trishul_api.common.concurrency import if_match_row_version
from trishul_api.common.errors import CONCURRENCY_RESPONSES, NOT_FOUND_RESPONSE, ApiError, problem_response
from trishul_api.modules.service.access import CAN_VIEW_CALLS
from trishul_api.modules.service.reports.schemas import (
    CallVisit,
    ChecklistAnswerType,
    ChecklistBrandOption,
    ChecklistTemplateInput,
    ChecklistTemplateOut,
    ChecklistTemplateUpdate,
    ReportOutcome,
    ServiceReportListItem,
    ServiceReportOut,
    ServiceReportSubmit,
    ServiceReportUpdate,
)
from trishul_api.modules.service.reports.service import SIGN_PERMISSIONS, ServiceReportService
from trishul_api.modules.service.reports.templates import ChecklistTemplateService

ANSWER_TYPES = [
    ChecklistAnswerType(value="OK Not OK", label="OK / Not OK", description="A pass or fail tick."),
    ChecklistAnswerType(value="Number", label="Number", description="A reading, e.g. pressure or hours."),
    ChecklistAnswerType(value="Text", label="Text", description="A short written answer."),
    ChecklistAnswerType(value="Photo", label="Photo", description="A photo of the check point."),
]

REPORT_OUTCOMES = [
    ReportOutcome(
        value="None",
        label="Work done",
        description="The machine is fixed; nothing more to do.",
        call_becomes="Report submitted",
        requires_visit_date=False,
    ),
    ReportOutcome(
        value="Parts required",
        label="Parts required",
        description="The call waits for parts.",
        call_becomes="Awaiting parts",
        requires_visit_date=False,
    ),
    ReportOutcome(
        value="Revisit",
        label="Revisit needed",
        description="Plan another visit on a date.",
        call_becomes="Revisit scheduled",
        requires_visit_date=True,
    ),
    ReportOutcome(
        value="Escalate",
        label="Escalate",
        description="Needs a specialist; the team lead is told.",
        call_becomes="Report submitted",
        requires_visit_date=False,
    ),
]

router = APIRouter(prefix="/svc", tags=["service-reports"])

CAN_VIEW = Depends(require_permission(*CAN_VIEW_CALLS))
CAN_WRITE = Depends(require_permission(*SIGN_PERMISSIONS))
# Read-only: service engineers (svc.report.submit) need the checklists to fill in their reports.
CAN_VIEW_CHECKLISTS = Depends(require_permission("svc.checklist.manage", "svc.call.assign", "svc.report.submit"))
CAN_MANAGE_CHECKLISTS = Depends(require_permission("svc.checklist.manage"))

CallId = Annotated[int, Path(alias="callId", gt=0)]
VisitId = Annotated[int, Path(alias="visitId", gt=0)]
ReportId = Annotated[int, Path(alias="reportId", gt=0)]
TemplateId = Annotated[int, Path(alias="templateId", gt=0)]

_MAX_SIGNATURE_UPLOAD = 1024 * 1024 + 1


@router.get(
    "/service-calls/{callId}/visits",
    summary="The visits of a call with the state of each visit's service report",
    dependencies=[CAN_VIEW],
    responses=NOT_FOUND_RESPONSE,
)
def list_service_call_visits(call_id: CallId, actor: CurrentUserDep, db: DbSession) -> list[CallVisit]:
    return ServiceReportService(db, actor).visits_of_call(call_id)


@router.get(
    "/service-calls/{callId}/reports",
    summary="Every service report of a call in full: inspection checklist, findings, files and the engineer",
    dependencies=[CAN_VIEW],
    responses=NOT_FOUND_RESPONSE,
)
def list_service_call_reports(call_id: CallId, actor: CurrentUserDep, db: DbSession) -> list[ServiceReportOut]:
    return ServiceReportService(db, actor).reports_of_call(call_id)


@router.get(
    "/service-reports",
    summary="Search service reports by report number, call number or customer",
    dependencies=[CAN_VIEW],
)
def list_service_reports(
    actor: CurrentUserDep,
    db: DbSession,
    search: Annotated[str | None, Query(max_length=100, description="Report no, call no or customer name.")] = None,
    status: Annotated[Literal["Draft", "Submitted"] | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
) -> list[ServiceReportListItem]:
    return ServiceReportService(db, actor).search(search, status, limit)


@router.get(
    "/service-report-outcomes",
    summary="Outcomes for the \"Outcome of this visit\" dropdown when finishing a visit",
    dependencies=[CAN_VIEW],
)
def list_service_report_outcomes() -> list[ReportOutcome]:
    return REPORT_OUTCOMES


@router.get(
    "/service-visits/{visitId}/report",
    summary="The service report of a visit",
    dependencies=[CAN_VIEW],
    responses=NOT_FOUND_RESPONSE,
)
def get_service_visit_report(visit_id: VisitId, actor: CurrentUserDep, db: DbSession) -> ServiceReportOut:
    return ServiceReportService(db, actor).for_visit(visit_id)


@router.post(
    "/service-visits/{visitId}/report",
    summary="Start the service report of a visit (the engineer is on site); copies in the inspection checklist",
    dependencies=[CAN_WRITE],
    responses={**NOT_FOUND_RESPONSE, 400: problem_response("The engineer has not reached the site yet.")},
)
def start_service_report(visit_id: VisitId, actor: CurrentUserDep, db: DbSession) -> ServiceReportOut:
    return ServiceReportService(db, actor).start(visit_id)


@router.patch(
    "/service-reports/{reportId}",
    summary="Fill in the report: inspection answers, findings, root cause, work done, customer details",
    dependencies=[CAN_WRITE],
    responses={**NOT_FOUND_RESPONSE, **CONCURRENCY_RESPONSES},
)
def update_service_report(
    report_id: ReportId,
    data: ServiceReportUpdate,
    actor: CurrentUserDep,
    db: DbSession,
    row_version: Annotated[bytes, Depends(if_match_row_version)],
) -> ServiceReportOut:
    return ServiceReportService(db, actor).update(report_id, row_version, data)


@router.get(
    "/service-reports/{reportId}/customer-signature",
    summary="The customer's signature image of a report",
    dependencies=[CAN_VIEW],
    response_class=Response,
    responses={**NOT_FOUND_RESPONSE, 200: {"content": {"image/png": {}}}},
)
def get_service_report_signature(report_id: ReportId, actor: CurrentUserDep, db: DbSession) -> Response:
    raw = ServiceReportService(db, actor).signature(report_id)
    return Response(
        content=raw,
        media_type="image/png",
        headers={"X-Content-Type-Options": "nosniff", "Cache-Control": "private, no-store"},
    )


@router.post(
    "/service-reports/{reportId}/customer-signature",
    summary="Attach the customer's signature (a PNG drawn on the phone) to the report",
    dependencies=[CAN_WRITE],
    responses={**NOT_FOUND_RESPONSE, 400: problem_response("The file is not a PNG image.")},
)
def sign_service_report(
    report_id: ReportId,
    actor: CurrentUserDep,
    db: DbSession,
    file: Annotated[UploadFile, File(description="The signature as a PNG image")],
) -> ServiceReportOut:
    raw = file.file.read(_MAX_SIGNATURE_UPLOAD)
    if not raw:
        raise ApiError("The uploaded file is empty.")
    return ServiceReportService(db, actor).sign(report_id, file.filename, raw)


@router.post(
    "/service-reports/{reportId}/submit",
    summary="Submit the report: closes the visit and moves the call on (done, parts needed, revisit, escalate)",
    dependencies=[CAN_WRITE],
    responses={
        **NOT_FOUND_RESPONSE,
        **CONCURRENCY_RESPONSES,
        400: problem_response("The report is incomplete, or it was already submitted."),
    },
)
def submit_service_report(
    report_id: ReportId,
    data: ServiceReportSubmit,
    actor: CurrentUserDep,
    db: DbSession,
    row_version: Annotated[bytes, Depends(if_match_row_version)],
) -> ServiceReportOut:
    return ServiceReportService(db, actor).submit(report_id, row_version, data)


# ---------------------------------------------------------------- checklist templates


@router.get(
    "/checklist-brands",
    summary="Brands for the Brand dropdown of an inspection checklist",
    dependencies=[CAN_VIEW_CHECKLISTS],
)
def list_checklist_brands(db: DbSession, actor: CurrentUserDep) -> list[ChecklistBrandOption]:
    return ChecklistTemplateService(db, actor).brands()


@router.get(
    "/checklist-answer-types",
    summary="Answer types for the Answer dropdown of an inspection checklist question",
    dependencies=[CAN_VIEW_CHECKLISTS],
)
def list_checklist_answer_types() -> list[ChecklistAnswerType]:
    return ANSWER_TYPES


@router.get(
    "/checklist-templates",
    summary="Inspection checklists",
    dependencies=[CAN_VIEW_CHECKLISTS],
)
def list_checklist_templates(
    db: DbSession, actor: CurrentUserDep, include_inactive: Annotated[bool, Query(alias="includeInactive")] = False
) -> list[ChecklistTemplateOut]:
    return ChecklistTemplateService(db, actor).list(include_inactive)


@router.post(
    "/checklist-templates",
    summary="Add an inspection checklist",
    status_code=201,
    dependencies=[CAN_MANAGE_CHECKLISTS],
    responses={400: problem_response("Some of the selected values don't exist.")},
)
def create_checklist_template(
    data: ChecklistTemplateInput, actor: CurrentUserDep, db: DbSession
) -> ChecklistTemplateOut:
    return ChecklistTemplateService(db, actor).create(data)


@router.get(
    "/checklist-templates/{templateId}",
    summary="One inspection checklist with its questions",
    dependencies=[CAN_VIEW_CHECKLISTS],
    responses=NOT_FOUND_RESPONSE,
)
def get_checklist_template(template_id: TemplateId, actor: CurrentUserDep, db: DbSession) -> ChecklistTemplateOut:
    return ChecklistTemplateService(db, actor).get(template_id)


@router.patch(
    "/checklist-templates/{templateId}",
    summary="Change an inspection checklist (reports already started keep their copy)",
    dependencies=[CAN_MANAGE_CHECKLISTS],
    responses={**NOT_FOUND_RESPONSE, **CONCURRENCY_RESPONSES},
)
def update_checklist_template(
    template_id: TemplateId,
    data: ChecklistTemplateUpdate,
    actor: CurrentUserDep,
    db: DbSession,
    row_version: Annotated[bytes, Depends(if_match_row_version)],
) -> ChecklistTemplateOut:
    return ChecklistTemplateService(db, actor).update(template_id, row_version, data)
