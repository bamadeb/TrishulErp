from typing import Literal

from trishul_api.common.schemas import ApiModel

RowAction = Literal["insert", "update", "skip"]


class BydImportRow(ApiModel):
    """What the importer decided for one row of the file."""

    row_number: int
    c4c_ticket_id: str | None
    external_reference: str | None
    subject: str | None
    account: str | None
    action: RowAction
    call_no: str | None  # the call this row created or matched (null in preview for inserts)
    customer_matched: bool
    machine_matched: bool
    engineer_matched: bool
    needs_linking: bool
    messages: list[str]


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
