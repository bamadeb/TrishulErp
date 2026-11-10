import builtins
from datetime import date
from typing import Any

from sqlalchemy import ColumnElement, Select, case, exists, false, func, or_, select, true
from sqlalchemy.orm import InstrumentedAttribute, Session, aliased

from trishul_api.auth import RequestScope
from trishul_api.common.paging import SortColumns, order_by_sort, paginate
from trishul_api.common.schemas import Page
from trishul_api.db.models import (
    AppUser,
    Branch,
    CallStatusLog,
    Customer,
    CustomerSite,
    Designation,
    Employee,
    LookupValue,
    MachineModel,
    MachineUnit,
    Principal,
    ServiceCall,
    ServiceVisit,
    TrackableActivity,
    Team,
    TeamMember,
    TrkTrip,
)
from trishul_api.modules.core.teams.repository import current_member
from trishul_api.modules.service.access import FINISHED_STATUSES, CallVisibility
from trishul_api.modules.service.assignment import support_engineers, supports_call
from trishul_api.modules.service.contracts.repository import ContractRepository
from trishul_api.modules.trk.constants import IN_PROGRESS as TRIP_IN_PROGRESS
from trishul_api.modules.service.schemas import (
    AssignedServiceCallListItem,
    AssignedServiceCallQuery,
    CallCover,
    CallStatusLogItem,
    EngineerOption,
    EngineerOptionQuery,
    MachineOptionQuery,
    MachineUnitOption,
    ServiceCallDetail,
    ServiceCallListItem,
    ServiceCallQuery,
    UnassignedCallItem,
    UnassignedCallQuery,
)

# Calls the engineer no longer needs to travel to: hidden unless the client asks for them by status.
_CLOSED_STATUSES = ("Closed", "Cancelled")

# A call is assigned to a Service Engineer, so the assign picker lists only employees with that
# designation (hr.designation code), not every employee of the branch.
_SERVICE_ENGINEER_DESIGNATION = "SERVICE_ENG"
_ENGINEER_NAME = func.concat_ws(" ", Employee.first_name, Employee.last_name)


def _visible(visibility: CallVisibility) -> ColumnElement[bool]:
    """SQL form of CallVisibility.allows, for a user who does not see every call."""
    conditions: list[ColumnElement[bool]] = []
    if visibility.engineer_ids:
        conditions.append(ServiceCall.assigned_engineer_id.in_(sorted(visibility.engineer_ids)))
    if visibility.unassigned:
        conditions.append(ServiceCall.assigned_engineer_id.is_(None))
    if visibility.engineer_ids:
        conditions.append(supports_call(visibility.engineer_ids))
    return or_(*conditions) if conditions else false()


def visible_calls(visibility: CallVisibility) -> ColumnElement[bool]:
    """Which calls the user sees, as a WHERE condition (the register's rule, for other screens)."""
    return true() if visibility.everything else _visible(visibility)


def _trip_ongoing() -> ColumnElement[bool]:
    """True while any trip of the call (across its visits) has been started and not yet stopped.
    Trips hang off trk.trackable_activity, which for SVC points at a service_visit."""
    ongoing = (
        exists()
        .where(
            ServiceVisit.service_call_id == ServiceCall.id,
            TrackableActivity.module_code == "SVC",
            TrackableActivity.source_table == "service_visit",
            TrackableActivity.source_id == ServiceVisit.id,
            TrkTrip.trackable_activity_id == TrackableActivity.id,
            TrkTrip.status == TRIP_IN_PROGRESS,
            TrkTrip.end_at.is_(None),
            TrkTrip.is_active,
        )
        .correlate(ServiceCall)
    )
    # SQL Server has no boolean expressions in a select list, hence the CASE around the EXISTS.
    return case((ongoing, True), else_=False)


def _planned_visit_date(engineer_id: int | None = None) -> ColumnElement[date | None]:
    """Earliest day a visit of the call is planned for and not yet started (a started visit leaves
    'Planned'). With an engineer, only that engineer's own visit."""
    statement = select(func.min(ServiceVisit.planned_date)).where(
        ServiceVisit.service_call_id == ServiceCall.id,
        ServiceVisit.status == "Planned",
        ServiceVisit.is_active,
    )
    if engineer_id is not None:
        statement = statement.where(ServiceVisit.engineer_employee_id == engineer_id)
    return statement.correlate(ServiceCall).scalar_subquery()


