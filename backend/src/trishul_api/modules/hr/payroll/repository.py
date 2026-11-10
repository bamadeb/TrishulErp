"""Reads and writes hr.salary_component. Amounts for a month stay on the payslip."""

from typing import Any

from sqlalchemy import case, func, or_, select
from sqlalchemy.orm import Session

from trishul_api.common.paging import order_by_sort, paginate
from trishul_api.common.schemas import Page
from trishul_api.db.models import (
    AppUser,
    AuditLog,
    PayrollRun,
    Payslip,
    PayslipLine,
    SalaryComponent,
    SalaryComponentRevision,
    SalaryStructureLine,
)
from trishul_api.modules.hr.payroll.schemas import (
    SalaryComponentAuditItem,
    SalaryComponentListItem,
    SalaryComponentQuery,
    SalaryComponentRevisionItem,
    SalaryComponentSummary,
)

_PROCESSED = ("Processed", "Approved", "Paid", "Locked")
_SORT = {
    "code": SalaryComponent.code,
    "name": SalaryComponent.name,
    "componentType": SalaryComponent.component_type,
    "calculationMethod": SalaryComponent.calculation_type,
    "displayOrder": SalaryComponent.display_order,
}


class SalaryComponentRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def search(self, query: SalaryComponentQuery) -> Page[SalaryComponentListItem]:
        statement = select(*_list_columns())
        statement = _filter(statement, query)
        statement = order_by_sort(
            statement, query.sort, _SORT, default="displayOrder", tiebreaker=SalaryComponent.id.asc()
        )
        return paginate(self._session, statement, query, SalaryComponentListItem)

    def summary(self) -> SalaryComponentSummary:
        # Compare with =, not IS. SQL Server rejects "is_active IS 1".
        earning = case((SalaryComponent.component_type == "Earning", 1), else_=0)
        deduction = case((SalaryComponent.component_type == "Employee Deduction", 1), else_=0)
        active = case((SalaryComponent.is_active == True, 1), else_=0)  # noqa: E712
        total, earnings, deductions, actives = self._session.execute(
            select(
                func.count(),
                func.coalesce(func.sum(earning), 0),
                func.coalesce(func.sum(deduction), 0),
                func.coalesce(func.sum(active), 0),
            ).select_from(SalaryComponent)
        ).one()
        return SalaryComponentSummary(
            total=int(total or 0),
            earning=int(earnings or 0),
            deduction=int(deductions or 0),
            active=int(actives or 0),
        )

    def get(self, component_id: int) -> dict[str, Any] | None:
        row = self._session.execute(
            select(*_detail_columns()).where(SalaryComponent.id == component_id)
        ).mappings().first()
        return dict(row) if row else None

    def code_owner(self, code: str) -> int | None:
        return self._session.scalar(select(SalaryComponent.id).where(SalaryComponent.code == code).limit(1))

    def model(self, component_id: int) -> SalaryComponent | None:
        return self._session.get(SalaryComponent, component_id)

    def usage(self, component_id: int) -> tuple[bool, bool]:
        """(used by a structure or payslip, used by a processed payroll)."""
        on_structure = self._session.scalar(
            select(SalaryStructureLine.id).where(SalaryStructureLine.salary_component_id == component_id).limit(1)
        )
        on_payslip = self._session.scalar(
            select(PayslipLine.id).where(PayslipLine.salary_component_id == component_id).limit(1)
        )
        processed = self._session.scalar(
            select(PayslipLine.id)
            .join(Payslip, Payslip.id == PayslipLine.payslip_id)
            .join(PayrollRun, PayrollRun.id == Payslip.payroll_run_id)
            .where(
                PayslipLine.salary_component_id == component_id,
                PayrollRun.status.in_(_PROCESSED),
            )
            .limit(1)
        )
        return on_structure is not None or on_payslip is not None, processed is not None

    def user_name(self, user_id: int | None) -> str | None:
        if user_id is None:
            return None
        return self._session.scalar(select(AppUser.username).where(AppUser.id == user_id))

    def audit(self, component_id: int) -> list[SalaryComponentAuditItem]:
        rows = self._session.execute(
            select(AuditLog.action, AuditLog.changed_at, AppUser.username.label("changed_by"))
            .outerjoin(AppUser, AppUser.id == AuditLog.changed_by_user_id)
            .where(AuditLog.entity_type == "hr.salary_component", AuditLog.entity_id == component_id)
            .order_by(AuditLog.changed_at.desc(), AuditLog.id.desc())
            .limit(20)
        ).mappings()
        return [SalaryComponentAuditItem.model_validate(row) for row in rows]

    def revisions(self, component_id: int) -> list[SalaryComponentRevisionItem]:
        rows = self._session.execute(
            select(
                SalaryComponentRevision.revision_no,
                SalaryComponentRevision.calculation_type.label("calculation_method"),
                SalaryComponentRevision.calculation_basis,
                SalaryComponentRevision.effective_from,
                SalaryComponentRevision.effective_to,
                SalaryComponentRevision.superseded_at,
            )
            .where(SalaryComponentRevision.salary_component_id == component_id)
            .order_by(SalaryComponentRevision.revision_no.desc())
        ).mappings()
        return [SalaryComponentRevisionItem.model_validate(row) for row in rows]

    def next_revision(self, component_id: int) -> int:
        current = self._session.scalar(
            select(func.max(SalaryComponentRevision.revision_no)).where(
                SalaryComponentRevision.salary_component_id == component_id
            )
        )
        return int(current or 0) + 1

    def add(self, row: Any) -> None:
        self._session.add(row)

    def flush(self) -> None:
        self._session.flush()


