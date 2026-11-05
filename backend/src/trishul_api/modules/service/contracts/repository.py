"""Reads for ASC contracts (svc.service_contract + svc.contract_coverage) and plans (svc.contract_plan).

An ASC covers one machine (one contract_coverage row). Its state is worked out from the dates: only a
cancellation is stored, so a contract never needs a nightly job to become "Expired".
"""

import builtins
import datetime as dt
from collections.abc import Collection
from decimal import Decimal
from typing import Any

from sqlalchemy import ColumnElement, Select, and_, case, func, literal, or_, select, true
from sqlalchemy.orm import Session, aliased

from trishul_api.auth import CurrentUser, RequestScope
from trishul_api.common.paging import SortColumns, order_by_sort, paginate
from trishul_api.common.schemas import Page
from trishul_api.db.models import (
    Branch,
    ContractCoverage,
    ContractPlan,
    ContractVisit,
    Customer,
    Designation,
    Employee,
    MachineModel,
    MachineUnit,
    Principal,
    ServiceCall,
    ServiceContract,
)
from trishul_api.modules.service.contracts.schemas import (
    AscCallVisit,
    ContractEngineerOption,
    ContractPlanItem,
    ContractPlanQuery,
    MachineAsc,
    ServiceContractDetail,
    ServiceContractListItem,
    ServiceContractQuery,
)

ASC = "ASC"
EXPIRING_DAYS = 30
COUNTABLE_STATUSES = ("Completed", "Closed")
"""A service call can be counted as ASC visits once the work is finished."""
_SERVICE_ENGINEER_DESIGNATION = "SERVICE_ENG"  # as in the service-call engineer picker

_SORT_COLUMNS: SortColumns = {
    "contractNo": ServiceContract.contract_no,
    "endDate": ServiceContract.end_date,
    "startDate": ServiceContract.start_date,
    "customerName": Customer.name,
    "machineSerialNo": MachineUnit.serial_number,
}


def state_expression(today: dt.date) -> ColumnElement[str]:
    """AscState in SQL: Cancelled is stored; the rest follows from the dates."""
    return case(
        (ServiceContract.status == "Cancelled", literal("Cancelled")),
        (ServiceContract.start_date > today, literal("Upcoming")),
        (ServiceContract.end_date < today, literal("Expired")),
        else_=literal("Active"),
    )


def visits_remaining() -> ColumnElement[int | None]:
    """Visits still available; never below 0 even if the register brought in more than the limit."""
    return case(
        (ServiceContract.visits_included.is_(None), None),
        (ServiceContract.visits_used >= ServiceContract.visits_included, 0),
        else_=ServiceContract.visits_included - ServiceContract.visits_used,
    ).label("visits_remaining")


def plan_total(price: Decimal | None, gst_pct: Decimal | None) -> Decimal | None:
    """Price with GST, to the rupee as on the offer letter."""
    if price is None:
        return None
    return (price * (1 + (gst_pct or Decimal(0)) / 100)).quantize(Decimal("1"))


def _coverage() -> Any:
    """The one machine an ASC covers."""
    return (
        select(
            ContractCoverage.service_contract_id, func.min(ContractCoverage.machine_unit_id).label("machine_unit_id")
        )
        .where(ContractCoverage.is_active)
        .group_by(ContractCoverage.service_contract_id)
        .subquery("coverage")
    )


def _list_select(today: dt.date) -> Select[*tuple[Any, ...]]:
    """Columns of ServiceContractListItem."""
    coverage = _coverage()
    return (
        select(
            ServiceContract.id,
            ServiceContract.contract_no,
            state_expression(today).label("state"),
            ServiceContract.branch_id,
            Branch.name.label("branch_name"),
            ServiceContract.customer_id,
            Customer.code.label("customer_code"),
            Customer.name.label("customer_name"),
            coverage.c.machine_unit_id,
            MachineUnit.serial_number.label("machine_serial_no"),
            MachineModel.model_name.label("machine_model"),
            ServiceContract.contract_plan_id,
            ContractPlan.name.label("plan_name"),
            ServiceContract.start_date,
            ServiceContract.end_date,
            ServiceContract.visits_included,
            ServiceContract.visits_used,
            visits_remaining(),
            ServiceContract.contract_value,
            ServiceContract.is_renewal,
            ServiceContract.engineer_name,
            ServiceContract.book_no,
        )
        .join(Customer, Customer.id == ServiceContract.customer_id)
        .outerjoin(Branch, Branch.id == ServiceContract.branch_id)
        .outerjoin(coverage, coverage.c.service_contract_id == ServiceContract.id)
        .outerjoin(MachineUnit, MachineUnit.id == coverage.c.machine_unit_id)
        .outerjoin(MachineModel, MachineModel.id == MachineUnit.model_id)
        .outerjoin(ContractPlan, ContractPlan.id == ServiceContract.contract_plan_id)
        .where(ServiceContract.contract_type == ASC, ServiceContract.is_active)
    )


