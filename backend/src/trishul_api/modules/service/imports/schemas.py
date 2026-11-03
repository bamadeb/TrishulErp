from typing import Literal

from pydantic import Field

from trishul_api.common.schemas import ApiModel, PageQuery, UtcDateTime

RowAction = Literal["insert", "update", "skip"]


class FieldChange(ApiModel):
    """One field an import changed on an existing call, as shown to people (names, not ids)."""

    field: str
    old: str | None = Field(description="Value before the import; dates are ISO 8601 UTC.")
    new: str | None = Field(description="Value after the import; dates are ISO 8601 UTC.")


class BydImportRow(ApiModel):
    """What the importer decided for one row of the file."""

    row_number: int
    c4c_ticket_id: str | None
    external_reference: str | None
    subject: str | None
    account: str | None
    action: RowAction
    service_call_id: int | None = None  # the call this row created or updated (null in preview)
    call_no: str | None  # the call this row created or matched (null in preview for inserts)
    customer_matched: bool
    machine_matched: bool
    engineer_matched: bool
    needs_linking: bool
    messages: list[str]
    changes: list[FieldChange] = Field(
        default_factory=list, description="For an applied update: the fields it changed. Empty otherwise."
    )


class BydImportSummary(ApiModel):
    """Counts for the whole file, shown on both preview and after import."""

    source_kind: str
    file_name: str
    total: int
    inserts: int
    updates: int
    skips: int
    needs_linking: int


class BydImportPreview(ApiModel):
    """Dry run: what would happen if this file were imported. Nothing is written."""

    summary: BydImportSummary
    rows: list[BydImportRow]


class BydImportResult(ApiModel):
    """Outcome of an applied import."""

    batch_id: int
    summary: BydImportSummary
    rows: list[BydImportRow]


class BydImportLogQuery(PageQuery):
    """search: file name."""


class BydImportLogItem(ApiModel):
    """One upload in the import log."""

    id: int
    file_name: str
    source_kind: str
    branch_name: str
    principal_code: str
    imported_at: UtcDateTime
    imported_by_name: str | None
    total_rows: int
    inserted_count: int
    updated_count: int
    unlinked_count: int
    failed_count: int


class BydImportLogDetail(BydImportLogItem):
    rows: list[BydImportRow] = Field(
        description="Every row of the file and what happened to it. Empty for imports made before row logging."
    )