def _list_columns() -> tuple[Any, ...]:
    return (
        SalaryComponent.id,
        SalaryComponent.code,
        SalaryComponent.name,
        SalaryComponent.component_type,
        SalaryComponent.calculation_type.label("calculation_method"),
        SalaryComponent.calculation_basis,
        SalaryComponent.include_in_gross,
        SalaryComponent.is_taxable,
        SalaryComponent.is_pf_wage.label("is_pf_applicable"),
        SalaryComponent.is_esi_wage.label("is_esi_applicable"),
        SalaryComponent.is_active,
        SalaryComponent.effective_from,
        SalaryComponent.effective_to,
        SalaryComponent.row_version,
    )


def _detail_columns() -> tuple[Any, ...]:
    return (
        *_list_columns(),
        SalaryComponent.description,
        SalaryComponent.display_order,
        SalaryComponent.fixed_amount,
        SalaryComponent.percentage,
        SalaryComponent.formula,
        SalaryComponent.is_prorated,
        SalaryComponent.allow_manual_override,
        SalaryComponent.include_in_net_pay,
        SalaryComponent.allow_reversal,
        SalaryComponent.display_in_statement,
        SalaryComponent.display_in_payslip,
        SalaryComponent.created_at,
        SalaryComponent.created_by_user_id,
        SalaryComponent.updated_at,
        SalaryComponent.updated_by_user_id,
    )


def _filter(statement: Any, query: SalaryComponentQuery) -> Any:
    if query.component_type:
        statement = statement.where(SalaryComponent.component_type == query.component_type)
    if query.calculation_method:
        statement = statement.where(SalaryComponent.calculation_type == query.calculation_method)
    if query.status == "active":
        statement = statement.where(SalaryComponent.is_active == True)  # noqa: E712
    elif query.status == "inactive":
        statement = statement.where(SalaryComponent.is_active == False)  # noqa: E712
    if query.search and query.search.strip():
        term = query.search.strip()
        statement = statement.where(
            or_(
                SalaryComponent.code.contains(term, autoescape=True),
                SalaryComponent.name.contains(term, autoescape=True),
            )
        )
    return statement
