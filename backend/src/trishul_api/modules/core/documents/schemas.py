from datetime import date
from typing import Literal

from pydantic import Field

from trishul_api.common.schemas import ApiModel, InputModel, PageQuery, RowVersion, UtcDateTime

DocumentCategory = Literal["Document", "Invoice", "Photo", "Other"]


class DocumentOut(ApiModel):
    """A file attached to a record of any module (core.attachment)."""

    id: int
    entity_type: str = Field(description="The record's table, e.g. trk.manual_travel.")
    entity_id: int = Field(description="The record's id (the reference id).")
    category: str = Field(description="Document type.")
    file_name: str
    content_type: str | None
    file_size_bytes: int | None
    uploaded_at: UtcDateTime
    uploaded_by_user_id: int | None
    uploaded_by_name: str | None
    can_delete: bool = Field(description="The signed-in user may remove or rename this document.")
    row_version: RowVersion


class DocumentUpdate(InputModel):
    """Rename a document or change its type. The file itself is never replaced: upload a new one."""

    file_name: str | None = Field(None, min_length=1, max_length=200)
    category: DocumentCategory | None = None


class DocumentEntityType(ApiModel):
    """A kind of record that can carry documents (for the library's filter)."""

    entity_type: str
    label: str


class DocumentLibraryQuery(PageQuery):
    """Filters of the all-documents list (Administration)."""

    entity_type: str | None = Field(None, max_length=50, description="Only documents of this kind of record.")
    category: DocumentCategory | None = None
    uploaded_from: date | None = Field(None, description="Uploaded on or after this day (UTC).")
    uploaded_to: date | None = Field(None, description="Uploaded on or before this day (UTC).")


class DocumentLibraryItem(ApiModel):
    """A document with the record it belongs to, for the administration library."""

    id: int
    entity_type: str
    entity_label: str = Field(description="What kind of record: e.g. Manual travel.")
    entity_id: int
    record_label: str | None = Field(description="Which record, in words: e.g. BHADRAK/SC/00024 · Bus · 04 Nov 2026.")
    category: str
    file_name: str
    content_type: str | None
    file_size_bytes: int | None
    uploaded_at: UtcDateTime
    uploaded_by_name: str | None
    can_delete: bool
    row_version: RowVersion


class DocumentRecordOption(ApiModel):
    """A record a document can be attached to, found by search (the Documents page's record picker)."""

    id: int
    label: str
