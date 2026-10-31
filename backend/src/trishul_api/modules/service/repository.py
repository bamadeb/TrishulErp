import builtins
from typing import Any

from sqlalchemy import Select, case, func, or_, select
from sqlalchemy.orm import Session, aliased

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
)
from trishul_api.modules.service.schemas import (
    AssignedServiceCallListItem,
    AssignedServiceCallQuery,
    CallStatusLogItem,
    EngineerOption,
    EngineerOptionQuery,
    MachineOptionQuery,
    MachineUnitOption,
    ServiceCallDetail,
    ServiceCallListItem,
    ServiceCallQuery,
)

# Calls the engineer no longer needs to travel to: hidden unless the client asks for them by status.
_CLOSED_STATUSES = ("Closed", "Cancelled")

# A call is assigned to a Service Engineer, so the assign picker lists only employees with that
# designation (hr.designation code), not every employee of the branch.
_SERVICE_ENGINEER_DESIGNATION = "SERVICE_ENG"

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
}


class ServiceCallRepository:
    """Read queries return response models directly (projections of just the columns a screen shows).
    Writes will go through a service and work with ORM objects."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def list(self, scope: RequestScope, query: ServiceCallQuery) -> Page[ServiceCallListItem]:
        return paginate(self._session, self.list_statement(scope, query), query, ServiceCallListItem)

    def get_list_item(self, call_id: int) -> ServiceCallListItem:
        """One call as the register shows it; the call must exist."""
        row = self._session.execute(self._register_select().where(ServiceCall.id == call_id)).mappings().one()
        return ServiceCallListItem.model_validate(row)

    def assignment(self, call_id: int) -> tuple[bool, int | None]:
        """(the call exists, its assigned engineer's employee id): a cheap check before showing its history."""
        row = self._session.execute(
            select(ServiceCall.assigned_engineer_id).where(ServiceCall.id == call_id, ServiceCall.is_active)
        ).one_or_none()
        return (row is not None, row[0] if row is not None else None)

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
        return ServiceCallDetail.model_validate(row) if row is not None else None

    # builtins.list: this class has a method named `list`, which otherwise shadows the builtin here.
    def machine_options(self, scope: RequestScope, query: MachineOptionQuery) -> builtins.list[MachineUnitOption]:
        """Machines to pick for a new call, narrowed to the selected brand and (optionally) customer."""
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
        return [MachineUnitOption.model_validate(row) for row in self._session.execute(statement).mappings()]

    def engineer_options(self, scope: RequestScope, query: EngineerOptionQuery) -> builtins.list[EngineerOption]:
        """Engineers a team lead can assign a call to: active Service Engineers of the selected branch."""
        name = func.concat_ws(" ", Employee.first_name, Employee.last_name)
        statement = (
            select(Employee.id, name.label("name"), Employee.employee_code)
            .join(Designation, Designation.id == Employee.designation_id)
            .where(Employee.is_active, Designation.code == _SERVICE_ENGINEER_DESIGNATION)
        )
        if scope.branch_id is not None:
            statement = statement.where(Employee.branch_id == scope.branch_id)
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
                Customer.name.label("customer_name"),
                MachineUnit.serial_number.label("machine_serial_no"),
                MachineModel.model_name.label("machine_model"),
                ServiceCall.complaint_description,
                ServiceCall.priority,
                ServiceCall.is_machine_down,
                ServiceCall.is_asc_priority,
                ServiceCall.coverage_type,
                ServiceCall.current_status,
                func.nullif(func.concat_ws(" ", Employee.first_name, Employee.last_name), "").label(
                    "assigned_engineer_name"
                ),
                ServiceCall.oem_call_id,
                ServiceCall.sla_due_at,
                ServiceCall.row_version,
            )
            .join(Customer, Customer.id == ServiceCall.customer_id)
            .join(Principal, Principal.id == ServiceCall.principal_id)
            .outerjoin(MachineUnit, MachineUnit.id == ServiceCall.machine_unit_id)
            .outerjoin(MachineModel, MachineModel.id == MachineUnit.model_id)
            .outerjoin(Employee, Employee.id == ServiceCall.assigned_engineer_id)
            .where(ServiceCall.is_active)
        )

    @staticmethod
    def list_statement(scope: RequestScope, query: ServiceCallQuery) -> Select[*tuple[Any, ...]]:
        statement = ServiceCallRepository._register_select()
        # Row-level security limits what the user may see; these narrow it to what they selected.
        if scope.branch_id is not None:
            statement = statement.where(ServiceCall.branch_id == scope.branch_id)
        if scope.principal_id is not None:
            statement = statement.where(ServiceCall.principal_id == scope.principal_id)
        if query.status:
            statement = statement.where(ServiceCall.current_status.in_(query.status))
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

        return order_by_sort(
            statement, query.sort, _SORT_COLUMNS, default="-receivedAt", tiebreaker=ServiceCall.id.desc()
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
                ServiceCall.row_version,
            )
            .join(Customer, Customer.id == ServiceCall.customer_id)
            .join(Principal, Principal.id == ServiceCall.principal_id)
            .outerjoin(CustomerSite, CustomerSite.id == ServiceCall.customer_site_id)
            .outerjoin(MachineUnit, MachineUnit.id == ServiceCall.machine_unit_id)
            .outerjoin(MachineModel, MachineModel.id == MachineUnit.model_id)
            # The engineer only ever sees calls assigned to them. A reassigned call moves to the new
            # engineer (assigned_engineer_id is updated), so it drops off the old engineer's list.
            .where(ServiceCall.is_active, ServiceCall.assigned_engineer_id == engineer_id)
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
        # Most urgent first (Critical → Low), stable by id for consistent paging.
        return order_by_sort(statement, query.sort, _SORT_COLUMNS, default="priority", tiebreaker=ServiceCall.id.desc())
