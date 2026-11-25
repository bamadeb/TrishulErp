from collections.abc import Set

from sqlalchemy import case, select
from sqlalchemy.orm import Session, aliased

from trishul_api.db.models import Branch, Department, LookupType, LookupValue, Principal, Region, Role
from trishul_api.modules.core.brands.names import BRAND_COMPANY_NAME
from trishul_api.modules.core.schemas import BranchRef, LookupValueOut, PrincipalRef


class CoreRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def branches(self, ids: Set[int] | None) -> list[BranchRef]:
        """Active branches; ids None means all."""
        warehouse = aliased(Branch)
        query = (
            select(
                Branch.id,
                Branch.code,
                Branch.name,
                Branch.branch_type,
                case((Branch.branch_type == "Warehouse", Branch.id), else_=Branch.parent_warehouse_id).label(
                    "warehouse_id"
                ),
                case((Branch.branch_type == "Warehouse", Branch.name), else_=warehouse.name).label("warehouse_name"),
                Branch.region_id,
                Region.name.label("region_name"),
            )
            .outerjoin(warehouse, warehouse.id == Branch.parent_warehouse_id)
            .outerjoin(Region, Region.id == Branch.region_id)
            .where(Branch.is_active)
            .order_by(Branch.name)
        )
        if ids is not None:
            query = query.where(Branch.id.in_(ids))
        return [BranchRef.model_validate(row) for row in self._session.execute(query)]

    def principals(self, ids: Set[int] | None) -> list[PrincipalRef]:
        query = (
            select(Principal.id, Principal.code, Principal.name, BRAND_COMPANY_NAME)
            .where(Principal.is_active)
            .order_by(Principal.name)
        )
        if ids is not None:
            query = query.where(Principal.id.in_(ids))
        return [PrincipalRef.model_validate(row) for row in self._session.execute(query)]

    def derived_permissions(self, employee_id: int | None) -> frozenset[str]:
        """Permissions the user has from their position rather than a role, for the apps' menus only (the
        server checks the position itself): a department head works the department's complaints."""
        if employee_id is None:
            return frozenset()
        head = self._session.scalar(
            select(Department.id).where(Department.head_employee_id == employee_id, Department.is_active).limit(1)
        )
        return frozenset({"core.complaint.manage"}) if head is not None else frozenset()

    def role_names(self, codes: Set[str]) -> list[str]:
        """Names of the active roles among `codes`, alphabetically."""
        if not codes:
            return []
        return list(
            self._session.scalars(select(Role.name).where(Role.code.in_(codes), Role.is_active).order_by(Role.name))
        )

    def lookup_values(self, type_code: str) -> list[LookupValueOut] | None:
        """Active values of a lookup type, or None if the type does not exist."""
        type_id = self._session.scalar(select(LookupType.id).where(LookupType.code == type_code, LookupType.is_active))
        if type_id is None:
            return None
        rows = self._session.execute(
            select(LookupValue.id, LookupValue.code, LookupValue.label.label("name"), LookupValue.sort_order)
            .where(LookupValue.lookup_type_id == type_id, LookupValue.is_active)
            .order_by(LookupValue.sort_order, LookupValue.label)
        )
        return [LookupValueOut.model_validate(row) for row in rows]