def _visit_planned_on(day: date, engineer_id: int | None = None) -> ColumnElement[bool]:
    """The call has a visit planned (not yet started) on that day; with an engineer, their own visit."""
    condition = exists().where(
        ServiceVisit.service_call_id == ServiceCall.id,
        ServiceVisit.status == "Planned",
        ServiceVisit.is_active,
        ServiceVisit.planned_date == day,
    )
    if engineer_id is not None:
        condition = condition.where(ServiceVisit.engineer_employee_id == engineer_id)
    return condition


# Ascending puts calls with no planned day after every dated one (SQL Server sorts NULL first).
_NO_DAY = date(9999, 12, 31)

_PRIORITY_RANK = case(
    {"Critical": 1, "High": 2, "Normal": 3, "Low": 4},
    value=ServiceCall.priority,
    else_=5,
)

_SORT_COLUMNS: SortColumns = {
    "callNo": ServiceCall.call_no,
    "receivedAt": ServiceCall.received_at,
    "customerName": Customer.name,
    "priority": _PRIORITY_RANK,
    "slaDueAt": ServiceCall.sla_due_at,
    "plannedVisitDate": func.coalesce(_planned_visit_date(), _NO_DAY),
}

# The engineer's own list. "visitDate" (their own visit) depends on the engineer, so it is added there.
_ASSIGNED_SORT_COLUMNS: SortColumns = {
    "callNo": ServiceCall.call_no,
    "receivedAt": ServiceCall.received_at,
    "priority": _PRIORITY_RANK,
    "slaDueAt": ServiceCall.sla_due_at,
}


def _cover(item: UnassignedCallItem, under_asc_today: bool) -> CallCover:
    """Who pays. The ASC and warranty come from the machine too: older calls never had them worked out."""
    under_asc = under_asc_today or item.is_asc_priority or item.coverage_type == "Contract"
    warranty_end = item.machine_warranty_end_date
    under_warranty = item.coverage_type == "Warranty" or (
        warranty_end is not None and warranty_end >= item.received_at.date()
    )
    if under_asc and under_warranty:
        return "ASC + Warranty"
    if under_asc:
        return "ASC"
    if under_warranty:
        return "Warranty"
    if item.coverage_type == "Chargeable" or item.coverage_type == "Goodwill":
        return item.coverage_type
    return "Unknown" if item.machine_unit_id is None else "Not covered"


