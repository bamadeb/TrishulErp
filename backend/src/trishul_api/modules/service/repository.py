from typing import Any

from sqlalchemy import Select, case, func, or_, select
from sqlalchemy.orm import Session

from trishul_api.auth import RequestScope
from trishul_api.common.paging import SortColumns, order_by_sort, paginate
from trishul_api.common.schemas import Page
from trishul_api.db.models import Customer, Employee, MachineModel, MachineUnit, Principal, ServiceCall
from trishul_api.modules.service.schemas import ServiceCallListItem, ServiceCallQuery

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

    @staticmethod
    def list_statement(scope: RequestScope, query: ServiceCallQuery) -> Select[*tuple[Any, ...]]:
        statement = (
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
