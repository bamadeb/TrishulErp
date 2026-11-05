from typing import Any

from sqlalchemy import Select, or_, select
from sqlalchemy.orm import Session

from trishul_api.common.paging import SortColumns, order_by_sort, paginate
from trishul_api.common.schemas import Page
from trishul_api.db.models import Customer, Lead, SalesActivity
from trishul_api.modules.presales.schemas import (
    FIELD_ACTIVITY_TYPES,
    AssignedSalesActivityListItem,
    AssignedSalesActivityQuery,
)

_SORT_COLUMNS: SortColumns = {
    "plannedAt": SalesActivity.planned_at,
    "customerName": Customer.name,
}


class SalesActivityRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def list_assigned(
        self, employee_id: int, query: AssignedSalesActivityQuery
    ) -> Page[AssignedSalesActivityListItem]:
        return paginate(
            self._session, self.assigned_statement(employee_id, query), query, AssignedSalesActivityListItem
        )

    @staticmethod
    def assigned_statement(employee_id: int, query: AssignedSalesActivityQuery) -> Select[*tuple[Any, ...]]:
        statement = (
            select(
                SalesActivity.id,
                SalesActivity.activity_type,
                Customer.name.label("customer_name"),
                Lead.prospect_name.label("lead_name"),
                SalesActivity.planned_at,
                SalesActivity.started_at,
                SalesActivity.ended_at,
                SalesActivity.notes,
                SalesActivity.next_follow_up_at,
                SalesActivity.row_version,
            )
            .outerjoin(Customer, Customer.id == SalesActivity.customer_id)
            .outerjoin(Lead, Lead.id == SalesActivity.lead_id)
            # Only the signed-in salesperson's own activities; there is no branch/brand column here,
            # so employee ownership is the access boundary.
            .where(SalesActivity.is_active, SalesActivity.employee_id == employee_id)
        )
        if query.activity_type:
            statement = statement.where(SalesActivity.activity_type.in_(query.activity_type))
        else:
            # Default to the field activities you travel for, and only those not yet completed.
            statement = statement.where(
                SalesActivity.activity_type.in_(FIELD_ACTIVITY_TYPES), SalesActivity.ended_at.is_(None)
            )
        if query.search:
            term = query.search.strip()
            statement = statement.where(
                or_(
                    Customer.name.contains(term, autoescape=True),
                    Lead.prospect_name.contains(term, autoescape=True),
                    SalesActivity.notes.contains(term, autoescape=True),
                )
            )
        # Soonest planned first; stable by id for consistent paging.
        return order_by_sort(
            statement, query.sort, _SORT_COLUMNS, default="plannedAt", tiebreaker=SalesActivity.id.desc()
        )
