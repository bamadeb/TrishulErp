from collections.abc import Set

from sqlalchemy import select
from sqlalchemy.orm import Session

from trishul_api.db.models import Branch, LookupType, LookupValue, Principal
from trishul_api.modules.core.schemas import BranchRef, LookupValueOut, PrincipalRef


class CoreRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def branches(self, ids: Set[int] | None) -> list[BranchRef]:
        """Active branches; ids None means all."""
        query = select(Branch.id, Branch.code, Branch.name).where(Branch.is_active).order_by(Branch.name)
        if ids is not None:
            query = query.where(Branch.id.in_(ids))
        return [BranchRef.model_validate(row) for row in self._session.execute(query)]

    def principals(self, ids: Set[int] | None) -> list[PrincipalRef]:
        query = select(Principal.id, Principal.code, Principal.name).where(Principal.is_active).order_by(Principal.name)
        if ids is not None:
            query = query.where(Principal.id.in_(ids))
        return [PrincipalRef.model_validate(row) for row in self._session.execute(query)]

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
