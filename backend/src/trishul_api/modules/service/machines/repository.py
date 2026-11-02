from typing import Any

from sqlalchemy import Select, or_, select
from sqlalchemy.orm import Session

from trishul_api.auth import RequestScope
from trishul_api.common.paging import SortColumns, order_by_sort, paginate
from trishul_api.common.schemas import Page
from trishul_api.db.models import Customer, MachineModel, MachineUnit, Principal
from trishul_api.modules.service.machines.schemas import MachineListItem, MachineModelOption, MachineQuery

_SORT_COLUMNS: SortColumns = {
    "serialNumber": MachineUnit.serial_number,
    "modelName": MachineModel.model_name,
    "customerName": Customer.name,
    "warrantyEndDate": MachineUnit.warranty_end_date,
    "createdAt": MachineUnit.created_at,
}


def _list_select() -> Select[*tuple[Any, ...]]:
    """Columns of MachineListItem: the machine with its model and owner."""
    return (
        select(
            MachineUnit.id,
            MachineUnit.serial_number,
            MachineUnit.model_id,
            MachineModel.model_code,
            MachineModel.model_name,
            MachineModel.product_line,
            MachineUnit.customer_id,
            Customer.code.label("customer_code"),
            Customer.name.label("customer_name"),
            MachineUnit.status,
            MachineUnit.warranty_end_date,
            MachineUnit.current_hmr,
            MachineUnit.is_active,
            MachineUnit.created_at,
        )
        .join(MachineModel, MachineModel.id == MachineUnit.model_id)
        .outerjoin(Customer, Customer.id == MachineUnit.customer_id)
    )


class MachineRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    # ------------------------------------------------------------------ reads

    def search(self, scope: RequestScope, query: MachineQuery) -> Page[MachineListItem]:
        statement = _list_select()
        # Row-level security limits the brands the user may see; this narrows it to the selected one.
        if scope.principal_id is not None:
            statement = statement.where(MachineUnit.principal_id == scope.principal_id)
        if query.status != "all":
            statement = statement.where(MachineUnit.is_active == (query.status == "active"))
        if query.customer_id is not None:
            statement = statement.where(MachineUnit.customer_id == query.customer_id)
        if query.model_id is not None:
            statement = statement.where(MachineUnit.model_id == query.model_id)
        if query.search:
            term = query.search.strip()
            statement = statement.where(
                or_(
                    MachineUnit.serial_number.contains(term, autoescape=True),
                    MachineUnit.engine_number.contains(term, autoescape=True),
                    MachineUnit.registration_number.contains(term, autoescape=True),
                    MachineUnit.oem_registered_product_id.contains(term, autoescape=True),
                    MachineModel.model_name.contains(term, autoescape=True),
                    Customer.name.contains(term, autoescape=True),
                    Customer.code.contains(term, autoescape=True),
                )
            )
        statement = order_by_sort(
            statement, query.sort, _SORT_COLUMNS, default="serialNumber", tiebreaker=MachineUnit.id.asc()
        )
        return paginate(self._session, statement, query, MachineListItem)

    def get(self, machine_id: int) -> MachineUnit | None:
        return self._session.get(MachineUnit, machine_id)

    def detail_row(self, machine_id: int) -> dict[str, Any]:
        """One machine with every field MachineDetail needs; the machine must exist."""
        statement = (
            _list_select()
            .add_columns(
                MachineUnit.principal_id,
                Principal.code.label("principal_code"),
                MachineUnit.engine_number,
                MachineUnit.registration_number,
                MachineUnit.year_of_manufacture,
                MachineUnit.sale_date,
                MachineUnit.commissioning_date,
                MachineUnit.warranty_start_date,
                MachineUnit.oem_registered_product_id,
                MachineUnit.row_version,
            )
            .join(Principal, Principal.id == MachineUnit.principal_id)
            .where(MachineUnit.id == machine_id)
        )
        return dict(self._session.execute(statement).mappings().one())

    def models(self, scope: RequestScope) -> list[MachineModelOption]:
        statement = select(
            MachineModel.id, MachineModel.model_code, MachineModel.model_name, MachineModel.product_line
        ).where(MachineModel.is_active)
        if scope.principal_id is not None:
            statement = statement.where(MachineModel.principal_id == scope.principal_id)
        rows = self._session.execute(statement.order_by(MachineModel.model_name)).mappings()
        return [MachineModelOption.model_validate(row) for row in rows]

    # ------------------------------------------------------------------ checks

    def serial_owner(self, serial_number: str) -> int | None:
        """The id of the machine holding this serial number, or None."""
        return self._session.scalar(select(MachineUnit.id).where(MachineUnit.serial_number == serial_number).limit(1))

    def active_model(self, model_id: int) -> MachineModel | None:
        model = self._session.get(MachineModel, model_id)
        return model if model is not None and model.is_active else None

    def active_customer(self, customer_id: int) -> bool:
        return (
            self._session.scalar(select(Customer.id).where(Customer.id == customer_id, Customer.is_active).limit(1))
            is not None
        )

    # ------------------------------------------------------------------ writes (committed by the service)

    def add(self, row: object) -> None:
        self._session.add(row)

    def flush(self) -> None:
        self._session.flush()
