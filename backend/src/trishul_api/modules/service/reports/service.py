"""Service reports: the inspection and repair record of one visit.

Lifecycle (separate from the trip, which only records travel):
  * The engineer arrives (stopping the trip puts the visit On site) and starts the report. The checklist of
    the best-matching svc.checklist_template is copied into it, so later edits to the template never change
    a report that already exists.
  * While the work goes on the engineer fills in the checklist, findings, root cause and work done.
  * Submitting closes the visit (Completed, service_ended_at) and says what happens next: nothing, parts
    needed, a revisit on a date, or escalation. The call moves to Report submitted / Awaiting parts /
    Revisit scheduled accordingly. Marking the call Completed stays a separate step.
One visit has at most one report; a call with three visits has three reports.
"""

from datetime import UTC, date, datetime
from decimal import Decimal

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from trishul_api.auth import CurrentUser
from trishul_api.common.concurrency import check_row_version
from trishul_api.common.errors import ApiError, NotFound
from trishul_api.db.models import (
    Attachment,
    ChecklistTemplate,
    ChecklistTemplateItem,
    Customer,
    Employee,
    LookupType,
    LookupValue,
    MachineUnit,
    ReportChecklistItem,
    ServiceCall,
    ServiceCallCurrentStatus,
    ServiceReport,
    ServiceVisit,
)
from trishul_api.modules.core.documents import storage
from trishul_api.modules.service.access import FINISHED_STATUSES, call_visibility
from trishul_api.modules.service.assignment import assignees, plan_visit
from trishul_api.modules.service.reports.schemas import (
    CallVisit,
    ChecklistAnswer,
    ReportAttachment,
    ReportSummary,
    ServiceReportListItem,
    ServiceReportOut,
    ServiceReportSubmit,
    ServiceReportUpdate,
)
from trishul_api.modules.service.repository import ServiceCallRepository
from trishul_api.modules.service.status_log import record_status_change

ENTITY_TYPE = "svc.service_report"
SIGN_PERMISSIONS = ("svc.report.submit", "svc.call.assign")
MAX_SIGNATURE_BYTES = 1024 * 1024
_NEXT_STATUS: dict[str, ServiceCallCurrentStatus] = {
    "None": "Report submitted",
    "Escalate": "Report submitted",
    "Parts required": "Awaiting parts",
    "Revisit": "Revisit scheduled",
}


def _now() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def can_write(db: Session, user: CurrentUser, call: ServiceCall) -> bool:
    """The engineers on the call, and the team lead who assigns it."""
    if not user.can(*SIGN_PERMISSIONS):
        return False
    return user.can("svc.call.assign") or (user.employee_id is not None and user.employee_id in assignees(db, call))


def can_read(db: Session, user: CurrentUser, call: ServiceCall) -> bool:
    if not call.is_active or not user.can_use_branch(call.branch_id):
        return False
    return call_visibility(user, ServiceCallRepository(db).team_members).allows(assignees(db, call))


