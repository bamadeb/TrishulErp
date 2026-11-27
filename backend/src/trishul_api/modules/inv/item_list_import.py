"""Item list import: create items in bulk from an Excel (.xlsx, .xls) or CSV file, with a history of every upload.

Flow:
  1. upload()   stores the file, reads and checks every row and saves the result as a batch (status Pending)
                with one line per row. The item master is not touched.
  2. confirm()  only the uploader, only a Pending batch. The batch goes to Processing, the stored file is
                checked again against the masters as they are now, and every valid row is written in ONE
                transaction: a database error rolls all of it back and the batch becomes Failed, so a
                failure never leaves half an import behind. Otherwise Completed / Partially Completed.

Rules:
  * Item codes are unique: a row whose code is already used is skipped. With duplicate mode "Update" and the
    permission inv.item.import.overwrite, the existing item is updated instead, but only from cells that have
    a value (a blank cell never clears a field), and never its brand, unit, item type or tracking flags.
  * A row repeating an item code (or a brand + OEM part number) of an earlier row is skipped.
  * A row whose brand + OEM part number belongs to an existing item with another code is skipped.
  * Category, unit, brand and HSN/SAC must be active masters; the brand must be one the user may see.
  * Items are written through the ORM, so core.audit_log records each creation and change with the user.
"""

from __future__ import annotations

import csv
import io
import json
import re
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, time, timedelta, timezone
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from itertools import islice
from pathlib import Path
from typing import Any

from openpyxl import Workbook, load_workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.datavalidation import DataValidation
from sqlalchemy import Select, case, delete, func, insert, or_, select, update
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from trishul_api.auth import CurrentUser, RequestScope
from trishul_api.common.errors import ApiError, Conflict, NotFound
from trishul_api.common.paging import SortColumns, order_by_sort, paginate
from trishul_api.common.schemas import Page
from trishul_api.db.models import (
    AppUser,
    Employee,
    HsnSac,
    Item,
    ItemCategory,
    ItemImport,
    ItemImportLine,
    Principal,
    Uom,
)
from trishul_api.db.models.item_import import ItemImportDuplicateMode, ItemImportLineAction
from trishul_api.modules.core.documents import storage
from trishul_api.modules.inv.common import default_company, now
from trishul_api.modules.inv.item_list_import_schemas import (
    ItemImportBatch,
    ItemImportFieldChange,
    ItemImportLineOut,
    ItemImportLineQuery,
    ItemImportQuery,
    ItemImportUploader,
)

ITEM_IMPORT = "inv.item.import"
ITEM_IMPORT_VIEW = "inv.item.import.view"
ITEM_IMPORT_OVERWRITE = "inv.item.import.overwrite"

MAX_ROWS = 10_000
MAX_BYTES = 10 * 1024 * 1024
_HEADER_SCAN = 10
_CHUNK = 500  # SQL Server allows about 2100 parameters per statement
_IST = timezone(timedelta(hours=5, minutes=30))
_CODE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_./ -]*$")
_TYPES = {"stock": "Stock", "nonstock": "Non stock", "service": "Service"}
_YES = {"y", "yes", "true", "1"}
_NO = {"n", "no", "false", "0"}
_EXTENSIONS = {
    ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    ".xls": "application/vnd.ms-excel",
    ".csv": "text/csv",
}
XLSX = _EXTENSIONS[".xlsx"]


@dataclass(frozen=True)
class Column:
    key: str
    label: str
    required: bool = False
    aliases: tuple[str, ...] = ()
    note: str = ""


COLUMNS: tuple[Column, ...] = (
    Column("item_code", "Item Code", True, (), "Unique code, up to 40 letters/digits (also - _ . / and space)."),
    Column("description", "Description", True, (), "Short description, up to 200 characters."),
    Column("category", "Category Code", True, ("category",), "Code of an active category or subcategory."),
    Column("item_type", "Item Type", False, ("type",), "Stock, Non stock or Service. Blank = Stock."),
    Column("uom", "UOM Code", False, ("uom", "unit", "unitcode", "stockunit"), "Blank = the category's default unit."),
    Column("brand", "Brand Code", False, ("brand", "principal", "principalcode"), "Blank = a common item (no brand)."),
    Column("oem", "OEM Part Number", False, ("oempartno", "partnumber", "partno"), "Up to 40 characters."),
    Column("long_description", "Long Description", False, (), "Up to 1000 characters."),
    Column("hsn", "HSN/SAC Code", False, ("hsnsac", "hsncode", "hsn", "saccode"), "Blank = the category's default."),
    Column("serialized", "Serialized (Y/N)", False, ("isserialized",), "Y or N. Blank = N."),
    Column("batch", "Batch Tracked (Y/N)", False, ("isbatchtracked", "batch"), "Y or N. Blank = N."),
    Column("standard_cost", "Standard Cost", False, (), "Number, 0 or more."),
    Column("mrp", "MRP", False, (), "Number, 0 or more (2 decimals)."),
    Column("reorder_level", "Reorder Level", False, (), "Quantity, 0 or more."),
    Column("reorder_qty", "Reorder Qty", False, ("reorderquantity",), "Quantity, 0 or more."),
    Column("lead_time", "Lead Time (Days)", False, ("leadtime", "leadtimedays"), "Whole days, 0 to 999."),
    Column("active", "Active (Y/N)", False, ("isactive",), "Y or N. Blank = Y."),
)
_BY_KEY = {c.key: c for c in COLUMNS}


