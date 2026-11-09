"""The records that carry documents, besides those a module registers itself (trk.manual_travel).

Each target says what the record is called, who may see and change its documents, how to find it by name
and how to describe it in the library. Access mirrors the module's own screens: whoever can open a service
call can attach documents to it; customers and employees follow their manage permissions. Holders of
core.document.manage (Administration > Documents) can add to any of them.

To add a module: write a target here (or next to the module) and register it; no other file changes.
"""

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from trishul_api.auth import CurrentUser
from trishul_api.db.models import Customer, Employee, ServiceCall, ServiceReport, ServiceVisit
from trishul_api.modules.core.documents.registry import DocumentTarget, register_target
from trishul_api.modules.service.access import call_visibility
from trishul_api.modules.service.assignment import assignees
from trishul_api.modules.service.repository import ServiceCallRepository


def _like(text: str) -> str:
    return "%" + text.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"


# ---------------------------------------------------------------- service calls


def _call_visible(db: Session, user: CurrentUser, call_id: int) -> bool:
    call = db.get(ServiceCall, call_id)
    if call is None or not call.is_active or not user.can_use_branch(call.branch_id):
        return False
    visibility = call_visibility(user, ServiceCallRepository(db).team_members)
    return visibility.allows(assignees(db, call))


def _call_exists(db: Session, _user: CurrentUser, call_id: int) -> bool:
    call = db.get(ServiceCall, call_id)
    return call is not None and call.is_active


def _call_labels(db: Session, ids: list[int]) -> dict[int, str]:
    rows = db.execute(
        select(ServiceCall.id, ServiceCall.call_no, Customer.name)
        .join(Customer, Customer.id == ServiceCall.customer_id)
        .where(ServiceCall.id.in_(ids))
    )
    return {r.id: f"{r.call_no} · {r.name}" for r in rows}


def _call_search(db: Session, user: CurrentUser, text: str, limit: int) -> list[tuple[int, str]]:
    # The endpoint is for document administrators, who may attach to any call, so no visibility filter.
    statement = (
        select(ServiceCall.id, ServiceCall.call_no, Customer.name)
        .join(Customer, Customer.id == ServiceCall.customer_id)
        .where(ServiceCall.is_active)
        .order_by(ServiceCall.id.desc())
        .limit(limit)
    )
    if text:
        pattern = _like(text)
        statement = statement.where(
            or_(ServiceCall.call_no.like(pattern, escape="\\"), Customer.name.like(pattern, escape="\\"))
        )
    return [(r.id, f"{r.call_no} · {r.name}") for r in db.execute(statement)]


register_target(
    DocumentTarget(
        entity_type="svc.service_call",
        label="Service call",
        can_view=_call_visible,
        can_edit=_call_visible,
        exists=_call_exists,
        describe=_call_labels,
        search=_call_search,
    )
)


# ---------------------------------------------------------------- customers


def _customer_view(db: Session, user: CurrentUser, customer_id: int) -> bool:
    customer = db.get(Customer, customer_id)
    return customer is not None and customer.is_active and user.can("core.customer.view", "core.customer.manage")


def _customer_edit(db: Session, user: CurrentUser, customer_id: int) -> bool:
    return _customer_view(db, user, customer_id) and user.can("core.customer.manage")


def _customer_exists(db: Session, _user: CurrentUser, customer_id: int) -> bool:
    customer = db.get(Customer, customer_id)
    return customer is not None and customer.is_active


def _customer_labels(db: Session, ids: list[int]) -> dict[int, str]:
    return {
        r.id: f"{r.name} ({r.code})"
        for r in db.execute(select(Customer.id, Customer.name, Customer.code).where(Customer.id.in_(ids)))
    }


def _customer_search(db: Session, user: CurrentUser, text: str, limit: int) -> list[tuple[int, str]]:
    statement = (
        select(Customer.id, Customer.name, Customer.code).where(Customer.is_active).order_by(Customer.name).limit(limit)
    )
    if text:
        pattern = _like(text)
        statement = statement.where(
            or_(Customer.name.like(pattern, escape="\\"), Customer.code.like(pattern, escape="\\"))
        )
    return [(r.id, f"{r.name} ({r.code})") for r in db.execute(statement)]


