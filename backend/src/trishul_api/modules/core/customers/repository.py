from collections.abc import Collection
from typing import Any

from sqlalchemy import ColumnElement, Select, func, or_, select
from sqlalchemy.orm import Session

from trishul_api.common.paging import SortColumns, order_by_sort, paginate
from trishul_api.common.schemas import Page
from trishul_api.db.models import Company, Customer, State
from trishul_api.modules.core.customers.schemas import (
    CompanyOption,
    CustomerListItem,
    CustomerQuery,
    StateOption,
)

_COMPANY_NAME: ColumnElement[str | None] = func.coalesce(Company.trade_name, Company.legal_name)

_SORT_COLUMNS: SortColumns = {
    "code": Customer.code,
    "name": Customer.name,
    "customerType": Customer.customer_type,
    "priorityTier": Customer.priority_tier,
    "createdAt": Customer.created_at,
}


def _list_select() -> Select[*tuple[Any, ...]]:
    """Columns of CustomerListItem: the customer plus its billing state name."""
    return select(
        Customer.id,
        Customer.code,
        Customer.name,
        Customer.customer_type,
        Customer.primary_phone,
        Customer.email,
        Customer.gstin,
        Customer.billing_state_id,
        State.name.label("billing_state_name"),
        Customer.priority_tier,
        Customer.is_asc_customer,
        Customer.is_active,
        Customer.created_at,
    ).outerjoin(State, State.id == Customer.billing_state_id)


class CustomerRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    # ------------------------------------------------------------------ reads

    def search(self, query: CustomerQuery) -> Page[CustomerListItem]:
        statement = _list_select()
        if query.status != "all":
            statement = statement.where(Customer.is_active == (query.status == "active"))
        if query.customer_type is not None:
            statement = statement.where(Customer.customer_type == query.customer_type)
        if query.priority_tier is not None:
            statement = statement.where(Customer.priority_tier == query.priority_tier)
        if query.search:
            term = query.search.strip()
            statement = statement.where(
                or_(
                    Customer.code.contains(term, autoescape=True),
                    Customer.name.contains(term, autoescape=True),
                    Customer.primary_phone.contains(term, autoescape=True),
                    Customer.gstin.contains(term, autoescape=True),
                    Customer.email.contains(term, autoescape=True),
                )
            )
        statement = order_by_sort(statement, query.sort, _SORT_COLUMNS, default="name", tiebreaker=Customer.id.asc())
        return paginate(self._session, statement, query, CustomerListItem)

    def get(self, customer_id: int) -> Customer | None:
        return self._session.get(Customer, customer_id)

    def detail_row(self, customer_id: int) -> dict[str, Any]:
        """One customer with every field CustomerDetail needs; the customer must exist."""
        statement = (
            _list_select()
            .add_columns(
                Customer.company_id,
                _COMPANY_NAME.label("company_name"),
                Customer.alternate_phone,
                Customer.pan,
                Customer.gst_registration_type,
                Customer.billing_address,
                Customer.row_version,
            )
            .outerjoin(Company, Company.id == Customer.company_id)
            .where(Customer.id == customer_id)
        )
        return dict(self._session.execute(statement).mappings().one())

    # ------------------------------------------------------------------ option lists (form dropdowns)

    def companies(self) -> list[CompanyOption]:
        rows = self._session.execute(
            select(Company.id, _COMPANY_NAME.label("name")).where(Company.is_active).order_by(_COMPANY_NAME)
        ).mappings()
        return [CompanyOption.model_validate(row) for row in rows]

    def states(self) -> list[StateOption]:
        rows = self._session.execute(select(State.id, State.name, State.gst_state_code).order_by(State.name)).mappings()
        return [StateOption.model_validate(row) for row in rows]

    # ------------------------------------------------------------------ checks

    def code_owner(self, code: str) -> int | None:
        """The id of the customer holding this code, or None."""
        return self._session.scalar(select(Customer.id).where(Customer.code == code).limit(1))

    def missing(self, model: type[Any], ids: Collection[int], *, active: bool = True) -> set[int]:
        """Ids in `ids` that are not rows of `model` (and, when `active`, not active rows)."""
        wanted = {i for i in ids if i is not None}
        if not wanted:
            return set()
        statement = select(model.id).where(model.id.in_(wanted))
        if active:
            statement = statement.where(model.is_active)
        return wanted - set(self._session.scalars(statement))

    # ------------------------------------------------------------------ writes (committed by the service)

    def add(self, row: object) -> None:
        self._session.add(row)

    def flush(self) -> None:
        self._session.flush()