def _norm(label: Any) -> str:
    """'Serialized (Y/N)*' -> 'serialized'; 'HSN/SAC Code' -> 'hsnsaccode'."""
    text = re.sub(r"\(.*?\)", "", str(label or "")).lower()
    return re.sub(r"[^a-z0-9]", "", text)


_HEADER_NAMES: dict[str, str] = {}
for _column in COLUMNS:
    for _name in (_norm(_column.label), *_column.aliases):
        _HEADER_NAMES.setdefault(_name, _column.key)


# ---------------------------------------------------------------------- reading the file


@dataclass
class FileRow:
    row_number: int
    values: dict[str, str | None]  # column key -> cell text
    source: dict[str, str | None]  # file header -> cell text, for the error report


def check_upload(file_name: str, raw: bytes) -> str:
    """The extension of an acceptable upload, or a 400."""
    extension = Path(file_name).suffix.lower()
    if extension not in _EXTENSIONS:
        raise ApiError("Upload an Excel (.xlsx, .xls) or CSV (.csv) file.")
    if not raw:
        raise ApiError("The uploaded file is empty.")
    if len(raw) > MAX_BYTES:
        raise ApiError("The file must be 10 MB or smaller.")
    if extension == ".csv":
        if b"\x00" in raw[:4096]:
            raise ApiError("The file content is not a valid CSV file.")
    else:
        storage.validate_file(file_name, raw)  # real Excel content, no macros, no zip bomb
    return extension


def read_rows(extension: str, raw: bytes) -> list[FileRow]:
    grid = _grid(extension, raw)
    header_index, columns, labels = _header(grid)
    rows: list[FileRow] = []
    for offset, cells in enumerate(grid[header_index + 1 :]):
        if not any(_text(c) for c in cells):
            continue
        if len(rows) >= MAX_ROWS:
            raise ApiError(f"The file has more than {MAX_ROWS:,} item rows. Split it into smaller files.")
        values = {key: _text(cells[i]) if i < len(cells) else None for key, i in columns.items()}
        source = {label: _text(cells[i]) if i < len(cells) else None for i, label in labels.items()}
        rows.append(FileRow(row_number=header_index + 2 + offset, values=values, source=source))
    if not rows:
        raise ApiError("The file has no item rows under the header row.")
    return rows


def _grid(extension: str, raw: bytes) -> list[list[Any]]:
    limit = MAX_ROWS + _HEADER_SCAN + 1000  # some room for blank rows
    if extension == ".csv":
        text = _decode(raw)
        try:
            dialect: Any = csv.Sniffer().sniff(text[:4096], delimiters=",;\t")
        except csv.Error:
            dialect = csv.excel
        return [list(r) for r in islice(csv.reader(io.StringIO(text), dialect), limit)]
    if extension == ".xls":
        import xlrd  # type: ignore[import-untyped]

        try:
            book = xlrd.open_workbook(file_contents=raw, on_demand=True)
        except Exception as exc:  # xlrd raises several error types on a bad file
            raise ApiError("That file could not be read as an Excel (.xls) workbook.") from exc
        try:
            names = [n.lower() for n in book.sheet_names()]
            sheet = book.sheet_by_index(names.index("items") if "items" in names else 0)
            return [sheet.row_values(r) for r in range(min(sheet.nrows, limit))]
        finally:
            book.release_resources()
    try:
        workbook = load_workbook(io.BytesIO(raw), read_only=True, data_only=True)
    except Exception as exc:  # openpyxl raises a grab-bag of errors on a bad file
        raise ApiError("That file could not be read as an Excel (.xlsx) workbook.") from exc
    try:
        sheet = workbook["Items"] if "Items" in workbook.sheetnames else workbook.worksheets[0]
        return [list(r) for r in islice(sheet.iter_rows(values_only=True), limit)]
    finally:
        workbook.close()


def _decode(raw: bytes) -> str:
    for encoding in ("utf-8-sig", "cp1252"):
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            continue
    raise ApiError("The CSV file's text could not be read. Save it as CSV UTF-8.")


def _header(grid: list[list[Any]]) -> tuple[int, dict[str, int], dict[int, str]]:
    for index, cells in enumerate(grid[:_HEADER_SCAN]):
        columns: dict[str, int] = {}
        labels: dict[int, str] = {}
        for position, cell in enumerate(cells):
            label = _text(cell)
            if not label:
                continue
            labels[position] = label.rstrip(" *")
            key = _HEADER_NAMES.get(_norm(label))
            if key:
                columns.setdefault(key, position)
        if "item_code" in columns:
            missing = [c.label for c in COLUMNS if c.required and c.key not in columns]
            if missing:
                raise ApiError(f"The file is missing the required column(s): {', '.join(missing)}.")
            return index, columns, labels
    raise ApiError("No header row with an 'Item Code' column was found in the first rows. Use the sample template.")


def _text(cell: Any) -> str | None:
    if cell is None:
        return None
    if isinstance(cell, bool):
        return "Y" if cell else "N"
    if isinstance(cell, float) and cell.is_integer():
        cell = int(cell)
    text = str(cell).strip()
    return text or None


# ---------------------------------------------------------------------- planning