class ServiceCallRepository:
    """Read queries return response models directly (projections of just the columns a screen shows).
    Writes will go through a service and work with ORM objects."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def list(
        self, scope: RequestScope, query: ServiceCallQuery, visibility: CallVisibility
    ) -> Page[ServiceCallListItem]:
        page = paginate(self._session, self.list_statement(scope, query, visibility), query, ServiceCallListItem)
        support = support_engineers(self._session, [item.id for item in page.items])
        for item in page.items:
            item.support_engineers = support.get(item.id, [])
        return page

    def team_members(self, lead_employee_id: int) -> builtins.list[int]:
        """Employees currently in the active teams this employee leads."""
        return list(
            self._session.scalars(
                select(TeamMember.employee_id)
                .join(Team, Team.id == TeamMember.team_id)
                .where(Team.team_lead_employee_id == lead_employee_id, Team.is_active, current_member(date.today()))
                .distinct()
            )
        )

    def get_list_item(self, call_id: int) -> ServiceCallListItem:
        """One call as the register shows it; the call must exist."""
        row = self._session.execute(self._register_select().where(ServiceCall.id == call_id)).mappings().one()
        item = ServiceCallListItem.model_validate(row)
        item.support_engineers = support_engineers(self._session, [call_id]).get(call_id, [])
        return item

    def status_history(self, call_id: int) -> builtins.list[CallStatusLogItem]:
        """Every status change of a call, newest first, with who made it."""
        who = func.coalesce(
            func.nullif(func.concat_ws(" ", Employee.first_name, Employee.last_name), ""), AppUser.username
        )
        statement = (
            select(
                CallStatusLog.id,
                CallStatusLog.from_status,
                CallStatusLog.to_status,
                CallStatusLog.changed_at,
                who.label("changed_by_name"),
                CallStatusLog.remarks,
            )
            .outerjoin(AppUser, AppUser.id == CallStatusLog.changed_by_user_id)
            .outerjoin(Employee, Employee.id == AppUser.employee_id)
            .where(CallStatusLog.service_call_id == call_id)
            .order_by(CallStatusLog.changed_at.desc(), CallStatusLog.id.desc())
        )
        return [CallStatusLogItem.model_validate(row) for row in self._session.execute(statement).mappings()]

    def detail(self, call_id: int) -> ServiceCallDetail | None:
        """Everything the call detail page needs, or None if the call doesn't exist."""
        call_type = aliased(LookupValue)
        call_source = aliased(LookupValue)
        engineer = aliased(Employee)
        statement = (
            select(
                ServiceCall.id,
                ServiceCall.call_no,
                ServiceCall.received_at,
                Branch.name.label("branch_name"),
                Principal.code.label("principal_code"),
                Principal.name.label("principal_name"),
                ServiceCall.customer_id,
                Customer.name.label("customer_name"),
                Customer.primary_phone.label("customer_phone"),
                ServiceCall.machine_unit_id,
                MachineUnit.serial_number.label("machine_serial_no"),
                MachineModel.model_name.label("machine_model"),
                MachineModel.model_code.label("machine_model_code"),
                MachineModel.product_line.label("machine_product_line"),
                MachineUnit.engine_number.label("machine_engine_number"),
                MachineUnit.registration_number.label("machine_registration_number"),
                MachineUnit.warranty_end_date.label("machine_warranty_end_date"),
                MachineUnit.current_hmr.label("machine_hmr"),
                MachineUnit.is_active.label("machine_is_active"),
                ServiceCall.complaint_description,
                call_type.label.label("call_type"),
                call_source.label.label("call_source"),
                ServiceCall.priority,
                ServiceCall.is_machine_down,
                ServiceCall.is_asc_priority,
                ServiceCall.coverage_type,
                ServiceCall.current_status,
                ServiceCall.assigned_engineer_id,
                func.nullif(func.concat_ws(" ", engineer.first_name, engineer.last_name), "").label(
                    "assigned_engineer_name"
                ),
                ServiceCall.caller_name,
                ServiceCall.caller_phone,
                ServiceCall.oem_call_id,
                ServiceCall.source_reference,
                ServiceCall.sla_due_at,
                ServiceCall.first_response_at,
                ServiceCall.closed_at,
                CustomerSite.site_name,
                CustomerSite.address.label("site_address"),
                ServiceCall.needs_master_linking,
                ServiceCall.row_version,
            )
            .join(Customer, Customer.id == ServiceCall.customer_id)
            .join(Principal, Principal.id == ServiceCall.principal_id)
            .outerjoin(Branch, Branch.id == ServiceCall.branch_id)
            .outerjoin(MachineUnit, MachineUnit.id == ServiceCall.machine_unit_id)
            .outerjoin(MachineModel, MachineModel.id == MachineUnit.model_id)
            .outerjoin(engineer, engineer.id == ServiceCall.assigned_engineer_id)
            .outerjoin(call_type, call_type.id == ServiceCall.call_type_lookup_id)
            .outerjoin(call_source, call_source.id == ServiceCall.call_source_lookup_id)
            .outerjoin(CustomerSite, CustomerSite.id == ServiceCall.customer_site_id)
            .where(ServiceCall.id == call_id, ServiceCall.is_active)
        )
        row = self._session.execute(statement).mappings().one_or_none()
        if row is None:
            return None
        detail = ServiceCallDetail.model_validate(row)
        detail.support_engineers = support_engineers(self._session, [call_id]).get(call_id, [])
        return detail

    # builtins.list: this class has a method named `list`, which otherwise shadows the builtin here.
    def machine_options(self, scope: RequestScope, query: MachineOptionQuery) -> builtins.list[MachineUnitOption]:
        """Active machines to pick for a new call, narrowed to the selected brand and (optionally) the
        customer who owns them. Deactivated machines are never offered."""
        statement = (
            select(
                MachineUnit.id,
                MachineUnit.serial_number,
                MachineModel.model_name,
                Customer.name.label("customer_name"),
            )
            .outerjoin(MachineModel, MachineModel.id == MachineUnit.model_id)
            .outerjoin(Customer, Customer.id == MachineUnit.customer_id)
            .where(MachineUnit.is_active)
        )
        if scope.principal_id is not None:
            statement = statement.where(MachineUnit.principal_id == scope.principal_id)
        if query.customer_id is not None:
            statement = statement.where(MachineUnit.customer_id == query.customer_id)
        if query.search:
            term = query.search.strip()
            statement = statement.where(
                or_(
                    MachineUnit.serial_number.contains(term, autoescape=True),
                    MachineUnit.oem_registered_product_id.contains(term, autoescape=True),
                    MachineModel.model_name.contains(term, autoescape=True),
                )
            )
        statement = statement.order_by(MachineUnit.serial_number).limit(query.limit)
        options = [MachineUnitOption.model_validate(row) for row in self._session.execute(statement).mappings()]
        # So the call form can show whether the picked machine is under ASC.
        asc = ContractRepository(self._session).machine_asc([o.id for o in options], date.today())
        for option in options:
            option.asc = asc.get(option.id)
        return options

    @staticmethod
    def engineers_statement(scope: RequestScope, visibility: CallVisibility) -> Select[*tuple[Any, ...]]:
        """Engineers a team lead can assign a call to: active Service Engineers of the selected branch,
        and only their own team's when they see just their team's calls."""
        statement = (
            select(Employee.id, _ENGINEER_NAME.label("name"), Employee.employee_code)
            .join(Designation, Designation.id == Employee.designation_id)
            .where(Employee.is_active, Designation.code == _SERVICE_ENGINEER_DESIGNATION)
        )
        if not visibility.everything:
            statement = statement.where(Employee.id.in_(visibility.engineer_ids or [0]))
        if scope.branch_id is not None:
            statement = statement.where(Employee.branch_id == scope.branch_id)
        return statement

    @staticmethod
    def engineer_branch() -> InstrumentedAttribute[int]:
        return Employee.branch_id

    def engineer_options(
        self, scope: RequestScope, query: EngineerOptionQuery, visibility: CallVisibility
    ) -> builtins.list[EngineerOption]:
        name = _ENGINEER_NAME
        statement = self.engineers_statement(scope, visibility)
        if query.search:
            term = query.search.strip()
            statement = statement.where(
                or_(name.contains(term, autoescape=True), Employee.employee_code.contains(term, autoescape=True))
            )
        statement = statement.order_by(Employee.first_name, Employee.last_name).limit(query.limit)
        return [EngineerOption.model_validate(row) for row in self._session.execute(statement).mappings()]

    @staticmethod
    def _register_select() -> Select[*tuple[Any, ...]]:
        """Columns of ServiceCallListItem, with the joins the register row needs."""
        return (
            select(
                ServiceCall.id,
                ServiceCall.call_no,
                ServiceCall.received_at,
                Principal.code.label("principal_code"),
                ServiceCall.customer_id,
                Customer.name.label("customer_name"),
                ServiceCall.machine_unit_id,
                MachineUnit.serial_number.label("machine_serial_no"),
                MachineModel.model_name.label("machine_model"),
                ServiceCall.complaint_description,
                ServiceCall.priority,
                ServiceCall.is_machine_down,
                ServiceCall.is_asc_priority,
                ServiceCall.coverage_type,
                ServiceCall.current_status,
                ServiceCall.assigned_engineer_id,
                func.nullif(func.concat_ws(" ", Employee.first_name, Employee.last_name), "").label(
                    "assigned_engineer_name"
                ),
                ServiceCall.oem_call_id,
                ServiceCall.sla_due_at,
                ServiceCall.row_version,
                _trip_ongoing().label("is_trip_ongoing"),
                _planned_visit_date().label("planned_visit_date"),
            )
            .join(Customer, Customer.id == ServiceCall.customer_id)
            .join(Principal, Principal.id == ServiceCall.principal_id)
            .outerjoin(MachineUnit, MachineUnit.id == ServiceCall.machine_unit_id)
            .outerjoin(MachineModel, MachineModel.id == MachineUnit.model_id)
            .outerjoin(Employee, Employee.id == ServiceCall.assigned_engineer_id)
            .where(ServiceCall.is_active)
        )

    @staticmethod
    def list_statement(
        scope: RequestScope, query: ServiceCallQuery, visibility: CallVisibility
    ) -> Select[*tuple[Any, ...]]:
        statement = ServiceCallRepository._register_select()
        if not visibility.everything:
            statement = statement.where(_visible(visibility))
        # Row-level security limits what the user may see; these narrow it to what they selected.
        if scope.branch_id is not None:
            statement = statement.where(ServiceCall.branch_id == scope.branch_id)
        if scope.principal_id is not None:
            statement = statement.where(ServiceCall.principal_id == scope.principal_id)
        if query.status:
            statement = statement.where(ServiceCall.current_status.in_(query.status))
        if query.priority:
            statement = statement.where(ServiceCall.priority.in_(query.priority))
        if query.visit_date is not None:
            statement = statement.where(_visit_planned_on(query.visit_date))
        if query.search:
            term = query.search.strip()
            statement = statement.where(
                or_(
                    ServiceCall.call_no.contains(term, autoescape=True),
                    ServiceCall.oem_call_id.contains(term, autoescape=True),
                    Customer.name.contains(term, autoescape=True),
                    MachineUnit.serial_number.contains(term, autoescape=True),
                )
            )

        return order_by_sort(
            statement, query.sort, _SORT_COLUMNS, default="-receivedAt", tiebreaker=ServiceCall.id.desc()
        )

    def list_unassigned(
        self, scope: RequestScope, query: UnassignedCallQuery, visibility: CallVisibility
    ) -> Page[UnassignedCallItem]:
        page = paginate(self._session, self.unassigned_statement(scope, query, visibility), query, UnassignedCallItem)
        machines = [item.machine_unit_id for item in page.items if item.machine_unit_id is not None]
        asc = ContractRepository(self._session).machine_asc(machines, date.today())
        for item in page.items:
            contract = asc.get(item.machine_unit_id) if item.machine_unit_id is not None else None
            item.cover = _cover(item, contract is not None and contract.state == "Active")
        return page

    @staticmethod
    def unassigned_statement(
        scope: RequestScope, query: UnassignedCallQuery, visibility: CallVisibility
    ) -> Select[*tuple[Any, ...]]:
        # The call's own site, or else where its machine is kept.
        site = func.coalesce(ServiceCall.customer_site_id, MachineUnit.customer_site_id)
        statement = (
            select(
                ServiceCall.id,
                ServiceCall.call_no,
                ServiceCall.received_at,
                Principal.code.label("principal_code"),
                Branch.name.label("branch_name"),
                Customer.name.label("customer_name"),
                func.coalesce(CustomerSite.address, Customer.billing_address).label("location"),
                ServiceCall.machine_unit_id,
                MachineUnit.serial_number.label("machine_serial_no"),
                MachineModel.model_name.label("machine_model"),
                MachineUnit.warranty_end_date.label("machine_warranty_end_date"),
                ServiceCall.complaint_description,
                ServiceCall.priority,
                ServiceCall.is_machine_down,
                ServiceCall.is_asc_priority,
                ServiceCall.coverage_type,
                ServiceCall.sla_due_at,
                ServiceCall.row_version,
            )
            .join(Customer, Customer.id == ServiceCall.customer_id)
            .join(Principal, Principal.id == ServiceCall.principal_id)
            .outerjoin(Branch, Branch.id == ServiceCall.branch_id)
            .outerjoin(MachineUnit, MachineUnit.id == ServiceCall.machine_unit_id)
            .outerjoin(MachineModel, MachineModel.id == MachineUnit.model_id)
            .outerjoin(CustomerSite, CustomerSite.id == site)
            .where(
                ServiceCall.is_active,
                ServiceCall.assigned_engineer_id.is_(None),
                ServiceCall.current_status.notin_(sorted(FINISHED_STATUSES)),
            )
        )
        if not (visibility.everything or visibility.unassigned):
            statement = statement.where(false())
        if scope.branch_id is not None:
            statement = statement.where(ServiceCall.branch_id == scope.branch_id)
        if scope.principal_id is not None:
            statement = statement.where(ServiceCall.principal_id == scope.principal_id)
        if query.priority:
            statement = statement.where(ServiceCall.priority.in_(query.priority))
        if query.search:
            term = query.search.strip()
            statement = statement.where(
                or_(
                    ServiceCall.call_no.contains(term, autoescape=True),
                    ServiceCall.oem_call_id.contains(term, autoescape=True),
                    Customer.name.contains(term, autoescape=True),
                    MachineUnit.serial_number.contains(term, autoescape=True),
                )
            )
        # What needs attending first, then the longest waiting.
        return statement.order_by(
            _PRIORITY_RANK, ServiceCall.is_machine_down.desc(), ServiceCall.is_asc_priority.desc(), ServiceCall.id
        )

    def list_assigned(
        self, engineer_id: int, scope: RequestScope, query: AssignedServiceCallQuery
    ) -> Page[AssignedServiceCallListItem]:
        return paginate(
            self._session, self.assigned_statement(engineer_id, scope, query), query, AssignedServiceCallListItem
        )

    @staticmethod
    def assigned_statement(
        engineer_id: int, scope: RequestScope, query: AssignedServiceCallQuery
    ) -> Select[*tuple[Any, ...]]:
        my_visit = _planned_visit_date(engineer_id)
        statement = (
            select(
                ServiceCall.id,
                ServiceCall.call_no,
                ServiceCall.received_at,
                Principal.code.label("principal_code"),
                Customer.name.label("customer_name"),
                CustomerSite.site_name,
                CustomerSite.address.label("site_address"),
                CustomerSite.latitude.label("site_latitude"),
                CustomerSite.longitude.label("site_longitude"),
                MachineUnit.serial_number.label("machine_serial_no"),
                MachineModel.model_name.label("machine_model"),
                ServiceCall.complaint_description,
                ServiceCall.priority,
                ServiceCall.is_machine_down,
                ServiceCall.is_asc_priority,
                ServiceCall.coverage_type,
                ServiceCall.current_status,
                ServiceCall.caller_name,
                ServiceCall.caller_phone,
                ServiceCall.sla_due_at,
                my_visit.label("planned_visit_date"),
                ServiceCall.row_version,
            )
            .join(Customer, Customer.id == ServiceCall.customer_id)
            .join(Principal, Principal.id == ServiceCall.principal_id)
            .outerjoin(CustomerSite, CustomerSite.id == ServiceCall.customer_site_id)
            .outerjoin(MachineUnit, MachineUnit.id == ServiceCall.machine_unit_id)
            .outerjoin(MachineModel, MachineModel.id == MachineUnit.model_id)
            # The engineer only ever sees calls they are on, as lead or support. A reassigned call moves
            # to the new engineer, so it drops off the old engineer's list.
            .where(
                ServiceCall.is_active,
                or_(ServiceCall.assigned_engineer_id == engineer_id, supports_call([engineer_id])),
            )
        )
        # Row-level security plus the selected branch / brand narrow it further.
        if scope.branch_id is not None:
            statement = statement.where(ServiceCall.branch_id == scope.branch_id)
        if scope.principal_id is not None:
            statement = statement.where(ServiceCall.principal_id == scope.principal_id)
        # Closed and cancelled calls are hidden unless the client filters for them explicitly.
        if query.status:
            statement = statement.where(ServiceCall.current_status.in_(query.status))
        else:
            statement = statement.where(ServiceCall.current_status.notin_(_CLOSED_STATUSES))
        if query.search:
            term = query.search.strip()
            statement = statement.where(
                or_(
                    ServiceCall.call_no.contains(term, autoescape=True),
                    ServiceCall.oem_call_id.contains(term, autoescape=True),
                    Customer.name.contains(term, autoescape=True),
                    MachineUnit.serial_number.contains(term, autoescape=True),
                )
            )
        if query.visit_date is not None:
            statement = statement.where(_visit_planned_on(query.visit_date, engineer_id))
        my_day = func.coalesce(my_visit, _NO_DAY)
        columns = {**_ASSIGNED_SORT_COLUMNS, "visitDate": my_day}
        if query.sort and query.sort != "visitDate" and query.sort.removeprefix("-") in columns:
            return order_by_sort(statement, query.sort, columns, default="visitDate", tiebreaker=ServiceCall.id.desc())
        # Default: the engineer's days in order, undated calls last, and the most urgent first within a day.
        return statement.order_by(my_day, _PRIORITY_RANK, ServiceCall.id.desc())
