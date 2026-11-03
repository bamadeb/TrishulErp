"""Reads the BYD import log: svc.byd_call_import (one row per upload) and its lines."""

import json
from typing import Any

from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session

from trishul_api.auth import CurrentUser, RequestScope
from trishul_api.common.paging import SortColumns, order_by_sort, paginate
from trishul_api.common.schemas import Page
from trishul_api.db.models import AppUser, Branch, BydCallImport, BydCallImportLine, Employee, Principal
from trishul_api.modules.service.imports.schemas import (
    BydImportLogDetail,
    BydImportLogItem,
    BydImportLogQuery,
    BydImportRow,
    FieldChange,
)

_SORT_COLUMNS: SortColumns = {"importedAt": BydCallImport.imported_at, "fileName": BydCallImport.file_name}


def _log_select() -> Select[*tuple[Any, ...]]:
    """Columns of BydImportLogItem."""
    who = func.coalesce(func.nullif(func.concat_ws(" ", Employee.first_name, Employee.last_name), ""), AppUser.username)
    return (
        select(
            BydCallImport.id,
            BydCallImport.file_name,
            BydCallImport.source_kind,
            Branch.name.label("branch_name"),
            Principal.code.label("principal_code"),
            BydCallImport.imported_at,
            who.label("imported_by_name"),
            BydCallImport.total_rows,
            BydCallImport.inserted_count,
            BydCallImport.updated_count,
            BydCallImport.unlinked_count,
            BydCallImport.failed_count,
        )
        .join(Branch, Branch.id == BydCallImport.branch_id)
        .join(Principal, Principal.id == BydCallImport.principal_id)
        .outerjoin(AppUser, AppUser.id == BydCallImport.imported_by_user_id)
        .outerjoin(Employee, Employee.id == AppUser.employee_id)
    )


class ImportLogRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def list(self, actor: CurrentUser, scope: RequestScope, query: BydImportLogQuery) -> Page[BydImportLogItem]:
        statement = _log_select()
        # The imports table has no row-level security, so limit it to the user's branches and brands here.
        if actor.branch_ids is not None:
            statement = statement.where(BydCallImport.branch_id.in_(actor.branch_ids or [0]))
        if actor.principal_ids is not None:
            statement = statement.where(BydCallImport.principal_id.in_(actor.principal_ids or [0]))
        if scope.branch_id is not None:
            statement = statement.where(BydCallImport.branch_id == scope.branch_id)
        if scope.principal_id is not None:
            statement = statement.where(BydCallImport.principal_id == scope.principal_id)
        if query.search:
            statement = statement.where(BydCallImport.file_name.contains(query.search.strip(), autoescape=True))
        statement = order_by_sort(
            statement, query.sort, _SORT_COLUMNS, default="-importedAt", tiebreaker=BydCallImport.id.desc()
        )
        return paginate(self._session, statement, query, BydImportLogItem)

    def detail(self, actor: CurrentUser, import_id: int) -> BydImportLogDetail | None:
        """One upload with every row, or None if it doesn't exist or is outside the user's branches/brands."""
        row = self._session.execute(_log_select().where(BydCallImport.id == import_id)).mappings().one_or_none()
        if row is None:
            return None
        ids = self._session.execute(
            select(BydCallImport.branch_id, BydCallImport.principal_id).where(BydCallImport.id == import_id)
        ).one()
        if not actor.can_use_branch(ids.branch_id) or not actor.can_see_principal(ids.principal_id):
            return None
        lines = self._session.scalars(
            select(BydCallImportLine)
            .where(BydCallImportLine.import_id == import_id)
            .order_by(BydCallImportLine.row_number, BydCallImportLine.id)
        )
        return BydImportLogDetail(**row, rows=[_row(line) for line in lines])


def _row(line: BydCallImportLine) -> BydImportRow:
    return BydImportRow(
        row_number=line.row_number,
        c4c_ticket_id=line.c4c_ticket_id,
        external_reference=line.external_reference,
        subject=line.subject,
        account=line.account,
        action=line.action,
        service_call_id=line.service_call_id,
        call_no=line.call_no,
        customer_matched=line.customer_matched,
        machine_matched=line.machine_matched,
        engineer_matched=line.engineer_matched,
        needs_linking=line.needs_linking,
        messages=line.messages.split("\n") if line.messages else [],
        changes=[FieldChange.model_validate(c) for c in json.loads(line.changes)] if line.changes else [],
    )