@dataclass
class Masters:
    categories: dict[str, ItemCategory]
    uoms: dict[str, Uom]
    uom_codes: dict[int, str]
    principals: dict[str, Principal]
    hsn: dict[str, HsnSac]
    hsn_codes: dict[int, str]
    category_codes: dict[int, str]


@dataclass
class Planned:
    row: FileRow
    action: ItemImportLineAction = "Create"
    messages: list[str] = field(default_factory=list)
    item_code: str | None = None
    fields: dict[str, Any] = field(default_factory=dict)  # Item column -> value, for a new item
    given: set[str] = field(default_factory=set)  # Item columns that had a value in the file
    existing: Item | None = None
    changes: list[dict[str, str | None]] = field(default_factory=list)

    def error(self, message: str) -> None:
        self.action = "Error"
        self.messages.append(message)

    def skip(self, message: str) -> None:
        self.action = "Skip"
        self.messages.append(message)


def _plan_rows(db: Session, actor: CurrentUser, rows: list[FileRow], mode: ItemImportDuplicateMode) -> list[Planned]:
    masters = _masters(db)
    plan = [_check_row(row, masters, actor) for row in rows]
    _mark_repeats(plan)
    _match_existing(db, actor, plan, masters, mode)
    return plan


def _masters(db: Session) -> Masters:
    categories = db.scalars(select(ItemCategory)).all()
    uoms = db.scalars(select(Uom)).all()
    principals = db.scalars(select(Principal)).all()
    hsn = db.scalars(select(HsnSac)).all()
    by_principal: dict[str, Principal] = {}
    for p in principals:
        by_principal.setdefault(p.code.upper(), p)
    for p in principals:
        by_principal.setdefault(p.name.upper(), p)
    return Masters(
        categories={c.code.upper(): c for c in categories},
        uoms={u.code.upper(): u for u in uoms},
        uom_codes={u.id: u.code for u in uoms},
        principals=by_principal,
        hsn={h.code.upper(): h for h in hsn},
        hsn_codes={h.id: h.code for h in hsn},
        category_codes={c.id: c.code for c in categories},
    )


def _check_row(row: FileRow, m: Masters, actor: CurrentUser) -> Planned:
    v = row.values
    p = Planned(row=row)
    given = {k for k, value in v.items() if value is not None}

    code = (v.get("item_code") or "").upper()
    if not code:
        p.error("Item Code is required.")
    elif len(code) > 40:
        p.error("Item Code is longer than 40 characters.")
    elif not _CODE.match(code):
        p.error("Item Code may only have letters, digits, space and - _ . / (and must start with a letter or digit).")
    p.item_code = code or None

    description = v.get("description")
    if not description:
        p.error("Description is required.")
    elif len(description) > 200:
        p.error("Description is longer than 200 characters.")

    category: ItemCategory | None = None
    category_code = v.get("category")
    if not category_code:
        p.error("Category Code is required.")
    else:
        category = m.categories.get(category_code.upper())
        if category is None:
            p.error(f"Category '{category_code}' does not exist.")
        elif not category.is_active:
            p.error(f"Category '{category_code}' is inactive.")
            category = None

    item_type = "Stock"
    type_text = v.get("item_type")
    if type_text:
        found_type = _TYPES.get(_norm(type_text))
        if found_type is None:
            p.error(f"Item Type '{type_text}' is not valid (use Stock, Non stock or Service).")
        else:
            item_type = found_type

    uom_id: int | None = None
    uom_code = v.get("uom")
    if uom_code:
        unit = m.uoms.get(uom_code.upper())
        if unit is None:
            p.error(f"UOM '{uom_code}' does not exist.")
        elif not unit.is_active:
            p.error(f"UOM '{uom_code}' is inactive.")
        else:
            uom_id = unit.id
    elif category is not None:
        uom_id = category.default_uom_id
        if uom_id is None:
            p.error(f"UOM Code is required: category '{category.code}' has no default unit.")

    principal_id: int | None = None
    brand = v.get("brand")
    if brand:
        principal = m.principals.get(brand.upper())
        if principal is None:
            p.error(f"Brand '{brand}' does not exist.")
        elif not principal.is_active:
            p.error(f"Brand '{brand}' is inactive.")
        elif not actor.can_see_principal(principal.id):
            p.error(f"You do not have access to brand '{brand}'.")
        else:
            principal_id = principal.id

    hsn_id: int | None = category.default_hsn_sac_id if category is not None else None
    hsn_code = v.get("hsn")
    if hsn_code:
        hsn = m.hsn.get(hsn_code.upper())
        if hsn is None:
            p.error(f"HSN/SAC '{hsn_code}' is not in the HSN/SAC master.")
        elif not hsn.is_active:
            p.error(f"HSN/SAC '{hsn_code}' is inactive.")
        else:
            hsn_id = hsn.id

    oem = v.get("oem")
    if oem and len(oem) > 40:
        p.error("OEM Part Number is longer than 40 characters.")
    long_description = v.get("long_description")
    if long_description and len(long_description) > 1000:
        p.error("Long Description is longer than 1000 characters.")

    flags = {name: _yes_no(p, name, v.get(name)) for name in ("serialized", "batch", "active")}
    numbers = {
        "standard_cost": _number(p, "standard_cost", v.get("standard_cost"), 4),
        "mrp": _number(p, "mrp", v.get("mrp"), 2),
        "reorder_level": _number(p, "reorder_level", v.get("reorder_level"), 3),
        "reorder_qty": _number(p, "reorder_qty", v.get("reorder_qty"), 3),
    }
    lead_time = _number(p, "lead_time", v.get("lead_time"), 0)
    if lead_time is not None and lead_time > 999:
        p.error("Lead Time (Days) must be 999 or less.")

    p.fields = {
        "item_code": code,
        "description": description,
        "long_description": long_description,
        "oem_part_number": oem,
        "category_id": category.id if category else None,
        "uom_id": uom_id,
        "principal_id": principal_id,
        "hsn_sac_id": hsn_id,
        "item_type": item_type,
        "is_serialized": bool(flags["serialized"]),
        "is_batch_tracked": bool(flags["batch"]),
        "is_active": flags["active"] is not False,
        "lead_time_days": int(lead_time) if lead_time is not None else None,
        **numbers,
    }
    column_of = {
        "description": "description", "long_description": "long_description", "oem": "oem_part_number",
        "category": "category_id", "uom": "uom_id", "brand": "principal_id", "hsn": "hsn_sac_id",
        "item_type": "item_type", "serialized": "is_serialized", "batch": "is_batch_tracked", "active": "is_active",
        "standard_cost": "standard_cost", "mrp": "mrp", "reorder_level": "reorder_level",
        "reorder_qty": "reorder_qty", "lead_time": "lead_time_days",
    }  # fmt: skip
    p.given = {column_of[k] for k in given if k in column_of}
    return p


