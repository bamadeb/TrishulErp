from decimal import Decimal
from typing import Literal

from pydantic import Field

from trishul_api.common.schemas import ApiModel

ImportAction = Literal["Create", "Update", "Unchanged", "Skip"]
IssueCode = Literal["duplicateInFile", "ambiguous", "missingHsn", "unknownHsn", "noPrice", "invalid"]
PriceField = Literal["mrp", "standardCost"]


class ItemImportIssue(ApiModel):
    code: IssueCode
    message: str


class ItemImportRow(ApiModel):
    row_number: int
    external_id: str | None
    material: str | None
    description: str | None
    hsn_code: str | None
    price: Decimal | None
    action: ImportAction
    item_code: str | None = Field(None, description="The item that is created or changed.")
    changes: list[str] = Field(default_factory=list, description="What the import changes, e.g. 'MRP 100 → 120'.")
    issues: list[ItemImportIssue] = Field(default_factory=list)


class ItemImportSummary(ApiModel):
    file_name: str
    total: int
    creates: int
    updates: int
    unchanged: int
    skips: int
    duplicates: int = Field(description="Rows repeating a part already in the file, or matching several items.")
    missing_hsn: int = Field(description="Rows without an HSN code ('Not assigned' or blank).")
    unknown_hsn: int = Field(description="Rows whose HSN code is not in the HSN master.")
    no_price: int = Field(description="Rows with a zero or blank price (the price is left as it is).")


class ItemImportPreview(ApiModel):
    summary: ItemImportSummary
    rows: list[ItemImportRow]


class ItemImportResult(ItemImportPreview):
    pass
