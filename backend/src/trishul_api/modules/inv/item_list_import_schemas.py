"""Item list import (Excel / CSV into the item master) and its history."""

from datetime import date
from typing import Literal

from pydantic import Field

from trishul_api.common.schemas import ApiModel, PageQuery, UtcDateTime
from trishul_api.db.models.item_import import (
    ItemImportDuplicateMode,
    ItemImportLineAction,
    ItemImportLineOutcome,
    ItemImportStatus,
)


class ItemImportFieldChange(ApiModel):
    field: str
    old: str | None = Field(alias="from")
    new: str | None = Field(alias="to")


class ItemImportBatch(ApiModel):
    """One uploaded item list. Until it is confirmed (status Pending) the counts are what the check found:
    validCount rows can be imported, failedCount have errors, skippedCount are duplicates."""

    id: int
    batch_no: str | None
    file_name: str
    file_size: int
    has_file: bool
    duplicate_mode: ItemImportDuplicateMode
    status: ItemImportStatus
    total_rows: int
    valid_count: int
    created_count: int
    updated_count: int
    failed_count: int
    skipped_count: int
    error_message: str | None
    uploaded_by_user_id: int | None
    uploaded_by_name: str | None
    uploaded_at: UtcDateTime
    completed_at: UtcDateTime | None
    can_confirm: bool = Field(False, description="The current user may confirm this batch now.")


class ItemImportLineOut(ApiModel):
    id: int
    row_number: int
    item_code: str | None
    description: str | None
    action: ItemImportLineAction = Field(description="What the check planned.")
    outcome: ItemImportLineOutcome | None = Field(description="What the import did; empty until confirmed.")
    item_id: int | None
    messages: list[str]
    changes: list[ItemImportFieldChange]


ItemImportSortKey = Literal["uploadedAt", "fileName", "batchNo", "totalRows", "status"]


class ItemImportQuery(PageQuery):
    status: ItemImportStatus | None = None
    uploaded_by_user_id: int | None = None
    date_from: date | None = Field(None, description="Uploaded on or after this day.")
    date_to: date | None = Field(None, description="Uploaded on or before this day.")


LineFilter = Literal["Create", "Update", "Skip", "Error", "Created", "Updated", "Skipped", "Failed"]


class ItemImportLineQuery(PageQuery):
    status: LineFilter | None = Field(None, description="A planned action (before confirmation) or an outcome.")


class ItemImportUploader(ApiModel):
    id: int
    name: str