def _yes_no(p: Planned, key: str, value: str | None) -> bool | None:
    if value is None:
        return None
    lowered = value.strip().lower()
    if lowered in _YES:
        return True
    if lowered in _NO:
        return False
    p.error(f"{_BY_KEY[key].label} must be Y or N, not '{value}'.")
    return None


def _number(p: Planned, key: str, value: str | None, places: int) -> Decimal | None:
    if value is None:
        return None
    label = _BY_KEY[key].label
    try:
        number = Decimal(value.replace(",", ""))
    except InvalidOperation:
        p.error(f"{label} '{value}' is not a number.")
        return None
    if not number.is_finite():
        p.error(f"{label} '{value}' is not a number.")
        return None
    if number < 0:
        p.error(f"{label} cannot be negative.")
        return None
    if places == 0 and number != number.to_integral_value():
        p.error(f"{label} must be a whole number.")
        return None
    number = number.quantize(Decimal(1).scaleb(-places), rounding=ROUND_HALF_UP)
    if number.adjusted() >= 14:  # every column holds at least 14 digits before the decimal point
        p.error(f"{label} is too large.")
        return None
    return number


def _mark_repeats(plan: list[Planned]) -> None:
    """The first row of an item code (or of a brand + OEM part number) wins; later rows are skipped."""
    by_code: dict[str, int] = {}
    by_part: dict[tuple[int | None, str], int] = {}
    for p in plan:
        if p.action == "Error":
            continue
        code = p.item_code or ""
        part = p.fields.get("oem_part_number")
        part_key = (p.fields.get("principal_id"), part.upper()) if part else None
        if code in by_code:
            p.skip(f"Duplicate in the file: same Item Code as row {by_code[code]}.")
        elif part_key is not None and part_key in by_part:
            p.skip(f"Duplicate in the file: same brand and OEM Part Number as row {by_part[part_key]}.")
        else:
            by_code[code] = p.row.row_number
            if part_key is not None:
                by_part[part_key] = p.row.row_number


def _match_existing(
    db: Session, actor: CurrentUser, plan: list[Planned], m: Masters, mode: ItemImportDuplicateMode
) -> None:
    candidates = [p for p in plan if p.action == "Create"]
    codes = sorted({p.item_code for p in candidates if p.item_code})
    by_code: dict[str, Item] = {}
    for start in range(0, len(codes), _CHUNK):
        for found in db.scalars(select(Item).where(Item.item_code.in_(codes[start : start + _CHUNK]))):
            by_code[found.item_code.upper()] = found
    parts = sorted({p.fields["oem_part_number"] for p in candidates if p.fields.get("oem_part_number")})
    by_part: dict[tuple[int | None, str], Item] = {}
    for start in range(0, len(parts), _CHUNK):
        for found in db.scalars(select(Item).where(Item.oem_part_number.in_(parts[start : start + _CHUNK]))):
            if found.oem_part_number:
                by_part.setdefault((found.principal_id, found.oem_part_number.upper()), found)

    overwrite = mode == "Update" and actor.can(ITEM_IMPORT_OVERWRITE)
    for p in candidates:
        item: Item | None = by_code.get(p.item_code or "")
        if item is None:
            part = p.fields.get("oem_part_number")
            other = by_part.get((p.fields.get("principal_id"), part.upper())) if part else None
            if other is not None:
                p.skip(f"Already exists: item {other.item_code} has this brand and OEM Part Number.")
            continue
        if item.principal_id is not None and not actor.can_see_principal(item.principal_id):
            p.error(f"Item Code {item.item_code} is used by an item of a brand you do not have access to.")
            continue
        p.existing = item
        if not overwrite:
            p.skip(f"Already exists: item {item.item_code} is in the item master.")
            continue
        _plan_update(p, item, m)


