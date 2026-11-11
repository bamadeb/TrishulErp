"""Figures for the home dashboard.

Which sections a user gets follows what their role lets them do, not the role's name, so a role edited on
the Roles screen gets the matching dashboard. Seeing calls alone is not enough: engineers and the ASC
Manager can view every call, but they don't run the call desk.

  * My work        works calls in the field: svc.call.status.update, with a linked employee (engineer)
  * Calls overview runs the call desk: assigns, logs, closes or imports calls, or reads the import log
                   (team lead, back office, management), with a call view permission. Its counts cover the
                   calls the register shows them: all, or their team's plus unassigned.
  * ASC overview   svc.contract.view / manage / visit

Every count uses the same limits as the screens the figures link to: the call register's visibility
(service.access.call_visibility) and the selected branch and brand. Visit figures count calls (a call
planned for three engineers is one), so they match the Service calls list's Visit date filter.
"""

import datetime as dt
from collections import Counter
from typing import Any

from sqlalchemy import ColumnElement, and_, func, or_, select
from sqlalchemy.orm import Session, aliased

from trishul_api.auth import CurrentUser, RequestScope
from trishul_api.db.models import (
    CallAssignment,
    ContractVisit,
    Customer,
    Employee,
    MachineModel,
    MachineUnit,
    ServiceCall,
    ServiceContract,
    ServiceVisit,
)
from trishul_api.modules.rpt.schemas import (
    AscOverview,
    CallsOverview,
    Dashboard,
    DashboardVisit,
    EngineerLoad,
    ExpiringContract,
    MyWork,
    StatusCount,
)
from trishul_api.modules.service.access import (
    ALL_STATUSES,
    CAN_VIEW_ALL_CALLS,
    CAN_VIEW_CALLS,
    CAN_VIEW_TEAM_CALLS,
    FINISHED_STATUSES,
    CallVisibility,
    call_visibility,
)
from trishul_api.modules.service.assignment import supports_call
from trishul_api.modules.service.contracts.repository import (
    ASC,
    COUNTABLE_STATUSES,
    EXPIRING_DAYS,
    _list_select,
)
from trishul_api.modules.service.repository import ServiceCallRepository, visible_calls

CAN_WORK_CALLS = "svc.call.status.update"
CAN_RUN_CALL_DESK = ("svc.call.assign", "svc.call.create", "svc.call.close", "svc.call.import", "svc.call.import.view")
CAN_VIEW_ASC = ("svc.contract.view", "svc.contract.manage", "svc.contract.visit")
Condition = Any  # a WHERE condition: a SQL expression or a boolean column
_LIST_SIZE = 10
_ENGINEER_NAME = func.concat_ws(" ", Employee.first_name, Employee.last_name)


def build_dashboard(db: Session, actor: CurrentUser, scope: RequestScope, now: dt.datetime) -> Dashboard:
    """now: the current UTC time; days (today, tomorrow) follow the server's date as the rest of the app does."""
    today = dt.date.today()
    figures = _Figures(db, scope, today, now)
    dashboard = Dashboard()
    if actor.employee_id is not None and actor.can(CAN_WORK_CALLS) and actor.can(*CAN_VIEW_CALLS):
        dashboard.my_work = figures.my_work(actor.employee_id)
    if actor.can(*CAN_RUN_CALL_DESK) and actor.can(CAN_VIEW_ALL_CALLS, CAN_VIEW_TEAM_CALLS):
        visibility = call_visibility(actor, ServiceCallRepository(db).team_members)
        dashboard.calls = figures.calls(visibility)
    if actor.can(*CAN_VIEW_ASC):
        dashboard.asc = figures.asc(actor)
    return dashboard


def _open() -> ColumnElement[bool]:
    return and_(ServiceCall.is_active, ServiceCall.current_status.notin_(FINISHED_STATUSES))


def _planned() -> ColumnElement[bool]:
    """A visit planned for a day and not yet started (starting a trip moves it on from 'Planned')."""
    return and_(ServiceVisit.status == "Planned", ServiceVisit.is_active, ServiceVisit.planned_date.is_not(None))


