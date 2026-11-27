"""Bulk item price import, its history, the item price change log and the change limit."""

from datetime import date
from decimal import Decimal
from typing import Literal

from pydantic import Field

from trishul_api.common.schemas import ApiModel, InputModel, PageQuery, RowVersion, UtcDateTime
from trishul_api.db.models.price_import import (
    PriceChangeSource,
    PriceField,
    PriceImportLayout,
    PriceImportLineAction,
    PriceImportLineOutcome,
    PriceImportStatus,
)


class PriceImportBatch(ApiModel):
    """One uploaded price file. Until it is applied, the counts are what the check found."""

    id: int
    batch_no: str | None
    file_name: str
    file_size: int
    has_file: bool
    file_layout: PriceImportLayout
    price_list_id: int | None
    price_list_name: str | None
    sap_price_field: PriceField | None
    reason: str
    status: PriceImportStatus
    max_change_pct: Decimal | None = Field(description="The limit when the file was checked.")
    total_rows: int
    valid_count: int
    invalid_count: int
    duplicate_count: int
    changed_count: int
    unchanged_count: int
    over_limit_count: int
    updated_count: int
    failed_count: int
    skipped_count: int
    error_message: str | None
    uploaded_by_user_id: int | None
    uploaded_by_name: str | None
    uploaded_at: UtcDateTime
    confirmed_by_name: str | None
    confirmed_at: UtcDateTime | None
    approved_by_name: str | None
    approved_at: UtcDateTime | None
    rejected_by_name: str | None
    rejected_at: UtcDateTime | None
    decision_note: str | None
    completed_at: UtcDateTime | None
    repeat_of_batch_no: str | None = Field(None, description="An earlier batch that imported the same file.")
    can_confirm: bool = Field(False, description="The current user may confirm this batch now.")
    can_approve: bool = Field(False, description="The current user may approve or reject this batch now.")


class PriceImportLineOut(ApiModel):
    id: int
    row_number: int
    item_code: str | None
    item_id: int | None
    item_name: str | None
    action: PriceImportLineAction = Field(description="What the check found.")
    outcome: PriceImportLineOutcome | None = Field(description="What the import did; empty until applied.")
    old_selling: Decimal | None
    new_selling: Decimal | None
    old_purchase: Decimal | None
    new_purchase: Decimal | None
    old_mrp: Decimal | None
    new_mrp: Decimal | None
    max_change_pct: Decimal | None = Field(description="The biggest change of the row's prices, in percent (signed).")
    over_limit: bool
    reason: str | None
    messages: list[str]


class PriceImportQuery(PageQuery):
    status: PriceImportStatus | None = None
    uploaded_by_user_id: int | None = None
    date_from: date | None = Field(None, description="Uploaded on or after this day.")
    date_to: date | None = Field(None, description="Uploaded on or before this day.")


PriceLineFilter = Literal[
    "Change", "Unchanged", "Duplicate", "Error", "Increase", "Decrease", "OverLimit",
    "Updated", "Skipped", "Failed",
]  # fmt: skip


class PriceImportLineQuery(PageQuery):
    status: PriceLineFilter | None = None


class PriceImportConfirm(InputModel):
    import_again: bool = Field(False, description="Confirm even though the same file was imported before.")


class PriceImportDecision(InputModel):
    note: str | None = Field(None, max_length=500)


class PriceImportUploader(ApiModel):
    id: int
    name: str


class PriceListOption(ApiModel):
    id: int
    code: str
    name: str
    price_list_type: str
    principal_code: str | None


class PriceImportOptions(ApiModel):
    price_lists: list[PriceListOption]
    default_price_list_id: int | None
    max_change_pct: Decimal


class PriceSettings(ApiModel):
    max_change_pct: Decimal
    row_version: RowVersion | None = Field(description="Send in If-Match to change the setting.")


class PriceSettingsUpdate(InputModel):
    max_change_pct: Decimal = Field(ge=0, le=1000, max_digits=6, decimal_places=2)


class ItemPriceChange(ApiModel):
    id: int
    item_id: int
    item_code: str
    price_list_name: str | None
    old_selling: Decimal | None
    new_selling: Decimal | None
    old_purchase: Decimal | None
    new_purchase: Decimal | None
    old_mrp: Decimal | None
    new_mrp: Decimal | None
    source: PriceChangeSource
    import_id: int | None
    batch_no: str | None
    reason: str | None
    changed_by_name: str | None
    changed_at: UtcDateTime