def _plan_update(p: Planned, item: Item, m: Masters) -> None:
    if item.principal_id != p.fields["principal_id"]:
        p.error(f"Item {item.item_code} belongs to another brand; an import cannot change an item's brand.")
        return
    labels = {
        "description": "Description", "long_description": "Long Description", "oem_part_number": "OEM Part Number",
        "category_id": "Category", "hsn_sac_id": "HSN/SAC", "standard_cost": "Standard Cost", "mrp": "MRP",
        "reorder_level": "Reorder Level", "reorder_qty": "Reorder Qty", "lead_time_days": "Lead Time (Days)",
        "is_active": "Active",
    }  # fmt: skip
    for column, label in labels.items():
        if column not in p.given:
            continue  # a blank cell never clears a field
        old, new = getattr(item, column), p.fields[column]
        if _same(old, new):
            continue
        p.changes.append({"field": label, "from": _show(column, old, m), "to": _show(column, new, m)})
    locked = {
        "uom_id": "UOM",
        "item_type": "Item Type",
        "is_serialized": "Serialized",
        "is_batch_tracked": "Batch Tracked",
    }
    for column, label in locked.items():
        if column in p.given and not _same(getattr(item, column), p.fields[column]):
            p.messages.append(f"{label} differs from the item master and is not changed by an import.")
    if p.changes:
        p.action = "Update"
    else:
        p.skip(f"Already exists: item {item.item_code} has these values already.")


def _same(old: Any, new: Any) -> bool:
    if isinstance(old, (int, float, Decimal)) and isinstance(new, Decimal) and not isinstance(old, bool):
        return Decimal(str(old)) == new
    return bool(old == new)


def _show(column: str, value: Any, m: Masters) -> str | None:
    if value is None:
        return None
    if column == "category_id":
        return str(m.category_codes.get(value, value))
    if column == "hsn_sac_id":
        return str(m.hsn_codes.get(value, value))
    if isinstance(value, bool):
        return "Y" if value else "N"
    if isinstance(value, Decimal):
        return f"{value.normalize():f}"
    return str(value)


# ---------------------------------------------------------------------- the service


