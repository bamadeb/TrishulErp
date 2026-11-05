from sqlalchemy import func, select
from sqlalchemy.orm import Session

from trishul_api.auth import CurrentUser
from trishul_api.common.concurrency import check_row_version
from trishul_api.common.errors import ApiError, Forbidden, NotFound
from trishul_api.db.models import AppUser, Attachment, Employee
from trishul_api.modules.core.documents import storage
from trishul_api.modules.core.documents.registry import DocumentTarget, target_for
from trishul_api.modules.core.documents.schemas import DocumentCategory, DocumentOut, DocumentUpdate


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
        if not target.can_view(self._db, user, entity_id):
            raise NotFound("Record not found.")
        return target

    def _editable(self, user: CurrentUser, entity_type: str, entity_id: int) -> DocumentTarget:
        target = self._viewable(user, entity_type, entity_id)
        if not target.can_edit(self._db, user, entity_id):
            raise Forbidden("You may not change the documents of this record.")
        return target

    def _document(self, document_id: int) -> Attachment:
        row = self._db.get(Attachment, document_id)
        # Employee photos use the same table but have their own endpoints; they are not documents.
        if row is None or not row.is_active or target_for(row.entity_type) is None:
            raise NotFound("Document not found.")
        return row

    # ------------------------------------------------------------------ reads

    def list(self, user: CurrentUser, entity_type: str, entity_id: int) -> list[DocumentOut]:
        target = self._viewable(user, entity_type, entity_id)
        can_edit = target.can_edit(self._db, user, entity_id)
        rows = self._db.scalars(
            select(Attachment)
            .where(Attachment.entity_type == entity_type, Attachment.entity_id == entity_id, Attachment.is_active)
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
        target = self._editable(user, entity_type, entity_id)
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
        self._editable(user, row.entity_type, row.entity_id)
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
        self._editable(user, row.entity_type, row.entity_id)
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
