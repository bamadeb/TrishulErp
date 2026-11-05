from typing import Literal

from pydantic import Field

from trishul_api.common.schemas import ApiModel, InputModel, RowVersion, UtcDateTime

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