class ItemListImportService:
    def __init__(self, db: Session, actor: CurrentUser) -> None:
        self._db = db
        self._actor = actor

    # ------------------------------------------------------------------ upload and confirm

    def upload(self, file_name: str, raw: bytes, mode: ItemImportDuplicateMode, scope: RequestScope) -> ItemImportBatch:
        name = storage.clean_file_name(file_name)
        extension = check_upload(name, raw)
        if mode == "Update" and not self._actor.can(ITEM_IMPORT_OVERWRITE):
            raise ApiError(
                "You are not allowed to update existing items from an import.",
                errors={"duplicateMode": ["Only 'Skip' is allowed for you."]},
            )
        batch = ItemImport(
            company_id=default_company(self._db, self._actor, scope),
            file_name=name,
            file_size=len(raw),
            duplicate_mode=mode,
            status="Pending",
            uploaded_by_user_id=self._actor.id,
            uploaded_at=now(),
        )
        self._db.add(batch)
        self._db.flush()
        batch.batch_no = f"IMP-{batch.id:06d}"
        batch.file_key = storage.store("item_import", batch.id, name, raw)
        try:
            plan = _plan_rows(self._db, self._actor, read_rows(extension, raw), mode)
        except ApiError as error:
            batch.status = "Failed"
            batch.error_message = (error.detail or "The file could not be read.")[:1000]
            batch.completed_at = now()
            self._db.commit()
            return self.get(batch.id)
        self._write_lines(batch, plan, done=False)
        if batch.valid_count == 0:
            batch.status = "Failed"
            batch.error_message = "No row can be imported. Download the error report for the reasons."
            batch.completed_at = now()
        self._db.commit()
        return self.get(batch.id)

    def confirm(self, import_id: int) -> ItemImportBatch:
        batch = self._batch(import_id)
        if batch.uploaded_by_user_id != self._actor.id:
            raise ApiError("Only the person who uploaded this file can confirm its import.")
        # Pending -> Processing, guarded so two confirmations of the same batch cannot both run.
        claimed = self._db.execute(  # type: ignore[attr-defined]
            update(ItemImport)
            .where(ItemImport.id == import_id, ItemImport.status == "Pending")
            .values(status="Processing", confirmed_by_user_id=self._actor.id)
        ).rowcount
        if not claimed:
            self._db.rollback()
            raise Conflict(f"This import is already {batch.status.lower()}; it can only be confirmed once.")
        self._db.commit()

        batch = self._batch(import_id)
        try:
            raw = storage.read(batch.file_key or "")
            if raw is None:
                raise ApiError("The uploaded file is no longer available. Upload it again.")
            extension = Path(batch.file_name).suffix.lower()
            plan = _plan_rows(self._db, self._actor, read_rows(extension, raw), batch.duplicate_mode)
            self._apply(batch, plan)
            self._db.commit()
        except (ApiError, SQLAlchemyError) as error:
            self._db.rollback()
            reason = (error.detail or "error") if isinstance(error, ApiError) else "a database error occurred"
            self._fail(import_id, f"Nothing was imported: {reason}. Fix the file or the masters and upload it again.")
            if isinstance(error, ApiError):
                raise
            raise ApiError(f"The import failed and nothing was saved ({type(error).__name__}).") from error
        return self.get(import_id)

    def _apply(self, batch: ItemImport, plan: list[Planned]) -> None:
        stamp = now()
        for p in plan:
            if p.action == "Create":
                item = Item(company_id=batch.company_id, created_by_user_id=self._actor.id, **p.fields)
                self._db.add(item)
                p.existing = item
            elif p.action == "Update" and p.existing is not None:
                for change_column in self._changed_columns(p):
                    setattr(p.existing, change_column, p.fields[change_column])
                p.existing.updated_at = stamp
                p.existing.updated_by_user_id = self._actor.id
        self._db.flush()  # item ids for the lines; a duplicate code here fails the whole import
        self._write_lines(batch, plan, done=True)
        imported = batch.created_count + batch.updated_count
        problems = batch.failed_count + batch.skipped_count
        if imported:
            batch.status = "Partially Completed" if problems else "Completed"
        else:
            batch.status = "Failed" if batch.failed_count else "Completed"
        if not imported and batch.failed_count:
            batch.error_message = "No row could be imported. Download the error report for the reasons."
        batch.completed_at = now()

    @staticmethod
    def _changed_columns(p: Planned) -> list[str]:
        updatable = (
            "description", "long_description", "oem_part_number", "category_id", "hsn_sac_id", "standard_cost",
            "mrp", "reorder_level", "reorder_qty", "lead_time_days", "is_active",
        )  # fmt: skip
        return [c for c in updatable if c in p.given]

    def _write_lines(self, batch: ItemImport, plan: list[Planned], *, done: bool) -> None:
        self._db.execute(delete(ItemImportLine).where(ItemImportLine.import_id == batch.id))
        outcome = {"Create": "Created", "Update": "Updated", "Skip": "Skipped", "Error": "Failed"}
        rows = [
            {
                "import_id": batch.id,
                "row_number": p.row.row_number,
                "item_code": (p.item_code or p.row.values.get("item_code") or "")[:60] or None,
                "description": (p.row.values.get("description") or "")[:200] or None,
                "action": p.action,
                "outcome": outcome[p.action] if done else None,
                "item_id": p.existing.id if p.existing is not None and p.action != "Error" else None,
                "messages": json.dumps(p.messages) if p.messages else None,
                "changes": json.dumps(p.changes) if p.changes else None,
                "source_data": json.dumps(p.row.source, ensure_ascii=False),
            }
            for p in plan
        ]
        for start in range(0, len(rows), _CHUNK):
            self._db.execute(insert(ItemImportLine), rows[start : start + _CHUNK])

        def count(action: str) -> int:
            return sum(1 for p in plan if p.action == action)

        batch.total_rows = len(plan)
        batch.valid_count = count("Create") + count("Update")
        batch.failed_count = count("Error")
        batch.skipped_count = count("Skip")
        batch.created_count = count("Create") if done else 0
        batch.updated_count = count("Update") if done else 0

    def _fail(self, import_id: int, message: str) -> None:
        self._db.execute(
            update(ItemImport)
            .where(ItemImport.id == import_id)
            .values(status="Failed", error_message=message[:1000], completed_at=now(), created_count=0, updated_count=0)
        )
        self._db.commit()

    # ------------------------------------------------------------------ reading the history

    def search(self, query: ItemImportQuery) -> Page[ItemImportBatch]:
        statement = self._select()
        if query.status:
            statement = statement.where(ItemImport.status == query.status)
        if query.uploaded_by_user_id:
            statement = statement.where(ItemImport.uploaded_by_user_id == query.uploaded_by_user_id)
        if query.date_from:
            statement = statement.where(ItemImport.uploaded_at >= _utc_start(query.date_from))
        if query.date_to:
            statement = statement.where(ItemImport.uploaded_at < _utc_start(query.date_to + timedelta(days=1)))
        if query.search:
            term = query.search.strip()
            statement = statement.where(
                or_(
                    ItemImport.file_name.contains(term, autoescape=True),
                    ItemImport.batch_no.contains(term, autoescape=True),
                )
            )
        sort: SortColumns = {
            "uploadedAt": ItemImport.uploaded_at,
            "fileName": ItemImport.file_name,
            "batchNo": ItemImport.id,
            "totalRows": ItemImport.total_rows,
            "status": ItemImport.status,
        }
        statement = order_by_sort(statement, query.sort, sort, default="-uploadedAt", tiebreaker=ItemImport.id.desc())
        page = paginate(self._db, statement, query, ItemImportBatch)
        page.items = [self._with_permissions(b) for b in page.items]
        return page

    def get(self, import_id: int) -> ItemImportBatch:
        row = self._db.execute(self._select().where(ItemImport.id == import_id)).mappings().one_or_none()
        if row is None:
            raise NotFound("Import not found.")
        return self._with_permissions(ItemImportBatch.model_validate(row))

    def lines(self, import_id: int, query: ItemImportLineQuery) -> Page[ItemImportLineOut]:
        self._batch(import_id)
        statement: Select[Any] = select(ItemImportLine).where(ItemImportLine.import_id == import_id)
        if query.status in ("Create", "Update", "Skip", "Error"):
            statement = statement.where(ItemImportLine.action == query.status)
        elif query.status:
            statement = statement.where(ItemImportLine.outcome == query.status)
        if query.search:
            term = query.search.strip()
            statement = statement.where(
                or_(
                    ItemImportLine.item_code.contains(term, autoescape=True),
                    ItemImportLine.description.contains(term, autoescape=True),
                )
            )
        sort: SortColumns = {"rowNumber": ItemImportLine.row_number, "itemCode": ItemImportLine.item_code}
        statement = order_by_sort(statement, query.sort, sort, default="rowNumber", tiebreaker=ItemImportLine.id.asc())
        total = self._db.scalar(select(func.count()).select_from(statement.order_by(None).subquery())) or 0
        lines = self._db.scalars(statement.offset((query.page - 1) * query.page_size).limit(query.page_size)).all()
        return Page(items=[_line_out(line) for line in lines], total=total, page=query.page, page_size=query.page_size)

    def uploaders(self) -> list[ItemImportUploader]:
        who = _who()
        rows = self._db.execute(
            select(AppUser.id, who.label("name"))
            .where(AppUser.id.in_(select(ItemImport.uploaded_by_user_id).distinct()))
            .outerjoin(Employee, Employee.id == AppUser.employee_id)
            .order_by(who)
        ).all()
        return [ItemImportUploader(id=r.id, name=r.name) for r in rows]

    def original_file(self, import_id: int) -> tuple[str, str, bytes]:
        batch = self._batch(import_id)
        raw = storage.read(batch.file_key or "") if batch.file_key else None
        if raw is None:
            raise NotFound("The uploaded file is not available.")
        content_type = _EXTENSIONS.get(Path(batch.file_name).suffix.lower(), "application/octet-stream")
        return batch.file_name, content_type, raw

    def error_report(self, import_id: int) -> tuple[str, bytes]:
        """An .xlsx of the rows that were not (or will not be) imported, with the reasons and the original cells."""
        batch = self._batch(import_id)
        lines = self._db.scalars(
            select(ItemImportLine)
            .where(
                ItemImportLine.import_id == import_id,
                or_(ItemImportLine.action.in_(("Error", "Skip")), ItemImportLine.outcome.in_(("Failed", "Skipped"))),
            )
            .order_by(ItemImportLine.row_number, ItemImportLine.id)
        ).all()
        sources = [json.loads(line.source_data) if line.source_data else {} for line in lines]
        headers: list[str] = []
        for source in sources:
            headers.extend(h for h in source if h not in headers)

        book = Workbook()
        sheet = book.active
        assert sheet is not None
        sheet.title = "Errors"
        sheet.append(["Row", "Result", "Problems", *headers])
        for line, source in zip(lines, sources, strict=True):
            result = line.outcome or {"Error": "Error", "Skip": "Duplicate / skipped"}.get(line.action, line.action)
            messages = json.loads(line.messages) if line.messages else []
            sheet.append([line.row_number, result, "\n".join(messages), *(source.get(h) for h in headers)])
        if batch.error_message:
            sheet.append([])
            sheet.append(["", "Batch", batch.error_message])
        _style_header(sheet, 3 + len(headers))
        sheet.column_dimensions["C"].width = 70
        for cell in sheet["C"][1:]:
            cell.alignment = Alignment(wrap_text=True, vertical="top")
        return f"{batch.batch_no or batch.id}-errors.xlsx", _save(book)

    def template(self) -> bytes:
        return build_template(self._db, self._actor)

    # ------------------------------------------------------------------ helpers

    def _batch(self, import_id: int) -> ItemImport:
        batch = self._db.get(ItemImport, import_id)
        if batch is None:
            raise NotFound("Import not found.")
        self._db.refresh(batch)
        return batch

    def _select(self) -> Select[*tuple[Any, ...]]:
        return (
            select(
                ItemImport.id,
                ItemImport.batch_no,
                ItemImport.file_name,
                ItemImport.file_size,
                # SQL Server has no boolean expressions in a select list, so CASE instead of IS NOT NULL.
                case((ItemImport.file_key.is_not(None), True), else_=False).label("has_file"),
                ItemImport.duplicate_mode,
                ItemImport.status,
                ItemImport.total_rows,
                ItemImport.valid_count,
                ItemImport.created_count,
                ItemImport.updated_count,
                ItemImport.failed_count,
                ItemImport.skipped_count,
                ItemImport.error_message,
                ItemImport.uploaded_by_user_id,
                _who().label("uploaded_by_name"),
                ItemImport.uploaded_at,
                ItemImport.completed_at,
            )
            .outerjoin(AppUser, AppUser.id == ItemImport.uploaded_by_user_id)
            .outerjoin(Employee, Employee.id == AppUser.employee_id)
        )

    def _with_permissions(self, batch: ItemImportBatch) -> ItemImportBatch:
        batch.has_file = bool(batch.has_file)
        batch.can_confirm = (
            batch.status == "Pending"
            and batch.valid_count > 0
            and batch.uploaded_by_user_id == self._actor.id
            and self._actor.can(ITEM_IMPORT)
        )
        return batch