def _plan_select() -> Select[*tuple[Any, ...]]:
    return select(ContractPlan).where(ContractPlan.contract_type == ASC)


class ContractRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    # ------------------------------------------------------------------ contracts

    def search(
        self, actor: CurrentUser, scope: RequestScope, query: ServiceContractQuery, today: dt.date
    ) -> Page[ServiceContractListItem]:
        statement = _list_select(today)
        # Row-level security limits the brands; the branches the user may work in are applied here.
        if actor.branch_ids is not None:
            statement = statement.where(ServiceContract.branch_id.in_(actor.branch_ids or [0]))
        if scope.principal_id is not None:
            statement = statement.where(ServiceContract.principal_id == scope.principal_id)
        if query.branch_id is not None:
            statement = statement.where(ServiceContract.branch_id == query.branch_id)
        if query.machine_unit_id is not None:
            statement = statement.where(MachineUnit.id == query.machine_unit_id)
        statement = statement.where(_status_filter(query.status, today))
        if query.search:
            term = query.search.strip()
            statement = statement.where(
                or_(
                    ServiceContract.contract_no.contains(term, autoescape=True),
                    ServiceContract.book_no.contains(term, autoescape=True),
                    MachineUnit.serial_number.contains(term, autoescape=True),
                    Customer.name.contains(term, autoescape=True),
                    Customer.code.contains(term, autoescape=True),
                )
            )
        default = "-endDate" if query.status in ("expired", "cancelled") else "endDate"
        statement = order_by_sort(
            statement, query.sort, _SORT_COLUMNS, default=default, tiebreaker=ServiceContract.id.asc()
        )
        return paginate(self._session, statement, query, ServiceContractListItem)

    def detail(self, contract_id: int, today: dt.date) -> ServiceContractDetail | None:
        renewed_from = aliased(ServiceContract)
        renewal = (
            select(func.min(ServiceContract.id))
            .where(ServiceContract.renewed_from_contract_id == contract_id, ServiceContract.status != "Cancelled")
            .scalar_subquery()
        )
        statement = (
            _list_select(today)
            .add_columns(
                ServiceContract.principal_id,
                Principal.code.label("principal_code"),
                ServiceContract.oem_contract_id,
                ServiceContract.receipt_no,
                ServiceContract.invoice_ref,
                ServiceContract.terms,
                ServiceContract.engineer_employee_id,
                ServiceContract.renewed_from_contract_id,
                renewed_from.contract_no.label("renewed_from_contract_no"),
                renewal.label("renewed_by_contract_id"),
                ServiceContract.created_at,
                ServiceContract.row_version,
            )
            .join(Principal, Principal.id == ServiceContract.principal_id)
            .outerjoin(renewed_from, renewed_from.id == ServiceContract.renewed_from_contract_id)
            .where(ServiceContract.id == contract_id)
        )
        row = self._session.execute(statement).mappings().one_or_none()
        return ServiceContractDetail.model_validate(row) if row is not None else None

    def get(self, contract_id: int) -> ServiceContract | None:
        contract = self._session.get(ServiceContract, contract_id)
        return contract if contract is not None and contract.is_active and contract.contract_type == ASC else None

    def covered_machine(self, contract_id: int) -> int | None:
        return self._session.scalar(
            select(ContractCoverage.machine_unit_id)
            .where(ContractCoverage.service_contract_id == contract_id, ContractCoverage.is_active)
            .limit(1)
        )

    def overlapping(self, machine_id: int, start: dt.date, end: dt.date, exclude_id: int | None) -> str | None:
        """The number of another live ASC on this machine whose dates overlap, or None."""
        statement = (
            select(ServiceContract.contract_no)
            .join(ContractCoverage, ContractCoverage.service_contract_id == ServiceContract.id)
            .where(
                ContractCoverage.machine_unit_id == machine_id,
                ContractCoverage.is_active,
                ServiceContract.contract_type == ASC,
                ServiceContract.is_active,
                ServiceContract.status != "Cancelled",
                ServiceContract.start_date <= end,
                ServiceContract.end_date >= start,
            )
        )
        if exclude_id is not None:
            statement = statement.where(ServiceContract.id != exclude_id)
        return self._session.scalar(statement.limit(1))

    def machine_asc(self, machine_ids: Collection[int], today: dt.date) -> dict[int, MachineAsc]:
        """For each machine with an ASC: the one running today, else the next to start, else the last ended."""
        if not machine_ids:
            return {}
        rank = case(
            (ServiceContract.start_date > today, 1),
            (ServiceContract.end_date < today, 2),
            else_=0,
        )
        rows = self._session.execute(
            select(
                ContractCoverage.machine_unit_id,
                ServiceContract.id.label("contract_id"),
                ServiceContract.contract_no,
                state_expression(today).label("state"),
                ContractPlan.name.label("plan_name"),
                ServiceContract.start_date,
                ServiceContract.end_date,
                ServiceContract.visits_included,
                ServiceContract.visits_used,
                visits_remaining(),
            )
            .join(ContractCoverage, ContractCoverage.service_contract_id == ServiceContract.id)
            .outerjoin(ContractPlan, ContractPlan.id == ServiceContract.contract_plan_id)
            .where(
                ContractCoverage.machine_unit_id.in_(machine_ids),
                ContractCoverage.is_active,
                ServiceContract.contract_type == ASC,
                ServiceContract.is_active,
                ServiceContract.status != "Cancelled",
            )
            # Running first; among upcoming the soonest start; among ended the latest end.
            .order_by(rank, ServiceContract.start_date, ServiceContract.end_date.desc())
        ).mappings()
        found: dict[int, MachineAsc] = {}
        for row in rows:
            found.setdefault(row["machine_unit_id"], MachineAsc.model_validate(row))
        return found

    def active_contract_id(self, machine_id: int, on: dt.date) -> int | None:
        """The ASC covering the machine on that day, for a new service call."""
        return self._session.scalar(
            select(ServiceContract.id)
            .join(ContractCoverage, ContractCoverage.service_contract_id == ServiceContract.id)
            .where(
                ContractCoverage.machine_unit_id == machine_id,
                ContractCoverage.is_active,
                ServiceContract.contract_type == ASC,
                ServiceContract.is_active,
                ServiceContract.status != "Cancelled",
                ServiceContract.start_date <= on,
                ServiceContract.end_date >= on,
            )
            .order_by(ServiceContract.end_date.desc())
            .limit(1)
        )

    # ------------------------------------------------------------------ visits counted from service calls

    def lock(self, contract_id: int) -> ServiceContract:
        """The contract, held until commit so two people counting visits can't pass its limit together."""
        return self._session.scalars(
            select(ServiceContract)
            .where(ServiceContract.id == contract_id)
            # As in common/numbering.py: the SQL Server dialect ignores .with_for_update().
            .with_hint(ServiceContract, "WITH (UPDLOCK, ROWLOCK)", "mssql")
            .execution_options(populate_existing=True)
        ).one()

    def _under_contract(self, contract: ServiceContract) -> ColumnElement[bool]:
        """Calls linked to the ASC, and calls on its machine in its period logged before the ASC reached
        Trishul (a register upload doesn't go back and link them)."""
        linked = ServiceCall.service_contract_id == contract.id
        machine_id = self.covered_machine(contract.id)
        if machine_id is None:
            return linked
        return or_(
            linked,
            and_(
                ServiceCall.service_contract_id.is_(None),
                ServiceCall.machine_unit_id == machine_id,
                ServiceCall.received_at >= dt.datetime.combine(contract.start_date, dt.time.min),
                ServiceCall.received_at < dt.datetime.combine(contract.end_date + dt.timedelta(days=1), dt.time.min),
            ),
        )

    def call_visits(self, contract: ServiceContract) -> builtins.list[AscCallVisit]:
        """The finished calls of an ASC, plus any counted call that has since moved on; newest first."""
        finished_at = func.coalesce(ServiceCall.completed_at, ServiceCall.closed_at)
        rows = self._session.execute(
            select(
                ServiceCall.id.label("service_call_id"),
                ServiceCall.call_no,
                ServiceCall.current_status,
                ServiceCall.complaint_description,
                func.concat_ws(" ", Employee.first_name, Employee.last_name).label("engineer_name"),
                ServiceCall.received_at,
                finished_at.label("finished_at"),
                func.coalesce(ContractVisit.visits, 0).label("visits"),
                ContractVisit.remarks,
            )
            .outerjoin(Employee, Employee.id == ServiceCall.assigned_engineer_id)
            .outerjoin(ContractVisit, ContractVisit.service_call_id == ServiceCall.id)
            .where(
                ServiceCall.is_active,
                or_(
                    ContractVisit.service_contract_id == contract.id,
                    and_(
                        ContractVisit.id.is_(None),
                        ServiceCall.current_status.in_(COUNTABLE_STATUSES),
                        self._under_contract(contract),
                    ),
                ),
            )
            .order_by(finished_at.desc(), ServiceCall.id.desc())
        ).mappings()
        return [
            AscCallVisit.model_validate({**row, "countable": row["current_status"] in COUNTABLE_STATUSES})
            for row in rows
        ]

    def call_under_contract(self, contract: ServiceContract, call_id: int) -> ServiceCall | None:
        return self._session.scalars(
            select(ServiceCall).where(
                ServiceCall.id == call_id, ServiceCall.is_active, self._under_contract(contract)
            )
        ).one_or_none()

    def visit_record(self, call_id: int) -> ContractVisit | None:
        return self._session.scalar(select(ContractVisit).where(ContractVisit.service_call_id == call_id))

    def visits_counted(self, contract_id: int) -> int:
        """Of a contract's visits_used, how many came from service calls."""
        return (
            self._session.scalar(
                select(func.sum(ContractVisit.visits)).where(ContractVisit.service_contract_id == contract_id)
            )
            or 0
        )

    def contract_no(self, contract_id: int) -> str | None:
        return self._session.scalar(select(ServiceContract.contract_no).where(ServiceContract.id == contract_id))

    # ------------------------------------------------------------------ plans

    def plans(self, scope: RequestScope, query: ContractPlanQuery) -> builtins.list[ContractPlanItem]:
        statement = _plan_select()
        if scope.principal_id is not None:
            statement = statement.where(
                or_(ContractPlan.principal_id == scope.principal_id, ContractPlan.principal_id.is_(None))
            )
        if query.status != "all":
            statement = statement.where(ContractPlan.is_active == (query.status == "active"))
        statement = statement.order_by(ContractPlan.duration_months.desc(), ContractPlan.price, ContractPlan.code)
        return [plan_item(plan) for plan in self._session.scalars(statement)]

    def get_plan(self, plan_id: int) -> ContractPlan | None:
        plan = self._session.get(ContractPlan, plan_id)
        return plan if plan is not None and plan.contract_type == ASC else None

    def plan_code_owner(self, code: str) -> int | None:
        return self._session.scalar(select(ContractPlan.id).where(ContractPlan.code == code).limit(1))

    # ------------------------------------------------------------------ lookups

    def machine(self, machine_id: int) -> MachineUnit | None:
        machine = self._session.get(MachineUnit, machine_id)
        return machine if machine is not None and machine.is_active else None

    def engineers(self, branch_id: int | None) -> builtins.list[ContractEngineerOption]:
        name = func.concat_ws(" ", Employee.first_name, Employee.last_name)
        statement = (
            select(Employee.id, name.label("name"), Employee.employee_code)
            .join(Designation, Designation.id == Employee.designation_id)
            .where(Employee.is_active, Designation.code == _SERVICE_ENGINEER_DESIGNATION)
        )
        if branch_id is not None:
            statement = statement.where(Employee.branch_id == branch_id)
        rows = self._session.execute(statement.order_by(name)).mappings()
        return [ContractEngineerOption.model_validate(row) for row in rows]

    def employee_name(self, employee_id: int) -> str | None:
        employee = self._session.get(Employee, employee_id)
        if employee is None or not employee.is_active:
            return None
        return " ".join(part for part in (employee.first_name, employee.last_name) if part)

    def active_branch(self, branch_id: int) -> Branch | None:
        branch = self._session.get(Branch, branch_id)
        return branch if branch is not None and branch.is_active else None


def plan_item(plan: ContractPlan) -> ContractPlanItem:
    fields = {name: getattr(plan, name) for name in ContractPlanItem.model_fields if name != "total_price"}
    return ContractPlanItem.model_validate({**fields, "total_price": plan_total(plan.price, plan.gst_pct)})


def _status_filter(status: str, today: dt.date) -> ColumnElement[bool]:
    not_cancelled = ServiceContract.status != "Cancelled"
    if status == "live":
        return and_(not_cancelled, ServiceContract.end_date >= today)
    if status == "expiring":
        return and_(
            not_cancelled,
            ServiceContract.start_date <= today,
            ServiceContract.end_date >= today,
            ServiceContract.end_date <= today + dt.timedelta(days=EXPIRING_DAYS),
        )
    if status == "expired":
        return and_(not_cancelled, ServiceContract.end_date < today)
    if status == "cancelled":
        return ServiceContract.status == "Cancelled"
    return true()