register_target(
    DocumentTarget(
        entity_type="core.customer",
        label="Customer",
        can_view=_customer_view,
        can_edit=_customer_edit,
        exists=_customer_exists,
        describe=_customer_labels,
        search=_customer_search,
    )
)


# ---------------------------------------------------------------- employees


def _employee_view(db: Session, user: CurrentUser, employee_id: int) -> bool:
    employee = db.get(Employee, employee_id)
    return (
        employee is not None
        and employee.is_active
        and user.can_use_branch(employee.branch_id)
        and user.can("core.employee.view", "core.employee.manage")
    )


def _employee_edit(db: Session, user: CurrentUser, employee_id: int) -> bool:
    return _employee_view(db, user, employee_id) and user.can("core.employee.manage")


def _employee_exists(db: Session, user: CurrentUser, employee_id: int) -> bool:
    employee = db.get(Employee, employee_id)
    return employee is not None and employee.is_active and user.can_use_branch(employee.branch_id)


def _employee_name(first: str | None, last: str | None, code: str) -> str:
    return f"{' '.join(p for p in (first, last) if p) or code} ({code})"


def _employee_labels(db: Session, ids: list[int]) -> dict[int, str]:
    rows = db.execute(
        select(Employee.id, Employee.first_name, Employee.last_name, Employee.employee_code).where(Employee.id.in_(ids))
    )
    return {r.id: _employee_name(r.first_name, r.last_name, r.employee_code) for r in rows}


def _employee_search(db: Session, user: CurrentUser, text: str, limit: int) -> list[tuple[int, str]]:
    statement = (
        select(Employee.id, Employee.first_name, Employee.last_name, Employee.employee_code, Employee.branch_id)
        .where(Employee.is_active)
        .order_by(Employee.first_name, Employee.last_name)
    )
    if text:
        pattern = _like(text)
        statement = statement.where(
            or_(
                Employee.first_name.like(pattern, escape="\\"),
                Employee.last_name.like(pattern, escape="\\"),
                Employee.employee_code.like(pattern, escape="\\"),
            )
        )
    rows = [r for r in db.execute(statement.limit(limit * 3)) if user.can_use_branch(r.branch_id)]
    return [(r.id, _employee_name(r.first_name, r.last_name, r.employee_code)) for r in rows[:limit]]


register_target(
    DocumentTarget(
        entity_type="core.employee",
        label="Employee",
        can_view=_employee_view,
        can_edit=_employee_edit,
        exists=_employee_exists,
        describe=_employee_labels,
        search=_employee_search,
        # An employee's photo is the same table's Photo row; the employee screen manages it.
        exclude_categories=("Photo",),
    )
)


# ---------------------------------------------------------------- service reports (photos of the work)


def _report_call(db: Session, report_id: int) -> ServiceCall | None:
    report = db.get(ServiceReport, report_id)
    visit = db.get(ServiceVisit, report.service_visit_id) if report is not None and report.is_active else None
    return db.get(ServiceCall, visit.service_call_id) if visit is not None else None


def _report_view(db: Session, user: CurrentUser, report_id: int) -> bool:
    from trishul_api.modules.service.reports.service import can_read

    call = _report_call(db, report_id)
    return call is not None and can_read(db, user, call)


def _report_edit(db: Session, user: CurrentUser, report_id: int) -> bool:
    from trishul_api.modules.service.reports.service import can_write

    call = _report_call(db, report_id)
    report = db.get(ServiceReport, report_id)
    return (
        call is not None
        and report is not None
        and report.submitted_at is None
        and _report_view(db, user, report_id)
        and can_write(db, user, call)
    )


def _report_exists(db: Session, _user: CurrentUser, report_id: int) -> bool:
    return _report_call(db, report_id) is not None


def _report_labels(db: Session, ids: list[int]) -> dict[int, str]:
    return {
        r.id: f"Service report {r.report_no}"
        for r in db.execute(select(ServiceReport.id, ServiceReport.report_no).where(ServiceReport.id.in_(ids)))
    }


register_target(
    DocumentTarget(
        entity_type="svc.service_report",
        label="Service report",
        can_view=_report_view,
        can_edit=_report_edit,
        exists=_report_exists,
        describe=_report_labels,
        # The customer's signature is part of the report form, not a document to browse.
        exclude_categories=("Signature",),
    )
)