def _who() -> Any:
    name = func.coalesce(Employee.first_name, "") + " " + func.coalesce(Employee.last_name, "")
    return func.coalesce(func.nullif(func.trim(name), ""), AppUser.username)


def _utc_start(day: date) -> datetime:
    return datetime.combine(day, time.min, tzinfo=_IST).astimezone(UTC).replace(tzinfo=None)


def _line_out(line: ItemImportLine) -> ItemImportLineOut:
    changes = json.loads(line.changes) if line.changes else []
    return ItemImportLineOut(
        id=line.id,
        row_number=line.row_number,
        item_code=line.item_code,
        description=line.description,
        action=line.action,
        outcome=line.outcome,
        item_id=line.item_id,
        messages=json.loads(line.messages) if line.messages else [],
        changes=[ItemImportFieldChange.model_validate(c) for c in changes],
    )


# ---------------------------------------------------------------------- workbooks

_HEADER_FILL = PatternFill("solid", fgColor="1F4E79")
_REQUIRED_FILL = PatternFill("solid", fgColor="9C2A00")


def _style_header(sheet: Any, columns: int, required: set[int] | None = None) -> None:
    for index in range(1, columns + 1):
        cell = sheet.cell(row=1, column=index)
        cell.font = Font(bold=True, color="FFFFFF")
        cell.fill = _REQUIRED_FILL if required and index in required else _HEADER_FILL
        cell.alignment = Alignment(vertical="center")
        sheet.column_dimensions[get_column_letter(index)].width = max(14, len(str(cell.value or "")) + 4)
    sheet.freeze_panes = "A2"


