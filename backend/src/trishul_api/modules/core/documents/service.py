import builtins
from datetime import datetime, time, timedelta

from sqlalchemy import and_, func, not_, select
from sqlalchemy.orm import Session

from trishul_api.auth import CurrentUser
from trishul_api.common.concurrency import check_row_version
from trishul_api.common.errors import ApiError, Forbidden, NotFound
from trishul_api.common.schemas import Page
from trishul_api.db.models import AppUser, Attachment, Employee
from trishul_api.modules.core.documents import storage
from trishul_api.modules.core.documents.registry import DocumentTarget, registered_targets, target_for
from trishul_api.modules.core.documents.schemas import (
    DocumentCategory,
    DocumentEntityType,
    DocumentLibraryItem,
    DocumentLibraryQuery,
    DocumentOut,
    DocumentRecordOption,
    DocumentUpdate,
)

# Permissions of the document administrators (Admin role): see every document / rename and remove them.
VIEW_ALL = ("core.document.view", "core.document.manage")
MANAGE_ALL = "core.document.manage"

_LIBRARY_SORT = {
    "uploadedAt": Attachment.created_at,
    "fileName": Attachment.file_name,
    "fileSizeBytes": Attachment.file_size_bytes,
    "category": Attachment.category,
    "entityType": Attachment.entity_type,
}


