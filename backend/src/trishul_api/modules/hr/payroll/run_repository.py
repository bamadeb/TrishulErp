"""Reads the salary structures and attendance a payroll month can use, and stores the run."""

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from trishul_api.db.models import (
    Attendance,
    Employee,
    PayrollRun,
    Payslip,
    PayslipLine,
    SalaryComponent,
    SalaryStructure,
    SalaryStructureLine,
)
from trishul_api.modules.hr.payroll.run_schemas import PayrollRunItem
from trishul_api.modules.hr.payroll.statutory_repository import month_end, month_start


@dataclass(frozen=True)
class PayableEmployee:
    employee_id: int
    company_id: int
    structure_id: int
    effective_from: date
    effective_to: date | None
    joining: date | None
    exited: date | None


@dataclass(frozen=True)
class PayableLine:
    structure_id: int
    salary_component_id: int
    code: str
    component_type: str
    calculation_type: str
    calculation_basis: str | None
    monthly_amount: Decimal | None
    percentage: Decimal | None
    formula: str | None
    is_prorated: bool
    include_in_gross: bool
    include_in_net_pay: bool
    is_pf_wage: bool
    is_esi_wage: bool
    display_order: int


class PayrollRunRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def payable(self, month: date) -> list[PayableEmployee]:
        start, end = month_start(month), month_end(month)
        ranked = (
            select(
                Employee.id.label("employee_id"),
                Employee.company_id.label("company_id"),
                SalaryStructure.id.label("structure_id"),
                SalaryStructure.effective_from.label("effective_from"),
                SalaryStructure.effective_to.label("effective_to"),
                Employee.date_of_joining.label("joining"),
                Employee.date_of_exit.label("exited"),
                func.row_number()
                .over(
                    partition_by=Employee.id,
                    order_by=(SalaryStructure.effective_from.desc(), SalaryStructure.id.desc()),
                )
                .label("rn"),
            )
            .join(SalaryStructure, SalaryStructure.employee_id == Employee.id)
            .where(
                Employee.is_active == True,  # noqa: E712
                Employee.status == "Active",
                SalaryStructure.is_active == True,  # noqa: E712
                SalaryStructure.effective_from <= end,
                or_(SalaryStructure.effective_to.is_(None), SalaryStructure.effective_to >= start),
            )
            .subquery()
        )
        rows = self._session.execute(select(ranked).where(ranked.c.rn == 1).order_by(ranked.c.employee_id)).all()
        return [
            PayableEmployee(
                employee_id=int(row.employee_id),
                company_id=int(row.company_id),
                structure_id=int(row.structure_id),
                effective_from=row.effective_from,
                effective_to=row.effective_to,
                joining=row.joining,
                exited=row.exited,
            )
            for row in rows
        ]

    def lines(self, structure_ids: list[int], month: date) -> list[PayableLine]:
        if not structure_ids:
            return []
        start, end = month_start(month), month_end(month)
        rows = self._session.execute(
            select(
                SalaryStructureLine.salary_structure_id,
                SalaryComponent.id,
                SalaryComponent.code,
                SalaryComponent.component_type,
                SalaryComponent.calculation_type,
                SalaryComponent.calculation_basis,
                SalaryStructureLine.monthly_amount,
                SalaryStructureLine.percentage,
                SalaryStructureLine.formula,
                SalaryComponent.is_prorated,
                SalaryComponent.include_in_gross,
                SalaryComponent.include_in_net_pay,
                SalaryComponent.is_pf_wage,
                SalaryComponent.is_esi_wage,
                SalaryComponent.display_order,
            )
            .join(SalaryComponent, SalaryComponent.id == SalaryStructureLine.salary_component_id)
            .where(
                SalaryStructureLine.salary_structure_id.in_(structure_ids),
                SalaryStructureLine.is_active == True,  # noqa: E712
                SalaryComponent.is_active == True,  # noqa: E712
                SalaryComponent.effective_from <= end,
                or_(SalaryComponent.effective_to.is_(None), SalaryComponent.effective_to >= start),
            )
            .order_by(SalaryComponent.display_order, SalaryComponent.code)
        ).all()
        return [
            PayableLine(
                structure_id=int(row[0]),
                salary_component_id=int(row[1]),
                code=row[2],
                component_type=row[3],
                calculation_type=row[4],
                calculation_basis=row[5],
                monthly_amount=row[6],
                percentage=row[7],
                formula=row[8],
                is_prorated=bool(row[9]),
                include_in_gross=bool(row[10]),
                include_in_net_pay=bool(row[11]),
                is_pf_wage=bool(row[12]),
                is_esi_wage=bool(row[13]),
                display_order=int(row[14] or 0),
            )
            for row in rows
        ]

    def lop_days(self, employee_id: int, first: date, last: date) -> Decimal:
        statuses = self._session.scalars(
            select(Attendance.status).where(
                Attendance.employee_id == employee_id,
                Attendance.attendance_date >= first,
                Attendance.attendance_date <= last,
                Attendance.is_active == True,  # noqa: E712
            )
        )
        lost = Decimal("0")
        for status in statuses:
            if status == "Absent":
                lost += Decimal("1")
            elif status == "Half day":
                lost += Decimal("0.5")
        return lost

    def existing(self, company_id: int, month: date) -> PayrollRun | None:
        return self._session.scalar(
            select(PayrollRun).where(
                PayrollRun.company_id == company_id,
                PayrollRun.period_month == month_start(month),
                PayrollRun.is_active == True,  # noqa: E712
            )
        )

    def add(self, row: PayrollRun | Payslip | PayslipLine) -> None:
        self._session.add(row)

    def flush(self) -> None:
        self._session.flush()

    def commit(self) -> None:
        self._session.commit()

    def list_runs(self) -> list[PayrollRunItem]:
        counts = (
            select(Payslip.payroll_run_id.label("run_id"), func.count(Payslip.id).label("employees"))
            .where(Payslip.is_active == True)  # noqa: E712
            .group_by(Payslip.payroll_run_id)
            .subquery()
        )
        rows = self._session.execute(
            select(PayrollRun, func.coalesce(counts.c.employees, 0))
            .outerjoin(counts, counts.c.run_id == PayrollRun.id)
            .where(PayrollRun.is_active == True)  # noqa: E712
            .order_by(PayrollRun.period_month.desc(), PayrollRun.id.desc())
        ).all()
        return [
            PayrollRunItem(
                id=int(run.id),
                period_month=run.period_month,
                run_date=run.run_date,
                status=run.status,
                employees=int(employees or 0),
                gross=run.total_gross or Decimal("0.00"),
                deductions=run.total_deductions or Decimal("0.00"),
                net_pay=run.total_net or Decimal("0.00"),
            )
            for run, employees in rows
        ]