def _save(book: Workbook) -> bytes:
    buffer = io.BytesIO()
    book.save(buffer)
    return buffer.getvalue()


def build_template(db: Session, actor: CurrentUser) -> bytes:
    """The sample workbook: an empty Items sheet with validation, the instructions, and the valid codes."""
    book = Workbook()
    items = book.active
    assert items is not None
    items.title = "Items"
    items.append([f"{c.label} *" if c.required else c.label for c in COLUMNS])
    _style_header(items, len(COLUMNS), {i + 1 for i, c in enumerate(COLUMNS) if c.required})

    categories = db.execute(
        select(ItemCategory.code, ItemCategory.name).where(ItemCategory.is_active).order_by(ItemCategory.code)
    ).all()
    uoms = db.execute(select(Uom.code, Uom.name).where(Uom.is_active).order_by(Uom.code)).all()
    brands_q = select(Principal.code, Principal.name).where(Principal.is_active).order_by(Principal.code)
    if actor.principal_ids is not None:
        brands_q = brands_q.where(Principal.id.in_(actor.principal_ids or [0]))
    brands = db.execute(brands_q).all()

    lists = book.create_sheet("Lists")
    lists.append(["Category Code", "Category", "", "UOM Code", "Unit", "", "Brand Code", "Brand", "", "Item Type"])
    longest = max(len(categories), len(uoms), len(brands), 3)
    types = ["Stock", "Non stock", "Service"]
    for i in range(longest):
        row: list[Any] = []
        for values in (categories, uoms, brands):
            row.extend([values[i][0], values[i][1]] if i < len(values) else ["", ""])
            row.append("")
        row.append(types[i] if i < len(types) else "")
        lists.append(row)
    _style_header(lists, 10)

    def column_of(key: str) -> str:
        return str(get_column_letter(next(i for i, c in enumerate(COLUMNS) if c.key == key) + 1))

    last = MAX_ROWS + 1
    validations = [
        ("item_type", '"Stock,Non stock,Service"'),
        ("serialized", '"Y,N"'),
        ("batch", '"Y,N"'),
        ("active", '"Y,N"'),
    ]
    if categories:
        validations.append(("category", f"Lists!$A$2:$A${len(categories) + 1}"))
    if uoms:
        validations.append(("uom", f"Lists!$D$2:$D${len(uoms) + 1}"))
    if brands:
        validations.append(("brand", f"Lists!$G$2:$G${len(brands) + 1}"))
    for key, formula in validations:
        rule = DataValidation(type="list", formula1=formula, allow_blank=True, showErrorMessage=True)
        rule.error = f"Pick a value from the list for {_BY_KEY[key].label}."
        items.add_data_validation(rule)
        rule.add(f"{column_of(key)}2:{column_of(key)}{last}")

    guide = book.create_sheet("Instructions")
    guide.append(["Column", "Required", "What to enter", "Example"])
    examples = {
        "item_code": "FIL-1001", "description": "Engine oil filter",
        "category": categories[0][0] if categories else "SP",
        "item_type": "Stock", "uom": uoms[0][0] if uoms else "NOS", "brand": brands[0][0] if brands else "",
        "oem": "4429729", "long_description": "Spin-on oil filter for EX 200", "hsn": "84212300",
        "serialized": "N", "batch": "N", "standard_cost": "450", "mrp": "620", "reorder_level": "10",
        "reorder_qty": "25", "lead_time": "7", "active": "Y",
    }  # fmt: skip
    for c in COLUMNS:
        guide.append([c.label, "Yes" if c.required else "", c.note, examples.get(c.key, "")])
    guide.append([])
    for note in (
        "Fill the Items sheet from row 2; keep the header row as it is. Columns may be in any order.",
        f"At most {MAX_ROWS:,} rows and 10 MB per file. Excel (.xlsx, .xls) and CSV (.csv) files are accepted.",
        "Codes for categories, units and brands are on the Lists sheet.",
        "An Item Code that already exists is skipped (or, if you may, updated from the filled cells only).",
        "A row repeating an Item Code of an earlier row in the file is skipped.",
        "Nothing is imported until you check the preview and confirm the import.",
    ):
        guide.append([note])
    _style_header(guide, 4)
    guide.column_dimensions["C"].width = 70
    guide.column_dimensions["D"].width = 30
    return _save(book)