class DocumentService:
    """Upload, list, download, rename and remove documents of any registered record type."""

    def __init__(self, db: Session) -> None:
        self._db = db

    # ------------------------------------------------------------------ access

    def _target(self, entity_type: str) -> DocumentTarget:
        target = target_for(entity_type)
        if target is None:
            raise ApiError(f"Documents cannot be attached to '{entity_type}'.")
        return target

    def _viewable(self, user: CurrentUser, entity_type: str, entity_id: int) -> DocumentTarget:
        target = self._target(entity_type)
        # Document administrators see every document, whatever the record's own rules say.
        if user.can(*VIEW_ALL):
            allowed = target.exists(self._db, user, entity_id)
        else:
            allowed = target.can_view(self._db, user, entity_id)
        if not allowed:
            raise NotFound("Record not found.")
        return target

    def _editable(
        self, user: CurrentUser, entity_type: str, entity_id: int, *, administrator: bool = False
    ) -> DocumentTarget:
        """`administrator` lets a holder of core.document.manage add, rename or remove documents of any
        registered record (the Administration > Documents page). Everyone else follows the record's rules."""
        target = self._viewable(user, entity_type, entity_id)
        if administrator and user.can(MANAGE_ALL):
            return target
        if not target.can_edit(self._db, user, entity_id):
            raise Forbidden("You may not change the documents of this record.")
        return target

    def _document(self, document_id: int) -> Attachment:
        row = self._db.get(Attachment, document_id)
        # Rows of other kinds (signatures, payslip PDFs, employee photos ...) share the table but have their
        # own screens; they are not documents.
        target = target_for(row.entity_type) if row is not None else None
        if row is None or not row.is_active or target is None or row.category in target.exclude_categories:
            raise NotFound("Document not found.")
        return row

    @staticmethod
    def _not_documents() -> list:
        """SQL conditions that leave out attachment rows that are not documents of their record type."""
        return [
            not_(and_(Attachment.entity_type == t.entity_type, Attachment.category.in_(t.exclude_categories)))
            for t in registered_targets()
            if t.exclude_categories
        ]

    # ------------------------------------------------------------------ reads

    def list(self, user: CurrentUser, entity_type: str, entity_id: int) -> list[DocumentOut]:
        target = self._viewable(user, entity_type, entity_id)
        can_edit = target.can_edit(self._db, user, entity_id)
        rows = self._db.scalars(
            select(Attachment)
            .where(
                Attachment.entity_type == entity_type,
                Attachment.entity_id == entity_id,
                Attachment.is_active,
                *self._not_documents(),
            )
            .order_by(Attachment.id)
        ).all()
        names = self._uploader_names({r.created_by_user_id for r in rows if r.created_by_user_id})
        return [self._out(r, names, can_edit) for r in rows]

    def download(self, user: CurrentUser, document_id: int) -> tuple[Attachment, bytes]:
        row = self._document(document_id)
        self._viewable(user, row.entity_type, row.entity_id)
        raw = storage.read(row.s3_key)
        if raw is None:
            raise NotFound("The file is no longer available.")
        return row, raw

    def entity_types(self) -> builtins.list[DocumentEntityType]:
        return [
            DocumentEntityType(entity_type=t.entity_type, label=t.label or t.entity_type) for t in registered_targets()
        ]

    def records(self, user: CurrentUser, entity_type: str, search: str) -> builtins.list[DocumentRecordOption]:
        """Records of a module a document can be attached to, found by what the user typed."""
        target = self._target(entity_type)
        if target.search is None:
            raise ApiError(f"Records of '{entity_type}' cannot be searched yet.")
        return [
            DocumentRecordOption(id=i, label=label) for i, label in target.search(self._db, user, search.strip(), 20)
        ]

    def library(self, user: CurrentUser, query: DocumentLibraryQuery) -> Page[DocumentLibraryItem]:
        """Every document of every registered record type, newest first (Administration)."""
        targets = {t.entity_type: t for t in registered_targets()}
        statement = select(Attachment).where(
            Attachment.is_active, Attachment.entity_type.in_(sorted(targets)), *self._not_documents()
        )
        if query.entity_type:
            statement = statement.where(Attachment.entity_type == query.entity_type)
        if query.category:
            statement = statement.where(Attachment.category == query.category)
        if query.search:
            statement = statement.where(Attachment.file_name.contains(query.search, autoescape=True))
        if query.uploaded_from:
            statement = statement.where(Attachment.created_at >= datetime.combine(query.uploaded_from, time.min))
        if query.uploaded_to:
            statement = statement.where(
                Attachment.created_at < datetime.combine(query.uploaded_to + timedelta(days=1), time.min)
            )
        total = self._db.scalar(select(func.count()).select_from(statement.subquery())) or 0
        column = _LIBRARY_SORT.get((query.sort or "-uploadedAt").lstrip("-"), Attachment.created_at)
        descending = (query.sort or "-uploadedAt").startswith("-")
        rows = self._db.scalars(
            statement.order_by(column.desc() if descending else column.asc(), Attachment.id.desc())
            .offset((query.page - 1) * query.page_size)
            .limit(query.page_size)
        ).all()
        names = self._uploader_names({r.created_by_user_id for r in rows if r.created_by_user_id})
        labels: dict[str, dict[int, str]] = {}
        for entity_type in {r.entity_type for r in rows}:
            describe = targets[entity_type].describe
            labels[entity_type] = (
                describe(self._db, sorted({r.entity_id for r in rows if r.entity_type == entity_type}))
                if describe
                else {}
            )
        can_manage = user.can(MANAGE_ALL)
        return Page(
            items=[
                DocumentLibraryItem(
                    id=r.id,
                    entity_type=r.entity_type,
                    entity_label=targets[r.entity_type].label or r.entity_type,
                    entity_id=r.entity_id,
                    record_label=labels[r.entity_type].get(r.entity_id),
                    category=r.category,
                    file_name=r.file_name,
                    content_type=r.content_type,
                    file_size_bytes=r.file_size_bytes,
                    uploaded_at=r.created_at,
                    uploaded_by_name=names.get(r.created_by_user_id) if r.created_by_user_id else None,
                    can_delete=can_manage,
                    row_version=r.row_version,
                )
                for r in rows
            ],
            total=total,
            page=query.page,
            page_size=query.page_size,
        )

    # ------------------------------------------------------------------ writes

    def upload(
        self,
        user: CurrentUser,
        entity_type: str,
        entity_id: int,
        category: DocumentCategory,
        file_name: str | None,
        raw: bytes,
    ) -> DocumentOut:
        target = self._editable(user, entity_type, entity_id, administrator=True)
        if category in target.exclude_categories:
            raise ApiError(f"'{category}' files cannot be added here; they are managed on the record's own screen.")
        name = storage.clean_file_name(file_name)
        content_type = storage.validate_file(name, raw)
        count = self._db.scalar(
            select(func.count())
            .select_from(Attachment)
            .where(Attachment.entity_type == entity_type, Attachment.entity_id == entity_id, Attachment.is_active)
        )
        if (count or 0) >= target.max_documents:
            raise ApiError(f"At most {target.max_documents} documents can be attached to one record.")
        row = Attachment(
            entity_type=entity_type,
            entity_id=entity_id,
            category=category,
            file_name=name,
            content_type=content_type,
            file_size_bytes=len(raw),
            s3_key=storage.store(entity_type, entity_id, name, raw),
            created_by_user_id=user.id,
        )
        self._db.add(row)
        self._db.commit()
        return self._out(row, self._uploader_names({user.id}), True)

    def update(self, user: CurrentUser, document_id: int, row_version: bytes, data: DocumentUpdate) -> DocumentOut:
        row = self._document(document_id)
        self._editable(user, row.entity_type, row.entity_id, administrator=True)
        check_row_version(row.row_version, row_version)
        if data.file_name is not None:
            new_name = storage.clean_file_name(data.file_name)
            if new_name.rpartition(".")[2].lower() != row.file_name.rpartition(".")[2].lower():
                raise ApiError("A document keeps its file type: change the name, not the extension.")
            row.file_name = new_name
        if data.category is not None:
            row.category = data.category
        row.updated_by_user_id = user.id
        self._db.commit()
        return self._out(row, self._uploader_names({row.created_by_user_id} - {None}), True)

    def delete(self, user: CurrentUser, document_id: int, row_version: bytes) -> None:
        """Soft delete: the row stays for the audit trail, the file is removed from storage."""
        row = self._document(document_id)
        self._editable(user, row.entity_type, row.entity_id, administrator=True)
        check_row_version(row.row_version, row_version)
        row.is_active = False
        row.updated_by_user_id = user.id
        self._db.commit()
        storage.remove(row.s3_key)

    # ------------------------------------------------------------------ helpers

    def _uploader_names(self, user_ids: set[int | None]) -> dict[int, str]:
        ids = sorted(i for i in user_ids if i is not None)
        if not ids:
            return {}
        rows = self._db.execute(
            select(AppUser.id, AppUser.username, Employee.first_name, Employee.last_name)
            .outerjoin(Employee, Employee.id == AppUser.employee_id)
            .where(AppUser.id.in_(ids))
        )
        return {r.id: " ".join(p for p in (r.first_name, r.last_name) if p) or r.username for r in rows}

    @staticmethod
    def _out(row: Attachment, names: dict[int, str], can_edit: bool) -> DocumentOut:
        return DocumentOut(
            id=row.id,
            entity_type=row.entity_type,
            entity_id=row.entity_id,
            category=row.category,
            file_name=row.file_name,
            content_type=row.content_type,
            file_size_bytes=row.file_size_bytes,
            uploaded_at=row.created_at,
            uploaded_by_user_id=row.created_by_user_id,
            uploaded_by_name=names.get(row.created_by_user_id) if row.created_by_user_id else None,
            can_delete=can_edit,
            row_version=row.row_version,
        )