class ServiceReportService:
    def __init__(self, db: Session, actor: CurrentUser) -> None:
        self._db = db
        self._actor = actor

    # ------------------------------------------------------------------ reads

    def visits_of_call(self, call_id: int) -> list[CallVisit]:
        call = self._call(call_id)
        writer = can_write(self._db, self._actor, call)
        rows = self._db.execute(
            select(ServiceVisit, func.concat_ws(" ", Employee.first_name, Employee.last_name).label("engineer"))
            .join(Employee, Employee.id == ServiceVisit.engineer_employee_id)
            .where(ServiceVisit.service_call_id == call_id, ServiceVisit.is_active, ServiceVisit.status != "Cancelled")
            .order_by(ServiceVisit.visit_no)
        ).all()
        reports = {
            r.service_visit_id: r
            for r in self._db.scalars(
                select(ServiceReport).where(
                    ServiceReport.service_visit_id.in_([row.ServiceVisit.id for row in rows]), ServiceReport.is_active
                )
            )
        }
        out: list[CallVisit] = []
        for row in rows:
            visit, report = row.ServiceVisit, reports.get(row.ServiceVisit.id)
            out.append(
                CallVisit(
                    id=visit.id,
                    visit_no=visit.visit_no,
                    visit_purpose=visit.visit_purpose,
                    status=visit.status,
                    engineer_name=row.engineer or None,
                    planned_date=visit.planned_date,
                    service_started_at=visit.service_started_at,
                    service_ended_at=visit.service_ended_at,
                    next_action=visit.next_action,
                    report=(
                        ReportSummary(
                            id=report.id,
                            report_no=report.report_no,
                            status="Submitted" if report.submitted_at else "Draft",
                            submitted_at=report.submitted_at,
                        )
                        if report
                        else None
                    ),
                    can_start_report=writer and report is None and visit.status == "On site",
                )
            )
        return out

    def for_visit(self, visit_id: int) -> ServiceReportOut:
        visit, call = self._visit(visit_id)
        report = self._report_of(visit.id)
        if report is None:
            raise NotFound("This visit has no service report yet.")
        return self._out(report, visit, call)

    def reports_of_call(self, call_id: int) -> list[ServiceReportOut]:
        """Every report of a call, in full (one per visit that has one)."""
        call = self._call(call_id)
        visits = self._db.scalars(
            select(ServiceVisit)
            .where(ServiceVisit.service_call_id == call_id, ServiceVisit.is_active)
            .order_by(ServiceVisit.visit_no)
        ).all()
        out = []
        for visit in visits:
            report = self._report_of(visit.id)
            if report is not None:
                out.append(self._out(report, visit, call))
        return out

    def search(self, text: str | None, status: str | None, limit: int) -> list[ServiceReportListItem]:
        """Find reports by report number, call number or customer; only calls the user may open."""
        statement = (
            select(ServiceReport, ServiceVisit, ServiceCall, Customer.name.label("customer"))
            .join(ServiceVisit, ServiceVisit.id == ServiceReport.service_visit_id)
            .join(ServiceCall, ServiceCall.id == ServiceVisit.service_call_id)
            .join(Customer, Customer.id == ServiceCall.customer_id)
            .where(ServiceReport.is_active)
            .order_by(ServiceReport.id.desc())
        )
        if text and text.strip():
            escaped = text.strip().replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
            pattern = f"%{escaped}%"
            statement = statement.where(
                or_(
                    ServiceReport.report_no.like(pattern, escape="\\"),
                    ServiceCall.call_no.like(pattern, escape="\\"),
                    Customer.name.like(pattern, escape="\\"),
                )
            )
        if status == "Submitted":
            statement = statement.where(ServiceReport.submitted_at.is_not(None))
        elif status == "Draft":
            statement = statement.where(ServiceReport.submitted_at.is_(None))
        out: list[ServiceReportListItem] = []
        for row in self._db.execute(statement.limit(limit * 4)):
            report, visit, call = row.ServiceReport, row.ServiceVisit, row.ServiceCall
            if not can_read(self._db, self._actor, call):
                continue
            engineer = self._db.get(Employee, visit.engineer_employee_id)
            name = " ".join(p for p in (engineer.first_name, engineer.last_name) if p) if engineer else None
            out.append(
                ServiceReportListItem(
                    id=report.id,
                    report_no=report.report_no,
                    status="Submitted" if report.submitted_at else "Draft",
                    service_call_id=call.id,
                    service_visit_id=visit.id,
                    call_no=call.call_no,
                    customer_name=row.customer,
                    visit_no=visit.visit_no,
                    engineer_name=name or None,
                    next_action=visit.next_action if report.submitted_at else None,
                    submitted_at=report.submitted_at,
                    updated_at=report.updated_at,
                )
            )
            if len(out) >= limit:
                break
        return out

    def signature(self, report_id: int) -> bytes:
        """The customer's signature image of a report."""
        report = self._db.get(ServiceReport, report_id)
        if report is None or not report.is_active:
            raise NotFound("Service report not found.")
        self._visit(report.service_visit_id)
        row = (
            self._db.get(Attachment, report.customer_signature_attachment_id)
            if report.customer_signature_attachment_id
            else None
        )
        raw = storage.read(row.s3_key) if row is not None and row.is_active else None
        if raw is None:
            raise NotFound("This report has no customer signature.")
        return raw

    # ------------------------------------------------------------------ writes

    def start(self, visit_id: int) -> ServiceReportOut:
        """Open the report of a visit (or return the one already open) and copy the checklist into it."""
        visit, call = self._visit(visit_id)
        existing = self._report_of(visit.id)
        if existing is not None:
            return self._out(existing, visit, call)
        self._require_writer(call)
        if visit.status != "On site":
            raise ApiError("Reach the customer's site (stop the trip) before starting the service report.")
        report = ServiceReport(
            service_visit_id=visit.id,
            report_no=self._report_no(call, visit),
            created_by_user_id=self._actor.id,
        )
        self._db.add(report)
        self._db.flush()
        template = self._best_template(call)
        if template is not None:
            for item in self._db.scalars(
                select(ChecklistTemplateItem)
                .where(ChecklistTemplateItem.checklist_template_id == template.id, ChecklistTemplateItem.is_active)
                .order_by(ChecklistTemplateItem.sequence, ChecklistTemplateItem.id)
            ):
                self._db.add(
                    ReportChecklistItem(
                        service_report_id=report.id,
                        checklist_template_item_id=item.id,
                        item_text=item.item_text,
                        created_by_user_id=self._actor.id,
                    )
                )
        if call.current_status in ("Trip started", "Reached site"):
            record_status_change(
                self._db, call.id, call.current_status, "In progress", self._actor.id, "Report started"
            )
            call.current_status = "In progress"
            call.updated_at = _now()
            call.updated_by_user_id = self._actor.id
        self._db.commit()
        return self._out(report, visit, call)

    def update(self, report_id: int, expected: bytes, data: ServiceReportUpdate) -> ServiceReportOut:
        report, visit, call = self._editable(report_id)
        check_row_version(report.row_version, expected)
        sent = data.model_fields_set
        self._check_lookups(data, sent)
        for field in (
            "hmr_reading",
            "machine_condition_lookup_id",
            "complaint_observed",
            "findings",
            "failure_code_lookup_id",
            "action_taken",
            "labour_hours",
            "recommendations",
            "customer_signed_name",
            "customer_signed_mobile",
        ):
            if field in sent:
                setattr(report, field, getattr(data, field))
        if data.checklist:
            rows = {
                r.id: r
                for r in self._db.scalars(
                    select(ReportChecklistItem).where(
                        ReportChecklistItem.service_report_id == report.id, ReportChecklistItem.is_active
                    )
                )
            }
            for answer in data.checklist:
                row = rows.get(answer.id)
                if row is None:
                    raise ApiError(
                        "That question is not on this report.", errors={"checklist": [f"Unknown question {answer.id}"]}
                    )
                row.is_ok = answer.is_ok
                row.response_value = answer.response_value
                row.remarks = answer.remarks
                row.updated_at = _now()
                row.updated_by_user_id = self._actor.id
        report.updated_at = _now()
        report.updated_by_user_id = self._actor.id
        self._db.commit()
        self._db.refresh(report)
        return self._out(report, visit, call)

    def submit(self, report_id: int, expected: bytes, data: ServiceReportSubmit) -> ServiceReportOut:
        report, visit, call = self._editable(report_id)
        check_row_version(report.row_version, expected)
        self._check_complete(report, data)
        now = _now()

        report.submitted_at = now
        report.is_parts_required = data.next_action == "Parts required"
        if data.customer_unavailable_reason and not report.customer_signed_name:
            report.customer_signed_name = "Customer not available"
        report.updated_at, report.updated_by_user_id = now, self._actor.id

        visit.status = "Completed"
        visit.service_ended_at = now
        visit.next_action = data.next_action
        if data.customer_unavailable_reason:
            visit.remarks = f"Customer not available: {data.customer_unavailable_reason}"[:500]
        visit.updated_at, visit.updated_by_user_id = now, self._actor.id

        target = _NEXT_STATUS[data.next_action]
        if data.next_action == "Revisit" and data.next_visit_date is not None:
            plan_visit(self._db, call, visit.engineer_employee_id, data.next_visit_date, self._actor.id, now)
        if call.current_status != target and call.current_status not in FINISHED_STATUSES:
            record_status_change(
                self._db, call.id, call.current_status, target, self._actor.id, f"Service report {report.report_no}"
            )
            call.current_status = target
            call.updated_at, call.updated_by_user_id = now, self._actor.id
        self._db.commit()
        self._db.refresh(report)
        return self._out(report, visit, call)

    def sign(self, report_id: int, file_name: str | None, raw: bytes) -> ServiceReportOut:
        """Store the customer's signature (a PNG drawn on the phone) and attach it to the report."""
        report, visit, call = self._editable(report_id)
        if len(raw) > MAX_SIGNATURE_BYTES:
            raise ApiError("That signature image is too large.")
        name = storage.clean_file_name(file_name or "signature.png")
        if not name.lower().endswith(".png"):
            raise ApiError("The signature must be a PNG image.")
        content_type = storage.validate_file(name, raw)
        row = Attachment(
            entity_type=ENTITY_TYPE,
            entity_id=report.id,
            category="Signature",
            file_name=name,
            content_type=content_type,
            file_size_bytes=len(raw),
            s3_key=storage.store(ENTITY_TYPE, report.id, name, raw),
            created_by_user_id=self._actor.id,
        )
        self._db.add(row)
        self._db.flush()
        report.customer_signature_attachment_id = row.id
        report.updated_at, report.updated_by_user_id = _now(), self._actor.id
        self._db.commit()
        self._db.refresh(report)
        return self._out(report, visit, call)

    # ------------------------------------------------------------------ rules

    def _check_complete(self, report: ServiceReport, data: ServiceReportSubmit) -> None:
        problems: dict[str, list[str]] = {}
        if report.machine_condition_lookup_id is None:
            problems["machineConditionLookupId"] = ["Say what condition the machine is in."]
        if not report.findings:
            problems["findings"] = ["Write what you found."]
        if data.next_action == "None":
            if not report.failure_code_lookup_id:
                problems["failureCodeLookupId"] = ["Choose the root cause."]
            if not report.action_taken:
                problems["actionTaken"] = ["Write the work you did."]
        if data.next_action == "Revisit":
            if data.next_visit_date is None:
                problems["nextVisitDate"] = ["Choose the date of the next visit."]
            elif data.next_visit_date < date.today():
                problems["nextVisitDate"] = ["The next visit cannot be in the past."]
        if not report.customer_signed_name and not data.customer_unavailable_reason:
            problems["customerSignedName"] = ["Enter the customer's name, or say why the customer could not sign."]
        unanswered = [row for row in self._checklist(report.id) if row.mandatory and not row.answered]
        if unanswered:
            problems["checklist"] = [f"Answer: {row.answer.item_text}" for row in unanswered[:10]]
        if problems:
            raise ApiError("The service report is not complete.", errors=problems)

    def _check_lookups(self, data: ServiceReportUpdate, sent: set[str]) -> None:
        errors: dict[str, list[str]] = {}
        for field, type_code in (
            ("machine_condition_lookup_id", "MACHINE_CONDITION"),
            ("failure_code_lookup_id", "FAILURE_CODE"),
        ):
            value = getattr(data, field)
            if field in sent and value is not None and not self._lookup_of_type(value, type_code):
                errors[_camel(field)] = [f"Not a valid {type_code.replace('_', ' ').lower()}."]
        if errors:
            raise ApiError("Some of the selected values don't exist.", errors=errors)

    def _lookup_of_type(self, value_id: int, type_code: str) -> bool:
        return (
            self._db.scalars(
                select(LookupValue.id)
                .join(LookupType, LookupType.id == LookupValue.lookup_type_id)
                .where(LookupValue.id == value_id, LookupType.code == type_code, LookupValue.is_active)
                .limit(1)
            ).first()
            is not None
        )

    def _best_template(self, call: ServiceCall) -> ChecklistTemplate | None:
        """The most specific active checklist for the call's brand, machine model and call type."""
        model_id = (
            self._db.scalar(select(MachineUnit.model_id).where(MachineUnit.id == call.machine_unit_id))
            if call.machine_unit_id is not None
            else None
        )
        best: tuple[int, int, ChecklistTemplate] | None = None
        for template in self._db.scalars(select(ChecklistTemplate).where(ChecklistTemplate.is_active)):
            score = 0
            for wanted, actual in (
                (template.principal_id, call.principal_id),
                (template.machine_model_id, model_id),
                (template.call_type_lookup_id, call.call_type_lookup_id),
            ):
                if wanted is None:
                    continue
                if wanted != actual:
                    break
                score += 1
            else:
                if best is None or (score, template.id) > (best[0], best[1]):
                    best = (score, template.id, template)
        return best[2] if best else None

    # ------------------------------------------------------------------ lookups of records

    def _call(self, call_id: int) -> ServiceCall:
        call = self._db.get(ServiceCall, call_id)
        if call is None or not can_read(self._db, self._actor, call):
            raise NotFound("Service call not found.")
        return call

    def _visit(self, visit_id: int) -> tuple[ServiceVisit, ServiceCall]:
        visit = self._db.get(ServiceVisit, visit_id)
        if visit is None or not visit.is_active:
            raise NotFound("Visit not found.")
        return visit, self._call(visit.service_call_id)

    def _report_of(self, visit_id: int) -> ServiceReport | None:
        return self._db.scalars(
            select(ServiceReport).where(ServiceReport.service_visit_id == visit_id, ServiceReport.is_active)
        ).first()

    def _editable(self, report_id: int) -> tuple[ServiceReport, ServiceVisit, ServiceCall]:
        report = self._db.get(ServiceReport, report_id)
        if report is None or not report.is_active:
            raise NotFound("Service report not found.")
        visit, call = self._visit(report.service_visit_id)
        self._require_writer(call)
        if report.submitted_at is not None:
            raise ApiError("This report has been submitted and can no longer be changed.")
        return report, visit, call

    def _require_writer(self, call: ServiceCall) -> None:
        if not can_write(self._db, self._actor, call):
            raise NotFound("Service call not found, or not assigned to you.")

    def _report_no(self, call: ServiceCall, visit: ServiceVisit) -> str:
        number = f"{call.call_no}/R{visit.visit_no}"
        if len(number) > 30:
            raise ApiError(f"Report number {number} is longer than 30 characters.")
        return number

    # ------------------------------------------------------------------ output

    def _checklist(self, report_id: int) -> list["_ChecklistRow"]:
        rows = self._db.execute(
            select(ReportChecklistItem, ChecklistTemplateItem)
            .outerjoin(
                ChecklistTemplateItem, ChecklistTemplateItem.id == ReportChecklistItem.checklist_template_item_id
            )
            .where(ReportChecklistItem.service_report_id == report_id, ReportChecklistItem.is_active)
            .order_by(ChecklistTemplateItem.sequence, ReportChecklistItem.id)
        ).all()
        return [_ChecklistRow(row[0], row[1]) for row in rows]

    def _label(self, lookup_id: int | None) -> str | None:
        return self._db.scalar(select(LookupValue.label).where(LookupValue.id == lookup_id)) if lookup_id else None

    def _out(self, report: ServiceReport, visit: ServiceVisit, call: ServiceCall) -> ServiceReportOut:
        engineer = self._db.get(Employee, visit.engineer_employee_id)
        name = " ".join(p for p in (engineer.first_name, engineer.last_name) if p) if engineer else None
        rows = self._checklist(report.id)
        first = next((r.item for r in rows if r.item is not None), None)
        template = self._db.get(ChecklistTemplate, first.checklist_template_id) if first else None
        attachments = self._db.scalars(
            select(Attachment)
            .where(
                Attachment.entity_type == ENTITY_TYPE,
                Attachment.entity_id == report.id,
                Attachment.is_active,
                Attachment.category != "Signature",
            )
            .order_by(Attachment.id)
        ).all()
        return ServiceReportOut(
            id=report.id,
            report_no=report.report_no,
            status="Submitted" if report.submitted_at else "Draft",
            service_visit_id=visit.id,
            service_call_id=call.id,
            call_no=call.call_no,
            visit_no=visit.visit_no,
            visit_purpose=visit.visit_purpose,
            visit_status=visit.status,
            engineer_name=name or None,
            engineer_code=engineer.employee_code if engineer else None,
            engineer_mobile=engineer.mobile if engineer else None,
            customer_name=self._db.scalar(select(Customer.name).where(Customer.id == call.customer_id)),
            checklist_name=template.name if template else None,
            inspection_note=template.inspection_note if template else None,
            attachments=[
                ReportAttachment(
                    id=a.id,
                    file_name=a.file_name,
                    category=a.category,
                    content_type=a.content_type,
                    file_size_bytes=a.file_size_bytes,
                    uploaded_at=a.created_at,
                )
                for a in attachments
            ],
            service_started_at=visit.service_started_at,
            service_ended_at=visit.service_ended_at,
            hmr_reading=report.hmr_reading,
            machine_condition_lookup_id=report.machine_condition_lookup_id,
            machine_condition=self._label(report.machine_condition_lookup_id),
            complaint_observed=report.complaint_observed,
            findings=report.findings,
            failure_code_lookup_id=report.failure_code_lookup_id,
            failure_code=self._label(report.failure_code_lookup_id),
            action_taken=report.action_taken,
            is_parts_required=bool(report.is_parts_required),
            labour_hours=report.labour_hours if report.labour_hours is None else Decimal(report.labour_hours),
            recommendations=report.recommendations,
            customer_signed_name=report.customer_signed_name,
            customer_signed_mobile=report.customer_signed_mobile,
            customer_signature_document_id=report.customer_signature_attachment_id,
            next_action=visit.next_action if report.submitted_at else None,
            submitted_at=report.submitted_at,
            can_edit=report.submitted_at is None and can_write(self._db, self._actor, call),
            checklist=[
                ChecklistAnswer(
                    id=row.answer.id,
                    template_item_id=row.answer.checklist_template_item_id,
                    item_text=row.answer.item_text,
                    response_type=row.item.response_type if row.item else "OK Not OK",
                    is_mandatory=bool(row.mandatory),
                    is_ok=row.answer.is_ok,
                    response_value=row.answer.response_value,
                    remarks=row.answer.remarks,
                    photo_document_id=row.answer.photo_attachment_id,
                )
                for row in rows
            ],
            row_version=report.row_version,
        )


class _ChecklistRow:
    """A checklist answer with the template question it came from."""

    def __init__(self, answer: ReportChecklistItem, item: ChecklistTemplateItem | None) -> None:
        self.answer = answer
        self.item = item

    @property
    def mandatory(self) -> bool:
        return bool(self.item.is_mandatory) if self.item else False

    @property
    def answered(self) -> bool:
        a = self.answer
        return a.is_ok is not None or bool(a.response_value) or a.photo_attachment_id is not None


def _camel(name: str) -> str:
    head, *rest = name.split("_")
    return head + "".join(part.title() for part in rest)
