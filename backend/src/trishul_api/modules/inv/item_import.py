"""Import a spare-part price file (.xlsx) into the item master.

Columns: Sl No, External ID (S4H), Material, Description, HSN Code, ZAmount. External ID is the part number as
SAP S/4HANA stores it (zero-padded, e.g. 0000534); Material is the plain number (534). Both are read as text.

* A row matches an existing item of the brand (or a common item) by OEM part number = External ID, else by
  item code = External ID. New parts become items with that External ID as the item code and OEM part number.
* The price (ZAmount) is stored as the MRP or the standard cost; a zero or blank price never overwrites one.
* The HSN code is looked up in core.hsn_sac and only fills an item that has none.
* Checked and reported per row: parts repeated in the file (the first one wins), parts matching several
  items, missing or unknown HSN codes, zero prices.

preview() is a dry run; apply() writes the same plan in one transaction.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from io import BytesIO
from itertools import islice
from typing import Any

from openpyxl import load_workbook
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from trishul_api.auth import CurrentUser, RequestScope
from trishul_api.common.errors import ApiError
from trishul_api.db.models import HsnSac, Item, ItemCategory, Uom
from trishul_api.modules.inv.common import default_company, now
from trishul_api.modules.inv.item_import_schemas import (
    ImportAction,
    ItemImportIssue,
    ItemImportPreview,
    ItemImportResult,
    ItemImportRow,
    ItemImportSummary,
    PriceField,
)

_MAX_ROWS = 20000
_MAX_HEADER_SCAN = 15
_CHUNK = 500  # SQL Server allows about 2100 parameters per statement
_NOT_ASSIGNED = {"", "not assigned", "n/a", "na", "-", "none"}


@dataclass
class FileRow:
    row_number: int
    external_id: str | None
    material: str | None
    description: str | None
    hsn_code: str | None
    price: Decimal | None
    price_text: str | None = None  # set when the price cell is not a number


@dataclass
class Planned:
    row: FileRow
    action: ImportAction
    item: Item | None = None
    hsn_id: int | None = None
    new_price: Decimal | None = None
    changes: list[str] = field(default_factory=list)
    issues: list[ItemImportIssue] = field(default_factory=list)


def _text(cell: Any) -> str | None:
    """Part numbers are text; a number cell has lost any leading zeros already, so write it out whole."""
    if cell is None:
        return None
    if isinstance(cell, float) and cell.is_integer():
        cell = int(cell)
    text = str(cell).strip()
    return text or None


def _key(value: str | None) -> str | None:
    """0000534 and 534 are the same part."""
    if not value:
        return None
    return value.upper().lstrip("0") or "0"


def parse_price_file(content: bytes) -> list[FileRow]:
    try:
        workbook = load_workbook(BytesIO(content), read_only=True, data_only=True)
    except Exception as exc:  # openpyxl raises a grab-bag of errors on a bad file
        raise ApiError("That file could not be read as an Excel (.xlsx) workbook.") from exc
    try:
        grid = list(islice(workbook.worksheets[0].iter_rows(values_only=True), _MAX_ROWS + _MAX_HEADER_SCAN))
    finally:
        workbook.close()

    header_index, columns = _find_header(grid)
    rows: list[FileRow] = []
    for offset, raw in enumerate(grid[header_index + 1 :]):
        if raw is None or not any(cell not in (None, "") for cell in raw):
            continue

        def cell(name: str, raw: tuple[Any, ...] = raw) -> Any:
            index = columns.get(name)
            return raw[index] if index is not None and index < len(raw) else None

        price, price_text = _price(cell("price"))
        rows.append(
            FileRow(
                row_number=header_index + 2 + offset,
                external_id=_text(cell("external")),
                material=_text(cell("material")),
                description=_text(cell("description")),
                hsn_code=_hsn(cell("hsn")),
                price=price,
                price_text=price_text,
            )
        )
    if not rows:
        raise ApiError("The file has no item rows.")
    return rows


def _find_header(grid: list[tuple[Any, ...]]) -> tuple[int, dict[str, int]]:
    for index, raw in enumerate(grid[:_MAX_HEADER_SCAN]):
        if raw is None:
            continue
        columns: dict[str, int] = {}
        for position, cell in enumerate(raw):
            label = str(cell).strip().lower() if cell not in (None, "") else ""
            if label.startswith("external id"):
                columns.setdefault("external", position)
            elif label == "material":
                columns.setdefault("material", position)
            elif label == "description":
                columns.setdefault("description", position)
            elif label.startswith("hsn"):
                columns.setdefault("hsn", position)
            elif label in {"zamount", "price", "amount"}:
                columns.setdefault("price", position)
        if "external" in columns and "price" in columns:
            return index, columns
    raise ApiError(
        "This doesn't look like the item price file. It needs the columns External ID (S4H), Material, "
        "Description, HSN Code and ZAmount."
    )


def _hsn(cell: Any) -> str | None:
    text = _text(cell)
    return None if text is None or text.lower() in _NOT_ASSIGNED else text


def _price(cell: Any) -> tuple[Decimal | None, str | None]:
    """(price, None) or (None, the text that is not a number); blank is (None, None)."""
    if cell is None or (isinstance(cell, str) and not cell.strip()):
        return None, None
    try:
        value = Decimal(str(cell).replace(",", "").strip())
    except InvalidOperation:
        return None, str(cell)
    return (value, None) if value.is_finite() and value >= 0 else (None, str(cell))


class ItemImportService:
    def __init__(self, db: Session, actor: CurrentUser) -> None:
        self._db = db
        self._actor = actor

    # ------------------------------------------------------------------ public

    def preview(
        self,
        content: bytes,
        file_name: str,
        scope: RequestScope,
        category_id: int | None,
        uom_id: int | None,
        price_field: PriceField,
    ) -> ItemImportPreview:
        plan = self._plan(content, scope, category_id, uom_id, price_field)
        return ItemImportPreview(summary=_summary(file_name, plan), rows=[_out(p) for p in plan])

    def apply(
        self,
        content: bytes,
        file_name: str,
        scope: RequestScope,
        category_id: int | None,
        uom_id: int | None,
        price_field: PriceField,
    ) -> ItemImportResult:
        plan = self._plan(content, scope, category_id, uom_id, price_field)
        company_id = default_company(self._db, self._actor, scope)
        category, unit_id = self._category_and_unit(category_id, uom_id, needed=any(p.action == "Create" for p in plan))
        stamp = now()
        column = "mrp" if price_field == "mrp" else "standard_cost"
        for p in plan:
            if p.action == "Create":
                assert category is not None and unit_id is not None
                self._db.add(
                    Item(
                        company_id=company_id,
                        item_code=(p.row.external_id or "")[:40].upper(),
                        principal_id=scope.principal_id,
                        oem_part_number=(p.row.external_id or "")[:40],
                        description=(p.row.description or p.row.external_id or "")[:200],
                        category_id=category.id,
                        uom_id=unit_id,
                        hsn_sac_id=p.hsn_id,
                        item_type="Stock",
                        is_serialized=False,
                        is_batch_tracked=False,
                        created_by_user_id=self._actor.id,
                        **{column: p.new_price},
                    )
                )
            elif p.action == "Update" and p.item is not None:
                if p.new_price is not None:
                    setattr(p.item, column, p.new_price)
                if p.hsn_id is not None and p.item.hsn_sac_id is None:
                    p.item.hsn_sac_id = p.hsn_id
                p.item.updated_at = stamp
                p.item.updated_by_user_id = self._actor.id
        self._db.commit()
        return ItemImportResult(summary=_summary(file_name, plan), rows=[_out(p) for p in plan])

    # ------------------------------------------------------------------ planning

    def _plan(
        self,
        content: bytes,
        scope: RequestScope,
        category_id: int | None,
        uom_id: int | None,
        price_field: PriceField,
    ) -> list[Planned]:
        if scope.principal_id is None:
            raise ApiError("Select a brand first: the items are created and matched within that brand.")
        rows = parse_price_file(content)
        company_id = default_company(self._db, self._actor, scope)
        existing = self._existing(company_id, scope.principal_id, rows)
        hsn_ids = self._hsn_ids({r.hsn_code for r in rows if r.hsn_code})
        plan = [self._plan_row(row, existing, hsn_ids, price_field) for row in rows]
        _mark_duplicates(plan)
        if any(p.action == "Create" for p in plan):
            self._category_and_unit(category_id, uom_id, needed=True)  # fail the preview, not just the import
        return plan

    def _plan_row(
        self, row: FileRow, existing: dict[str, list[Item]], hsn_ids: dict[str, int], price_field: PriceField
    ) -> Planned:
        p = Planned(row=row, action="Skip")
        if not row.external_id:
            p.issues.append(ItemImportIssue(code="invalid", message="No External ID on this row."))
            return p
        if row.price_text is not None:
            p.issues.append(ItemImportIssue(code="invalid", message=f"'{row.price_text}' is not a valid price."))
            return p

        matches = existing.get(_key(row.external_id) or "", [])
        if len(matches) > 1:
            codes = ", ".join(sorted(m.item_code for m in matches))
            p.issues.append(ItemImportIssue(code="ambiguous", message=f"Matches several items ({codes}); skipped."))
            return p
        item = matches[0] if matches else None

        if row.hsn_code is None:
            p.issues.append(ItemImportIssue(code="missingHsn", message="No HSN code in the file."))
        elif row.hsn_code in hsn_ids:
            p.hsn_id = hsn_ids[row.hsn_code]
        else:
            p.issues.append(ItemImportIssue(code="unknownHsn", message=f"HSN {row.hsn_code} is not in the HSN master."))

        has_price = row.price is not None and row.price > 0
        if not has_price:
            p.issues.append(ItemImportIssue(code="noPrice", message="Zero or blank price; the price is left as it is."))

        label = "MRP" if price_field == "mrp" else "Standard cost"
        if item is None:
            p.action = "Create"
            p.new_price = row.price if has_price else None
            p.changes.append("New item" + (f", {label} {_money(row.price)}" if has_price else ""))
            return p

        p.item = item
        current = item.mrp if price_field == "mrp" else item.standard_cost
        if has_price and row.price is not None and (current is None or Decimal(current) != row.price):
            p.new_price = row.price
            p.changes.append(f"{label} {_money(current)} → {_money(row.price)}")
        if p.hsn_id is not None and item.hsn_sac_id is None:
            p.changes.append(f"HSN {row.hsn_code} added")
        else:
            p.hsn_id = None  # never replace an HSN the item already has
        p.action = "Update" if p.changes else "Unchanged"
        return p

    def _existing(self, company_id: int, principal_id: int, rows: list[FileRow]) -> dict[str, list[Item]]:
        """Items of the brand (or common items) for the part numbers in the file, by part-number key."""
        wanted = sorted({r.external_id for r in rows if r.external_id})
        found: dict[str, list[Item]] = {}
        seen: set[int] = set()
        for start in range(0, len(wanted), _CHUNK):
            chunk = wanted[start : start + _CHUNK]
            items = self._db.scalars(
                select(Item).where(
                    Item.company_id == company_id,
                    or_(Item.principal_id == principal_id, Item.principal_id.is_(None)),
                    or_(Item.oem_part_number.in_(chunk), Item.item_code.in_(chunk)),
                )
            ).all()
            for item in items:
                if item.id in seen:
                    continue
                seen.add(item.id)
                for number in {item.oem_part_number, item.item_code}:
                    key = _key(number)
                    if key and number in chunk:
                        found.setdefault(key, []).append(item)
        return found

    def _hsn_ids(self, codes: set[str]) -> dict[str, int]:
        ids: dict[str, int] = {}
        ordered = sorted(codes)
        for start in range(0, len(ordered), _CHUNK):
            rows = self._db.execute(
                select(HsnSac.id, HsnSac.code).where(HsnSac.code.in_(ordered[start : start + _CHUNK]))
            ).all()
            for hsn_id, code in rows:
                ids[code] = hsn_id
        return ids

    def _category_and_unit(
        self, category_id: int | None, uom_id: int | None, *, needed: bool
    ) -> tuple[ItemCategory | None, int | None]:
        if not needed:
            return None, None
        if category_id is None:
            raise ApiError(
                "Choose the category for the new items.", errors={"categoryId": ["Pick a category above."]}
            )
        category = self._db.get(ItemCategory, category_id)
        if category is None or not category.is_active:
            raise ApiError("Choose an active category.", errors={"categoryId": [f"Unknown category {category_id}."]})
        unit_id = uom_id or category.default_uom_id
        if unit_id is None:
            raise ApiError(
                "Choose the stock unit for the new items.",
                errors={"uomId": ["Required (the category has no default unit)."]},
            )
        unit = self._db.get(Uom, unit_id)
        if unit is None or not unit.is_active:
            raise ApiError("Choose an active unit.", errors={"uomId": [f"Unknown or inactive unit {unit_id}."]})
        return category, unit_id


# ---------------------------------------------------------------------- helpers


def _mark_duplicates(plan: list[Planned]) -> None:
    """The first row of a part wins; a repeat (also 534 after 0000534) is skipped and reported."""
    first: dict[str, int] = {}
    for p in plan:
        key = _key(p.row.external_id) or _key(p.row.material)
        if key is None or any(i.code in ("invalid", "ambiguous") for i in p.issues):
            continue
        if key in first:
            p.action = "Skip"
            p.item = None
            p.changes = []
            p.issues = [i for i in p.issues if i.code not in ("missingHsn", "unknownHsn", "noPrice")]
            p.issues.append(ItemImportIssue(code="duplicateInFile", message=f"Same part as row {first[key]}; skipped."))
        else:
            first[key] = p.row.row_number


def _money(value: Decimal | None) -> str:
    return "none" if value is None else f"{Decimal(value):,.2f}"


def _out(p: Planned) -> ItemImportRow:
    code = p.item.item_code if p.item is not None else (p.row.external_id or "").upper() or None
    return ItemImportRow(
        row_number=p.row.row_number,
        external_id=p.row.external_id,
        material=p.row.material,
        description=p.row.description,
        hsn_code=p.row.hsn_code,
        price=p.row.price,
        action=p.action,
        item_code=code if p.action != "Skip" else None,
        changes=p.changes,
        issues=p.issues,
    )


def _summary(file_name: str, plan: list[Planned]) -> ItemImportSummary:
    def count(action: ImportAction) -> int:
        return sum(1 for p in plan if p.action == action)

    def issues(*codes: str) -> int:
        return sum(1 for p in plan if any(i.code in codes for i in p.issues))

    return ItemImportSummary(
        file_name=file_name,
        total=len(plan),
        creates=count("Create"),
        updates=count("Update"),
        unchanged=count("Unchanged"),
        skips=count("Skip"),
        duplicates=issues("duplicateInFile", "ambiguous"),
        missing_hsn=issues("missingHsn"),
        unknown_hsn=issues("unknownHsn"),
        no_price=issues("noPrice"),
    )