class _Figures:
    def __init__(self, db: Session, scope: RequestScope, today: dt.date, now: dt.datetime) -> None:
        self._db = db
        self._scope = scope
        self._today = today
        self._now = now

    # ------------------------------------------------------------------ shared pieces

    def _in_scope(self) -> list[Condition]:
        """The selected branch and brand (row-level security limits the rest)."""
        conditions: list[Condition] = []
        if self._scope.branch_id is not None:
            conditions.append(ServiceCall.branch_id == self._scope.branch_id)
        if self._scope.principal_id is not None:
            conditions.append(ServiceCall.principal_id == self._scope.principal_id)
        return conditions

    def _count_calls(self, *where: Condition) -> int:
        return self._db.scalar(select(func.count(ServiceCall.id)).where(*self._in_scope(), *where)) or 0

    def _count_visits(self, *where: Condition) -> int:
        """Calls with a matching planned visit (one call however many engineers it is planned for)."""
        statement = (
            select(func.count(func.distinct(ServiceCall.id)))
            .select_from(ServiceVisit)
            .join(ServiceCall, ServiceCall.id == ServiceVisit.service_call_id)
            .where(_planned(), _open(), *self._in_scope(), *where)
        )
        return self._db.scalar(statement) or 0

    def _visits(self, *where: Condition) -> list[DashboardVisit]:
        statement = (
            select(
                ServiceCall.id.label("service_call_id"),
                ServiceCall.call_no,
                Customer.name.label("customer_name"),
                MachineModel.model_name.label("machine_model"),
                MachineUnit.serial_number.label("machine_serial_no"),
                ServiceCall.complaint_description,
                ServiceCall.priority,
                ServiceCall.is_machine_down,
                ServiceCall.current_status,
                ServiceVisit.planned_date,
                func.nullif(_ENGINEER_NAME, "").label("engineer_name"),
            )
            .select_from(ServiceVisit)
            .join(ServiceCall, ServiceCall.id == ServiceVisit.service_call_id)
            .join(Customer, Customer.id == ServiceCall.customer_id)
            .outerjoin(MachineUnit, MachineUnit.id == ServiceCall.machine_unit_id)
            .outerjoin(MachineModel, MachineModel.id == MachineUnit.model_id)
            .outerjoin(Employee, Employee.id == ServiceVisit.engineer_employee_id)
            .where(_planned(), _open(), *self._in_scope(), *where)
            .order_by(ServiceVisit.planned_date, ServiceCall.id, Employee.first_name)
            .limit(_LIST_SIZE * 5)  # several engineers per call collapse into one row below
        )
        # One row per call: its earliest planned day, with everyone planned for it.
        by_call: dict[int, DashboardVisit] = {}
        for row in self._db.execute(statement).mappings():
            visit = by_call.get(row["service_call_id"])
            if visit is None:
                if len(by_call) == _LIST_SIZE:
                    continue
                by_call[row["service_call_id"]] = DashboardVisit.model_validate(row)
            elif row["engineer_name"] and row["engineer_name"] not in (visit.engineer_name or ""):
                visit.engineer_name = (
                    f"{visit.engineer_name}, {row['engineer_name']}" if visit.engineer_name else row["engineer_name"]
                )
        return list(by_call.values())

    # ------------------------------------------------------------------ sections

    def my_work(self, engineer_id: int) -> MyWork:
        on_call = or_(ServiceCall.assigned_engineer_id == engineer_id, supports_call([engineer_id]))
        mine = ServiceVisit.engineer_employee_id == engineer_id
        tomorrow = self._today + dt.timedelta(days=1)
        week = self._today + dt.timedelta(days=7)
        return MyWork(
            open_calls=self._count_calls(_open(), on_call),
            machine_down=self._count_calls(_open(), on_call, ServiceCall.is_machine_down),
            visits_today=self._count_visits(mine, ServiceVisit.planned_date == self._today),
            visits_tomorrow=self._count_visits(mine, ServiceVisit.planned_date == tomorrow),
            overdue_visits=self._count_visits(mine, ServiceVisit.planned_date < self._today),
            upcoming=self._visits(mine, ServiceVisit.planned_date <= week),
        )

    def calls(self, visibility: CallVisibility) -> CallsOverview:
        seen = visible_calls(visibility)
        tomorrow = self._today + dt.timedelta(days=1)
        month_start = dt.datetime(self._today.year, self._today.month, 1)
        finished_at = func.coalesce(ServiceCall.completed_at, ServiceCall.closed_at)
        by_status: Counter[str] = Counter(
            {
                str(status): count
                for status, count in self._db.execute(
                    select(ServiceCall.current_status, func.count(ServiceCall.id))
                    .where(_open(), seen, *self._in_scope())
                    .group_by(ServiceCall.current_status)
                )
            }
        )
        return CallsOverview(
            scope="all" if visibility.everything else "team",
            open_calls=sum(by_status.values()),
            unassigned=self._count_calls(_open(), seen, ServiceCall.assigned_engineer_id.is_(None)),
            machine_down=self._count_calls(_open(), seen, ServiceCall.is_machine_down),
            sla_breached=self._count_calls(_open(), seen, ServiceCall.sla_due_at < self._now),
            sla_due_soon=self._count_calls(
                _open(),
                seen,
                ServiceCall.sla_due_at >= self._now,
                ServiceCall.sla_due_at < self._now + dt.timedelta(hours=24),
            ),
            visits_today=self._count_visits(seen, ServiceVisit.planned_date == self._today),
            visits_tomorrow=self._count_visits(seen, ServiceVisit.planned_date == tomorrow),
            overdue_visits=self._count_visits(seen, ServiceVisit.planned_date < self._today),
            completed_this_month=self._count_calls(
                ServiceCall.is_active,
                seen,
                ServiceCall.current_status.in_(("Completed", "Closed")),
                finished_at >= month_start,
            ),
            by_status=[
                StatusCount.model_validate({"status": s, "count": by_status[s]}) for s in ALL_STATUSES if by_status[s]
            ],
            engineers=self._engineer_load(visibility, seen),
            overdue=self._visits(seen, ServiceVisit.planned_date < self._today),
        )

    def _engineer_load(self, visibility: CallVisibility, seen: ColumnElement[bool]) -> list[EngineerLoad]:
        """Open calls per engineer (lead or support) and their visits planned for today."""
        open_calls: Counter[int] = Counter()
        lead = (
            select(ServiceCall.assigned_engineer_id, func.count(ServiceCall.id))
            .where(_open(), seen, ServiceCall.assigned_engineer_id.is_not(None), *self._in_scope())
            .group_by(ServiceCall.assigned_engineer_id)
        )
        # An alias: a team lead's visibility tests call_assignment itself, and must not correlate to this row.
        row = aliased(CallAssignment)
        support = (
            select(row.engineer_employee_id, func.count(ServiceCall.id))
            .select_from(row)
            .join(ServiceCall, ServiceCall.id == row.service_call_id)
            .where(
                row.assignment_type == "Support",
                row.is_current,
                row.is_active,
                _open(),
                seen,
                *self._in_scope(),
            )
            .group_by(row.engineer_employee_id)
        )
        for statement in (lead, support):
            for engineer, count in self._db.execute(statement):
                if engineer is not None:
                    open_calls[engineer] += count
        today = Counter(
            {
                engineer: count
                for engineer, count in self._db.execute(
                    select(ServiceVisit.engineer_employee_id, func.count(ServiceVisit.id))
                    .join(ServiceCall, ServiceCall.id == ServiceVisit.service_call_id)
                    .where(_planned(), _open(), seen, ServiceVisit.planned_date == self._today, *self._in_scope())
                    .group_by(ServiceVisit.engineer_employee_id)
                )
            }
        )
        engineers = set(open_calls) | set(today)
        if not visibility.everything:
            engineers &= visibility.engineer_ids  # a team lead sees their own team, not outside helpers
        if not engineers:
            return []
        names: dict[int, str] = {
            employee_id: name
            for employee_id, name in self._db.execute(
                select(Employee.id, _ENGINEER_NAME).where(Employee.id.in_(sorted(engineers)))
            )
        }
        loads = [
            EngineerLoad(
                engineer_id=engineer,
                name=names.get(engineer) or f"Employee {engineer}",
                open_calls=open_calls[engineer],
                visits_today=today[engineer],
            )
            for engineer in engineers
        ]
        loads.sort(key=lambda load: (-load.open_calls, -load.visits_today, load.name))
        return loads[:_LIST_SIZE]

    def asc(self, actor: CurrentUser) -> AscOverview:
        today = self._today
        soon = today + dt.timedelta(days=EXPIRING_DAYS)
        allowed: list[Condition] = [
            ServiceContract.contract_type == ASC,
            ServiceContract.is_active,
            ServiceContract.status != "Cancelled",
        ]
        if actor.branch_ids is not None:
            allowed.append(ServiceContract.branch_id.in_(sorted(actor.branch_ids) or [0]))
        if self._scope.branch_id is not None:
            allowed.append(ServiceContract.branch_id == self._scope.branch_id)
        if self._scope.principal_id is not None:
            allowed.append(ServiceContract.principal_id == self._scope.principal_id)
        active = and_(*allowed, ServiceContract.start_date <= today, ServiceContract.end_date >= today)
        live = and_(*allowed, ServiceContract.end_date >= today)

        active_count = self._db.scalar(select(func.count(ServiceContract.id)).where(active)) or 0
        # Visit totals only over contracts with a limit; remaining never goes below 0 per contract.
        limited: list[tuple[int, int]] = [
            (included or 0, used)
            for included, used in self._db.execute(
                select(ServiceContract.visits_included, ServiceContract.visits_used).where(
                    active, ServiceContract.visits_included.is_not(None)
                )
            )
        ]
        calls_to_count = (
            self._db.scalar(
                select(func.count(ServiceCall.id))
                .join(ServiceContract, ServiceContract.id == ServiceCall.service_contract_id)
                .outerjoin(ContractVisit, ContractVisit.service_call_id == ServiceCall.id)
                .where(
                    live,
                    ServiceCall.is_active,
                    ServiceCall.current_status.in_(COUNTABLE_STATUSES),
                    ContractVisit.id.is_(None),
                )
            )
            or 0
        )
        expiring_rows = self._db.execute(
            _list_select(today)
            .where(active, ServiceContract.end_date <= soon)
            .order_by(ServiceContract.end_date, ServiceContract.id)
            .limit(5)
        ).mappings()
        expiring_soon = self._db.scalar(
            select(func.count(ServiceContract.id)).where(active, ServiceContract.end_date <= soon)
        )
        return AscOverview(
            active=active_count,
            expiring_soon=expiring_soon or 0,
            visits_included=sum(included for included, _ in limited),
            visits_used=sum(used for _, used in limited),
            visits_remaining=sum(max(included - used, 0) for included, used in limited),
            calls_to_count=calls_to_count,
            expiring=[ExpiringContract.model_validate(row) for row in expiring_rows],
        )
