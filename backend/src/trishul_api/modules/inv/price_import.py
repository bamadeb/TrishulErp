"""Bulk item price import: update the prices of existing items from an Excel (.xlsx, .xls) or CSV file.

Prices (see prices.py): Selling Price -> the chosen price list, Purchase Price -> standard cost, MRP -> MRP.
Items are never created here.

Files:
  * the SAP S/4HANA price file -- also the downloadable sample (Sl No., External ID (S4H), Material,
    Description, HSN Code, ZAmount): matched within the selected brand by OEM part number or item code
    (0000534 = 534); ZAmount updates the price chosen on upload.
  * the older layout: Item Code, Item Name (not read), Selling Price, Purchase Price, MRP, Reason. A blank price
    cell leaves that price as it is; a row needs at least one price.

Flow:
  1. upload()   stores the file (with its SHA-256), checks every row against the item master and saves the
                comparison (current -> new price) as a Pending batch. Nothing changes yet.
  2. confirm()  the uploader, once. The file is checked again; a row whose current price differs from what the
                preview showed is not applied (it fails with the reason). If a change is over the allowed
                percentage and the user cannot approve price changes, the batch waits (Pending approval).
                Otherwise every valid change is written in ONE transaction.
  3. approve() / reject()  for a batch waiting for approval (inv.price.approve).
Every change is added to inv.item_price_history with the batch and the reason.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import timedelta
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from pathlib import Path
from typing import Any

from openpyxl import Workbook
from openpyxl.styles import Alignment
from openpyxl.worksheet.datavalidation import DataValidation
from sqlalchemy import Select, case, delete, func, insert, or_, select, update
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, aliased

from trishul_api.auth import CurrentUser, RequestScope
from trishul_api.common.errors import ApiError, Conflict, Forbidden, NotFound
from trishul_api.common.paging import SortColumns, order_by_sort
from trishul_api.common.schemas import Page
from trishul_api.db.models import (
    AppUser,
    Employee,
    Item,
    ItemPriceHistory,
    PriceImport,
    PriceImportLine,
    PriceList,
    PriceListItem,
    Principal,
)
from trishul_api.db.models.price_import import PriceField, PriceImportLineAction
from trishul_api.modules.core.documents import storage
from trishul_api.modules.inv.common import default_company, now
from trishul_api.modules.inv.item_list_import import (
    MAX_ROWS,
    XLSX,
    _grid,
    _norm,
    _save,
    _style_header,
    _text,
    _utc_start,
    check_upload,
)
from trishul_api.modules.inv.price_import_schemas import (
    ItemPriceChange,
    PriceImportBatch,
    PriceImportLineOut,
    PriceImportLineQuery,
    PriceImportOptions,
    PriceImportQuery,
    PriceImportUploader,
    PriceListOption,
)
from trishul_api.modules.inv.prices import (
    PRICE_APPROVE,
    PRICE_IMPORT,
    base_selling_row,
    max_change_pct,
    record_price_change,
)

_CHUNK = 500
_HEADER_SCAN = 15
_FILE_TYPES = {".xlsx": XLSX, ".xls": "application/vnd.ms-excel", ".csv": "text/csv"}
_PLACES = {"selling": 4, "purchase": 4, "mrp": 2}
_LABELS = {"selling": "Selling Price", "purchase": "Purchase Price", "mrp": "MRP"}
_SAP_TARGET = {"Selling": "selling", "Purchase": "purchase", "MRP": "mrp"}

# The sample file is the SAP S/4HANA layout; the older Item Code / Selling / Purchase / MRP layout is still read.
TEMPLATE_COLUMNS = ("Sl No.", "External ID (S4H)", "Material", "Description", "HSN Code", "ZAmount")
_TEMPLATE_HEADERS = {
    "itemcode": "item_code", "code": "item_code",
    "itemname": "name", "description": "name", "name": "name",
    "sellingprice": "selling", "saleprice": "selling", "salesprice": "selling",
    "purchaseprice": "purchase", "standardcost": "purchase", "purchasecost": "purchase",
    "mrp": "mrp",
    "reason": "reason", "changereason": "reason",
}  # fmt: skip


# ---------------------------------------------------------------------- reading the file


@dataclass
class PriceRow:
    row_number: int
    code: str | None  # item code (template) or External ID (SAP)
    name: str | None
    prices: dict[str, str | None]  # selling / purchase / mrp -> cell text
    reason: str | None
    source: dict[str, str | None]


def read_price_rows(extension: str, raw: bytes, sap_field: PriceField | None) -> tuple[str, list[PriceRow]]:
    """('Template' | 'SAP', rows)."""
    grid = _grid(extension, raw)
    for index, cells in enumerate(grid[:_HEADER_SCAN]):
        labels = {i: (_text(c) or "").rstrip(" *") for i, c in enumerate(cells) if _text(c)}
        names = {i: _norm(label) for i, label in labels.items()}
        template = {_TEMPLATE_HEADERS[n]: i for i, n in reversed(list(names.items())) if n in _TEMPLATE_HEADERS}
        if "item_code" in template:
            return "Template", _rows(grid, index, labels, template, None)
        sap: dict[str, int] = {}
        for i, label in labels.items():
            text = label.lower()
            if text.startswith("external id"):
                sap.setdefault("item_code", i)
            elif text == "description":
                sap.setdefault("name", i)
            elif text in {"zamount", "amount"}:
                sap.setdefault("price", i)
        if "item_code" in sap and "price" in sap:
            return "SAP", _rows(grid, index, labels, sap, _SAP_TARGET[sap_field or "MRP"])
    raise ApiError(
        "No header row with an 'Item Code' column was found (or the SAP columns External ID and ZAmount). "
        "Use the sample template."
    )


def _rows(
    grid: list[list[Any]], header: int, labels: dict[int, str], columns: dict[str, int], sap_target: str | None
) -> list[PriceRow]:
    def cell(cells: list[Any], key: str) -> str | None:
        index = columns.get(key)
        return _text(cells[index]) if index is not None and index < len(cells) else None

    rows: list[PriceRow] = []
    for offset, cells in enumerate(grid[header + 1 :]):
        if not any(_text(c) for c in cells):
            continue
        if len(rows) >= MAX_ROWS:
            raise ApiError(f"The file has more than {MAX_ROWS:,} rows. Split it into smaller files.")
        if sap_target:
            price = cell(cells, "price")
            prices = {sap_target: None if price is None or _is_zero(price) else price}
        else:
            prices = {key: cell(cells, key) for key in ("selling", "purchase", "mrp")}
        rows.append(
            PriceRow(
                row_number=header + 2 + offset,
                code=cell(cells, "item_code"),
                name=cell(cells, "name"),
                prices=prices,
                reason=cell(cells, "reason"),
                source={label: _text(cells[i]) if i < len(cells) else None for i, label in labels.items()},
            )
        )
    if not rows:
        raise ApiError("The file has no rows under the header row.")
    return rows


def _is_zero(text: str) -> bool:
    try:
        return Decimal(text.replace(",", "")) == 0
    except InvalidOperation:
        return False


def _sap_key(value: str | None) -> str | None:
    """0000534 and 534 are the same SAP part."""
    return (value.upper().lstrip("0") or "0") if value else None


# ---------------------------------------------------------------------- planning


@dataclass
class Planned:
    row: PriceRow
    action: PriceImportLineAction = "Change"
    item: Item | None = None
    messages: list[str] = field(default_factory=list)
    old: dict[str, Decimal | None] = field(default_factory=dict)
    new: dict[str, Decimal | None] = field(default_factory=dict)
    pct: Decimal | None = None
    over_limit: bool = False

    def error(self, message: str) -> None:
        self.action = "Error"
        self.messages.append(message)

    def changed(self) -> dict[str, Decimal]:
        return {k: v for k, v in self.new.items() if v is not None and not _same(self.old.get(k), v)}


def _same(old: Decimal | None, new: Decimal | None) -> bool:
    return old is not None and new is not None and Decimal(old) == Decimal(new)


@dataclass
class Context:
    layout: str
    price_list: PriceList | None
    principal_id: int | None  # the brand selected at upload (SAP matching)
    limit: Decimal


class _Planner:
    def __init__(self, db: Session, actor: CurrentUser, ctx: Context) -> None:
        self._db = db
        self._actor = actor
        self._ctx = ctx

    def plan(self, rows: list[PriceRow]) -> list[Planned]:
        plan = [self._parse(row) for row in rows]
        self._match(plan)
        self._mark_duplicates(plan)
        for p in plan:
            if p.action != "Error" and p.item is not None:
                self._compare(p)
        return plan

    def _parse(self, row: PriceRow) -> Planned:
        p = Planned(row=row)
        if not row.code:
            p.error("Item Code is required." if self._ctx.layout == "Template" else "No External ID on this row.")
        for key, text in row.prices.items():
            if text is None:
                continue
            value = _money(p, _LABELS[key], text, _PLACES[key])
            if value is not None:
                p.new[key] = value
        if not row.prices or all(v is None for v in row.prices.values()):
            p.error(
                "No price given: fill at least one of Selling Price, Purchase Price and MRP."
                if self._ctx.layout == "Template"
                else "Zero or blank ZAmount: there is no price to import."
            )
        if p.new.get("selling") is not None and self._ctx.price_list is None:
            p.error("Choose a price list on the upload form to import selling prices.")
        if row.reason and len(row.reason) > 300:
            p.error("Reason is longer than 300 characters.")
        return p

    def _match(self, plan: list[Planned]) -> None:
        wanted = sorted({p.row.code for p in plan if p.row.code})
        sap = self._ctx.layout == "SAP"

        def key(code: str) -> str:
            return (_sap_key(code) or "") if sap else code.upper()

        if not sap:
            found: dict[str, list[Item]] = {}
            upper = sorted({c.upper() for c in wanted})
            for start in range(0, len(upper), _CHUNK):
                for item in self._db.scalars(select(Item).where(Item.item_code.in_(upper[start : start + _CHUNK]))):
                    found.setdefault(item.item_code.upper(), []).append(item)
        else:
            found = {}
            seen: set[int] = set()
            for start in range(0, len(wanted), _CHUNK):
                chunk = wanted[start : start + _CHUNK]
                items = self._db.scalars(
                    select(Item).where(
                        or_(Item.principal_id == self._ctx.principal_id, Item.principal_id.is_(None)),
                        or_(Item.oem_part_number.in_(chunk), Item.item_code.in_(chunk)),
                    )
                ).all()
                for item in items:
                    if item.id in seen:
                        continue
                    seen.add(item.id)
                    for number in {item.oem_part_number, item.item_code}:
                        if number and number in chunk:
                            found.setdefault(_sap_key(number) or "", []).append(item)

        for p in plan:
            if not p.row.code:
                continue
            matches = [
                i for i in found.get(key(p.row.code), [])
                if i.principal_id is None or self._actor.can_see_principal(i.principal_id)
            ]  # fmt: skip
            if not matches:
                p.error(f"Item {p.row.code} is not in the item master; nothing is created by a price import.")
            elif len(matches) > 1:
                codes = ", ".join(sorted(i.item_code for i in matches))
                p.error(f"{p.row.code} matches several items ({codes}); use the item code.")
            elif not matches[0].is_active:
                p.item = matches[0]
                p.error(f"Item {matches[0].item_code} is inactive.")
            else:
                p.item = matches[0]

    @staticmethod
    def _mark_duplicates(plan: list[Planned]) -> None:
        """An item on more than one row: none of its rows is imported (which price is right is unclear)."""
        rows_of: dict[int, list[int]] = {}
        for p in plan:
            if p.item is not None:
                rows_of.setdefault(p.item.id, []).append(p.row.row_number)
        for p in plan:
            if p.item is None or len(rows_of[p.item.id]) < 2:
                continue
            others = ", ".join(str(n) for n in rows_of[p.item.id])
            p.messages.append(f"Item {p.item.item_code} is on rows {others}; none of them is imported.")
            if p.action != "Error":
                p.action = "Duplicate"

    def _compare(self, p: Planned) -> None:
        item = p.item
        assert item is not None
        price_list = self._ctx.price_list
        p.old["purchase"] = item.standard_cost
        p.old["mrp"] = item.mrp
        if price_list is not None:
            if price_list.principal_id is not None and price_list.principal_id != item.principal_id:
                if p.new.get("selling") is not None:
                    p.error(f"Price list {price_list.code} is for another brand than item {item.item_code}.")
                    return
            else:
                current = base_selling_row(self._db, price_list.id, item.id)
                p.old["selling"] = current.unit_price if current is not None and current.is_active else None
        changes = p.changed()
        if not changes:
            p.action = "Unchanged"
            return
        biggest: Decimal | None = None
        for key, new in changes.items():
            old = p.old.get(key)
            if old is None or Decimal(old) == 0:
                continue
            pct = ((new - Decimal(old)) / Decimal(old) * 100).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
            if biggest is None or abs(pct) > abs(biggest):
                biggest = pct
        p.pct = biggest
        p.over_limit = biggest is not None and abs(biggest) > self._ctx.limit
        if p.over_limit:
            p.messages.append(f"Change of {biggest}% is over the {self._ctx.limit}% limit: needs approval.")


def _money(p: Planned, label: str, text: str, places: int) -> Decimal | None:
    try:
        value = Decimal(text.replace(",", "").replace("₹", "").strip())
    except InvalidOperation:
        p.error(f"{label} '{text}' is not a number.")
        return None
    if not value.is_finite():
        p.error(f"{label} '{text}' is not a number.")
        return None
    if value < 0:
        p.error(f"{label} cannot be negative.")
        return None
    value = value.quantize(Decimal(1).scaleb(-places), rounding=ROUND_HALF_UP)
    if value.adjusted() >= 14:
        p.error(f"{label} is too large.")
        return None
    return value


# ---------------------------------------------------------------------- the service


class PriceImportService:
    def __init__(self, db: Session, actor: CurrentUser) -> None:
        self._db = db
        self._actor = actor

    # ------------------------------------------------------------------ upload, confirm, approve

    def options(self, scope: RequestScope) -> PriceImportOptions:
        lists = self._price_lists()
        default = next(
            (p for p in lists if p.price_list_type == "Retail" and p.principal_id == scope.principal_id), None
        ) or next((p for p in lists if p.price_list_type == "Retail"), None)
        codes = dict(self._db.execute(select(Principal.id, Principal.code)).all())
        return PriceImportOptions(
            price_lists=[
                PriceListOption(
                    id=p.id,
                    code=p.code,
                    name=p.name,
                    price_list_type=p.price_list_type,
                    principal_code=codes.get(p.principal_id) if p.principal_id else None,
                )
                for p in lists
            ],
            default_price_list_id=default.id if default else (lists[0].id if lists else None),
            max_change_pct=max_change_pct(self._db),
        )

    def upload(
        self,
        file_name: str,
        raw: bytes,
        *,
        price_list_id: int | None,
        sap_price_field: PriceField | None,
        reason: str,
        scope: RequestScope,
    ) -> PriceImportBatch:
        reason = (reason or "").strip()
        if len(reason) < 3:
            raise ApiError("Give the reason for the price change.", errors={"reason": ["At least 3 characters."]})
        name = storage.clean_file_name(file_name)
        check_upload(name, raw)
        price_list = self._price_list(price_list_id)
        batch = PriceImport(
            company_id=default_company(self._db, self._actor, scope),
            file_name=name,
            file_size=len(raw),
            file_hash=hashlib.sha256(raw).hexdigest(),
            price_list_id=price_list.id if price_list else None,
            principal_id=scope.principal_id,
            sap_price_field=sap_price_field,
            reason=reason[:300],
            status="Pending",
            max_change_pct=max_change_pct(self._db),
            uploaded_by_user_id=self._actor.id,
            uploaded_at=now(),
        )
        self._db.add(batch)
        self._db.flush()
        batch.batch_no = f"PRC-{batch.id:06d}"
        batch.file_key = storage.store("price_import", batch.id, name, raw)
        try:
            plan = self._plan(batch, raw)
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
        elif batch.changed_count == 0:
            batch.status = "Completed"
            batch.error_message = "Every price in the file is the same as now; nothing to update."
            batch.completed_at = now()
            self._write_lines(batch, plan, done=True)
        self._db.commit()
        return self.get(batch.id)

    def confirm(self, import_id: int, import_again: bool) -> PriceImportBatch:
        batch = self._batch(import_id)
        if batch.uploaded_by_user_id != self._actor.id:
            raise ApiError("Only the person who uploaded this file can confirm it.")
        if batch.status == "Pending":
            repeat = self._repeat_of(batch)
            if repeat and not import_again:
                raise Conflict(
                    f"This file was already imported in batch {repeat}. Tick 'Import this file again' to go on."
                )
        self._claim(import_id, "Pending", confirmed_by_user_id=self._actor.id, confirmed_at=now())
        return self._process(import_id, approving=False)

    def approve(self, import_id: int, note: str | None) -> PriceImportBatch:
        self._require_approver()
        self._batch(import_id)
        self._claim(
            import_id, "Pending approval", approved_by_user_id=self._actor.id, approved_at=now(), decision_note=note
        )
        return self._process(import_id, approving=True)

    def reject(self, import_id: int, note: str | None) -> PriceImportBatch:
        self._require_approver()
        self._batch(import_id)
        self._claim(
            import_id,
            "Pending approval",
            status="Rejected",
            rejected_by_user_id=self._actor.id,
            rejected_at=now(),
            decision_note=note,
            completed_at=now(),
        )
        self._db.execute(
            update(PriceImportLine).where(PriceImportLine.import_id == import_id).values(outcome="Skipped")
        )
        self._db.commit()
        return self.get(import_id)

    def _process(self, import_id: int, *, approving: bool) -> PriceImportBatch:
        batch = self._batch(import_id)
        try:
            raw = storage.read(batch.file_key or "")
            if raw is None:
                raise ApiError("The uploaded file is no longer available. Upload it again.")
            preview = {
                line.row_number: line
                for line in self._db.scalars(select(PriceImportLine).where(PriceImportLine.import_id == import_id))
            }
            plan = self._plan(batch, raw)
            _keep_what_was_shown(plan, preview)
            needs_approval = any(p.over_limit and p.action == "Change" for p in plan)
            if needs_approval and not approving and not self._actor.can(PRICE_APPROVE):
                self._write_lines(batch, plan, done=False)
                batch.status = "Pending approval"
                self._db.commit()
                return self.get(import_id)
            if needs_approval and not approving:  # the confirming user may approve: recorded as the approver
                batch.approved_by_user_id = self._actor.id
                batch.approved_at = now()
            self._apply(batch, plan)
            self._db.commit()
        except (ApiError, SQLAlchemyError) as error:
            self._db.rollback()
            reason = (error.detail or "error") if isinstance(error, ApiError) else "a database error occurred"
            self._fail(import_id, f"No price was changed: {reason}.")
            if isinstance(error, ApiError):
                raise
            raise ApiError(f"The price import failed and nothing was saved ({type(error).__name__}).") from error
        return self.get(import_id)

    def _apply(self, batch: PriceImport, plan: list[Planned]) -> None:
        stamp = now()
        for p in plan:
            if p.action != "Change" or p.item is None:
                continue
            item, changes = p.item, p.changed()
            selling_pair = None
            min_qty = None
            if "selling" in changes and batch.price_list_id is not None:
                row = base_selling_row(self._db, batch.price_list_id, item.id)
                if row is None:
                    row = PriceListItem(
                        price_list_id=batch.price_list_id,
                        item_id=item.id,
                        unit_price=changes["selling"],
                        min_qty=Decimal(1),
                        created_by_user_id=self._actor.id,
                    )
                    self._db.add(row)
                else:
                    row.unit_price = changes["selling"]
                    row.is_active = True
                    row.updated_at = stamp
                    row.updated_by_user_id = self._actor.id
                selling_pair = (p.old.get("selling"), changes["selling"])
                min_qty = row.min_qty
            if "purchase" in changes:
                item.standard_cost = changes["purchase"]
            if "mrp" in changes:
                item.mrp = changes["mrp"]
            if "purchase" in changes or "mrp" in changes:
                item.updated_at = stamp
                item.updated_by_user_id = self._actor.id
            record_price_change(
                self._db,
                item,
                user_id=self._actor.id,
                source="Import",
                selling=selling_pair,
                price_list_id=batch.price_list_id,
                min_qty=min_qty,
                purchase=(p.old.get("purchase"), changes["purchase"]) if "purchase" in changes else None,
                mrp=(p.old.get("mrp"), changes["mrp"]) if "mrp" in changes else None,
                import_id=batch.id,
                reason=p.row.reason or batch.reason,
            )
        self._db.flush()  # a failure here rolls the whole import back
        self._write_lines(batch, plan, done=True)
        if batch.updated_count:
            problems = batch.failed_count + batch.skipped_count
            batch.status = "Partially Completed" if problems else "Completed"
        else:
            batch.status = "Failed" if batch.failed_count else "Completed"
            if batch.failed_count:
                batch.error_message = "No price could be updated. Download the error report for the reasons."
        batch.completed_at = now()

    def _plan(self, batch: PriceImport, raw: bytes) -> list[Planned]:
        extension = Path(batch.file_name).suffix.lower()
        sap_field = batch.sap_price_field
        layout, rows = read_price_rows(extension, raw, sap_field)
        batch.file_layout = "SAP" if layout == "SAP" else "Template"
        if layout == "SAP":
            if batch.principal_id is None:
                raise ApiError("Select a brand at the top first: SAP price files are matched within a brand.")
            if batch.sap_price_field is None:
                batch.sap_price_field = "MRP"
        price_list = self._db.get(PriceList, batch.price_list_id) if batch.price_list_id else None
        limit = Decimal(batch.max_change_pct) if batch.max_change_pct is not None else max_change_pct(self._db)
        ctx = Context(layout=layout, price_list=price_list, principal_id=batch.principal_id, limit=limit)
        return _Planner(self._db, self._actor, ctx).plan(rows)

    def _write_lines(self, batch: PriceImport, plan: list[Planned], *, done: bool) -> None:
        self._db.execute(delete(PriceImportLine).where(PriceImportLine.import_id == batch.id))
        outcome = {"Change": "Updated", "Unchanged": "Unchanged", "Duplicate": "Skipped", "Error": "Failed"}
        rows = [
            {
                "import_id": batch.id,
                "row_number": p.row.row_number,
                "item_code": (p.item.item_code if p.item is not None else (p.row.code or ""))[:60] or None,
                "item_id": p.item.id if p.item is not None else None,
                "item_name": ((p.item.description if p.item is not None else p.row.name) or "")[:200] or None,
                "action": p.action,
                "outcome": outcome[p.action] if done else None,
                "old_selling": p.old.get("selling"),
                "new_selling": p.new.get("selling"),
                "old_purchase": p.old.get("purchase"),
                "new_purchase": p.new.get("purchase"),
                "old_mrp": p.old.get("mrp"),
                "new_mrp": p.new.get("mrp"),
                "max_change_pct": p.pct,
                "over_limit": p.over_limit,
                "reason": (p.row.reason or "")[:300] or None,
                "messages": json.dumps(p.messages) if p.messages else None,
                "source_data": json.dumps(p.row.source, ensure_ascii=False),
            }
            for p in plan
        ]
        for start in range(0, len(rows), _CHUNK):
            self._db.execute(insert(PriceImportLine), rows[start : start + _CHUNK])

        def count(action: str) -> int:
            return sum(1 for p in plan if p.action == action)

        batch.total_rows = len(plan)
        batch.valid_count = count("Change") + count("Unchanged")
        batch.invalid_count = count("Error")
        batch.duplicate_count = count("Duplicate")
        batch.changed_count = count("Change")
        batch.unchanged_count = count("Unchanged")
        batch.over_limit_count = sum(1 for p in plan if p.action == "Change" and p.over_limit)
        batch.updated_count = count("Change") if done else 0
        batch.failed_count = count("Error")
        batch.skipped_count = count("Duplicate")

    def _claim(self, import_id: int, expected: str, **values: Any) -> None:
        """Moves the batch on from `expected` (to Processing unless a status is given); only one request can."""
        claimed = self._db.execute(  # type: ignore[attr-defined]
            update(PriceImport)
            .where(PriceImport.id == import_id, PriceImport.status == expected)
            .values(status=values.pop("status", "Processing"), **values)
        ).rowcount
        if not claimed:
            self._db.rollback()
            current = self._db.scalar(select(PriceImport.status).where(PriceImport.id == import_id))
            raise Conflict(f"This price import is {str(current).lower()}, not {expected.lower()}.")
        self._db.commit()

    def _fail(self, import_id: int, message: str) -> None:
        self._db.execute(
            update(PriceImport)
            .where(PriceImport.id == import_id)
            .values(status="Failed", error_message=message[:1000], completed_at=now(), updated_count=0)
        )
        self._db.execute(update(PriceImportLine).where(PriceImportLine.import_id == import_id).values(outcome=None))
        self._db.commit()

    def _require_approver(self) -> None:
        if not self._actor.can(PRICE_APPROVE):
            raise Forbidden("Approving price changes needs the price approval permission.")

    # ------------------------------------------------------------------ reading

    def search(self, query: PriceImportQuery) -> Page[PriceImportBatch]:
        statement = self._select()
        if query.status:
            statement = statement.where(PriceImport.status == query.status)
        if query.uploaded_by_user_id:
            statement = statement.where(PriceImport.uploaded_by_user_id == query.uploaded_by_user_id)
        if query.date_from:
            statement = statement.where(PriceImport.uploaded_at >= _utc_start(query.date_from))
        if query.date_to:
            statement = statement.where(PriceImport.uploaded_at < _utc_start(query.date_to + timedelta(days=1)))
        if query.search:
            term = query.search.strip()
            statement = statement.where(
                or_(
                    PriceImport.file_name.contains(term, autoescape=True),
                    PriceImport.batch_no.contains(term, autoescape=True),
                    PriceImport.reason.contains(term, autoescape=True),
                )
            )
        sort: SortColumns = {
            "uploadedAt": PriceImport.uploaded_at,
            "fileName": PriceImport.file_name,
            "batchNo": PriceImport.batch_no,  # zero-padded, so it sorts like the id
            "totalRows": PriceImport.total_rows,
            "updatedCount": PriceImport.updated_count,
            "status": PriceImport.status,
        }
        statement = order_by_sort(statement, query.sort, sort, default="-uploadedAt", tiebreaker=PriceImport.id.desc())
        total = self._db.scalar(select(func.count()).select_from(statement.order_by(None).subquery())) or 0
        rows = self._db.execute(statement.offset((query.page - 1) * query.page_size).limit(query.page_size))
        items = [self._finish(PriceImportBatch.model_validate(r)) for r in rows.mappings()]
        return Page(items=items, total=total, page=query.page, page_size=query.page_size)

    def get(self, import_id: int) -> PriceImportBatch:
        row = self._db.execute(self._select().where(PriceImport.id == import_id)).mappings().one_or_none()
        if row is None:
            raise NotFound("Price import not found.")
        batch = self._finish(PriceImportBatch.model_validate(row))
        stored = self._db.get(PriceImport, import_id)
        batch.repeat_of_batch_no = self._repeat_of(stored) if stored else None
        return batch

    def lines(self, import_id: int, query: PriceImportLineQuery) -> Page[PriceImportLineOut]:
        self._batch(import_id)
        line = PriceImportLine
        statement: Select[Any] = select(line).where(line.import_id == import_id)
        status = query.status
        if status in ("Change", "Unchanged", "Duplicate", "Error"):
            statement = statement.where(line.action == status)
        elif status == "Increase":
            statement = statement.where(line.action == "Change", line.max_change_pct > 0)
        elif status == "Decrease":
            statement = statement.where(line.action == "Change", line.max_change_pct < 0)
        elif status == "OverLimit":
            statement = statement.where(line.over_limit.is_(True))
        elif status:
            statement = statement.where(line.outcome == status)
        if query.search:
            term = query.search.strip()
            statement = statement.where(
                or_(line.item_code.contains(term, autoescape=True), line.item_name.contains(term, autoescape=True))
            )
        sort: SortColumns = {
            "rowNumber": line.row_number,
            "itemCode": line.item_code,
            "change": func.abs(line.max_change_pct),
        }
        statement = order_by_sort(statement, query.sort, sort, default="rowNumber", tiebreaker=line.id.asc())
        total = self._db.scalar(select(func.count()).select_from(statement.order_by(None).subquery())) or 0
        found = self._db.scalars(statement.offset((query.page - 1) * query.page_size).limit(query.page_size)).all()
        return Page(items=[_line_out(x) for x in found], total=total, page=query.page, page_size=query.page_size)

    def uploaders(self) -> list[PriceImportUploader]:
        who = _who(Employee, AppUser)
        rows = self._db.execute(
            select(AppUser.id, who.label("name"))
            .where(AppUser.id.in_(select(PriceImport.uploaded_by_user_id).distinct()))
            .outerjoin(Employee, Employee.id == AppUser.employee_id)
            .order_by(who)
        ).all()
        return [PriceImportUploader(id=r.id, name=r.name) for r in rows]

    def original_file(self, import_id: int) -> tuple[str, str, bytes]:
        batch = self._batch(import_id)
        raw = storage.read(batch.file_key) if batch.file_key else None
        if raw is None:
            raise NotFound("The uploaded file is not available.")
        return batch.file_name, _FILE_TYPES.get(Path(batch.file_name).suffix.lower(), "application/octet-stream"), raw

    def error_report(self, import_id: int) -> tuple[str, bytes]:
        batch = self._batch(import_id)
        lines = self._db.scalars(
            select(PriceImportLine)
            .where(
                PriceImportLine.import_id == import_id,
                or_(
                    PriceImportLine.action.in_(("Error", "Duplicate")),
                    PriceImportLine.outcome.in_(("Failed", "Skipped")),
                ),
            )
            .order_by(PriceImportLine.row_number, PriceImportLine.id)
        ).all()
        sources = [json.loads(x.source_data) if x.source_data else {} for x in lines]
        headers: list[str] = []
        for source in sources:
            headers.extend(h for h in source if h not in headers)
        book = Workbook()
        sheet = book.active
        assert sheet is not None
        sheet.title = "Errors"
        sheet.append(["Row", "Result", "Problems", *headers])
        for x, source in zip(lines, sources, strict=True):
            result = x.outcome or {"Error": "Error", "Duplicate": "Duplicate"}.get(x.action, x.action)
            messages = json.loads(x.messages) if x.messages else []
            sheet.append([x.row_number, result, "\n".join(messages), *(source.get(h) for h in headers)])
        if batch.error_message:
            sheet.append([])
            sheet.append(["", "Batch", batch.error_message])
        _style_header(sheet, 3 + len(headers))
        sheet.column_dimensions["C"].width = 70
        for cell in sheet["C"][1:]:
            cell.alignment = Alignment(wrap_text=True, vertical="top")
        return f"{batch.batch_no or batch.id}-errors.xlsx", _save(book)

    def template(self) -> bytes:
        """The sample price file, in the SAP S/4HANA layout (External ID ... ZAmount)."""
        book = Workbook()
        sheet = book.active
        assert sheet is not None
        sheet.title = "Prices"
        sheet.append(list(TEMPLATE_COLUMNS))
        _style_header(sheet, len(TEMPLATE_COLUMNS), {2, 6})
        for column, width in zip("ABCDEF", (8, 20, 20, 40, 14, 14), strict=True):
            sheet.column_dimensions[column].width = width
        for column in "BCE":  # keep leading zeros (0000534) as typed
            for row in range(2, 1002):
                sheet[f"{column}{row}"].number_format = "@"
        rule = DataValidation(type="decimal", operator="greaterThanOrEqual", formula1="0", allow_blank=True)
        rule.error = "Enter a price of 0 or more."
        sheet.add_data_validation(rule)
        rule.add(f"F2:F{MAX_ROWS + 1}")
        sheet.auto_filter.ref = f"A1:F{MAX_ROWS + 1}"
        guide = book.create_sheet("Instructions")
        guide.append(["Column", "What to enter"])
        for row in (
            ("Sl No.", "Optional running number; not imported."),
            (
                "External ID (S4H) *",
                "The SAP part number, e.g. 0000534 or 0001310050J. It is matched within the "
                "brand chosen on the upload screen by OEM part number or item code; leading zeros do not matter "
                "(0000534 = 534).",
            ),
            ("Material", "Optional, for your reference only; not imported."),
            ("Description", "Optional, for your reference only; not imported."),
            ("HSN Code", "Optional, for your reference only; not imported."),
            (
                "ZAmount *",
                "The new price. On the upload screen choose which price it updates: MRP, Selling price "
                "(on the chosen price list) or Purchase price (standard cost). 0 or blank = leave as it is.",
            ),
            ("", ""),
            ("Rules", "Each part once per file. Items are never created by a price import."),
            ("", "A change bigger than the allowed percentage needs approval before it is applied."),
            ("", "Nothing changes until you check the comparison and confirm the update."),
            ("", ""),
            (
                "Example",
                "Sl No. 1 | External ID 0000534 | Material 534 | Description CASE;T.MISSION | "
                "HSN Code 84314930 | ZAmount 102358",
            ),
        ):
            guide.append(list(row))
        _style_header(guide, 2)
        guide.column_dimensions["A"].width = 20
        guide.column_dimensions["B"].width = 110
        for cell in guide["B"][1:]:
            cell.alignment = Alignment(wrap_text=True, vertical="top")
        return _save(book)

    def item_history(self, item_id: int, page: int, page_size: int) -> Page[ItemPriceChange]:
        item = self._db.get(Item, item_id)
        if item is None or (item.principal_id is not None and not self._actor.can_see_principal(item.principal_id)):
            raise NotFound("Item not found.")
        who = _who(Employee, AppUser)
        statement = (
            select(
                ItemPriceHistory.id,
                ItemPriceHistory.item_id,
                ItemPriceHistory.item_code,
                PriceList.name.label("price_list_name"),
                ItemPriceHistory.old_selling,
                ItemPriceHistory.new_selling,
                ItemPriceHistory.old_purchase,
                ItemPriceHistory.new_purchase,
                ItemPriceHistory.old_mrp,
                ItemPriceHistory.new_mrp,
                ItemPriceHistory.source,
                ItemPriceHistory.import_id,
                PriceImport.batch_no,
                ItemPriceHistory.reason,
                who.label("changed_by_name"),
                ItemPriceHistory.changed_at,
            )
            .outerjoin(PriceList, PriceList.id == ItemPriceHistory.price_list_id)
            .outerjoin(PriceImport, PriceImport.id == ItemPriceHistory.import_id)
            .outerjoin(AppUser, AppUser.id == ItemPriceHistory.changed_by_user_id)
            .outerjoin(Employee, Employee.id == AppUser.employee_id)
            .where(ItemPriceHistory.item_id == item_id)
            .order_by(ItemPriceHistory.changed_at.desc(), ItemPriceHistory.id.desc())
        )
        total = self._db.scalar(select(func.count()).select_from(statement.order_by(None).subquery())) or 0
        rows = self._db.execute(statement.offset((page - 1) * page_size).limit(page_size)).mappings()
        return Page(
            items=[ItemPriceChange.model_validate(r) for r in rows], total=total, page=page, page_size=page_size
        )

    # ------------------------------------------------------------------ helpers

    def _batch(self, import_id: int) -> PriceImport:
        batch = self._db.get(PriceImport, import_id)
        if batch is None:
            raise NotFound("Price import not found.")
        self._db.refresh(batch)
        return batch

    def _price_lists(self) -> list[PriceList]:
        statement = select(PriceList).where(PriceList.is_active).order_by(PriceList.name)
        if self._actor.principal_ids is not None:
            statement = statement.where(
                or_(PriceList.principal_id.is_(None), PriceList.principal_id.in_(self._actor.principal_ids or [0]))
            )
        return list(self._db.scalars(statement).all())

    def _price_list(self, price_list_id: int | None) -> PriceList | None:
        if price_list_id is None:
            return None
        price_list = next((p for p in self._price_lists() if p.id == price_list_id), None)
        if price_list is None:
            raise ApiError("Choose one of your active price lists.", errors={"priceListId": ["Unknown or inactive."]})
        return price_list

    def _repeat_of(self, batch: PriceImport) -> str | None:
        return self._db.scalar(
            select(PriceImport.batch_no)
            .where(
                PriceImport.file_hash == batch.file_hash,
                PriceImport.id < batch.id,
                or_(
                    PriceImport.updated_count > 0,
                    PriceImport.status.in_(("Pending approval", "Processing")),
                ),
            )
            .order_by(PriceImport.id.desc())
            .limit(1)
        )

    def _select(self) -> Select[*tuple[Any, ...]]:
        uploader, up_emp = aliased(AppUser), aliased(Employee)
        confirmer, co_emp = aliased(AppUser), aliased(Employee)
        approver, ap_emp = aliased(AppUser), aliased(Employee)
        rejecter, re_emp = aliased(AppUser), aliased(Employee)
        return (
            select(
                PriceImport.id,
                PriceImport.batch_no,
                PriceImport.file_name,
                PriceImport.file_size,
                # SQL Server has no boolean expressions in a select list, so CASE instead of IS NOT NULL.
                case((PriceImport.file_key.is_not(None), True), else_=False).label("has_file"),
                PriceImport.file_layout,
                PriceImport.price_list_id,
                PriceList.name.label("price_list_name"),
                PriceImport.sap_price_field,
                PriceImport.reason,
                PriceImport.status,
                PriceImport.max_change_pct,
                PriceImport.total_rows,
                PriceImport.valid_count,
                PriceImport.invalid_count,
                PriceImport.duplicate_count,
                PriceImport.changed_count,
                PriceImport.unchanged_count,
                PriceImport.over_limit_count,
                PriceImport.updated_count,
                PriceImport.failed_count,
                PriceImport.skipped_count,
                PriceImport.error_message,
                PriceImport.uploaded_by_user_id,
                _who(up_emp, uploader).label("uploaded_by_name"),
                PriceImport.uploaded_at,
                _who(co_emp, confirmer).label("confirmed_by_name"),
                PriceImport.confirmed_at,
                _who(ap_emp, approver).label("approved_by_name"),
                PriceImport.approved_at,
                _who(re_emp, rejecter).label("rejected_by_name"),
                PriceImport.rejected_at,
                PriceImport.decision_note,
                PriceImport.completed_at,
            )
            .outerjoin(PriceList, PriceList.id == PriceImport.price_list_id)
            .outerjoin(uploader, uploader.id == PriceImport.uploaded_by_user_id)
            .outerjoin(up_emp, up_emp.id == uploader.employee_id)
            .outerjoin(confirmer, confirmer.id == PriceImport.confirmed_by_user_id)
            .outerjoin(co_emp, co_emp.id == confirmer.employee_id)
            .outerjoin(approver, approver.id == PriceImport.approved_by_user_id)
            .outerjoin(ap_emp, ap_emp.id == approver.employee_id)
            .outerjoin(rejecter, rejecter.id == PriceImport.rejected_by_user_id)
            .outerjoin(re_emp, re_emp.id == rejecter.employee_id)
        )

    def _finish(self, batch: PriceImportBatch) -> PriceImportBatch:
        batch.has_file = bool(batch.has_file)
        batch.can_confirm = (
            batch.status == "Pending"
            and batch.changed_count > 0
            and batch.uploaded_by_user_id == self._actor.id
            and self._actor.can(PRICE_IMPORT)
        )
        batch.can_approve = batch.status == "Pending approval" and self._actor.can(PRICE_APPROVE)
        return batch


def _keep_what_was_shown(plan: list[Planned], preview: dict[int, PriceImportLine]) -> None:
    """Only a change the user saw is applied: if a row's current prices differ from the comparison shown
    (someone changed them since), or the row was not a change then, it fails instead."""
    for p in plan:
        if p.action != "Change":
            continue
        shown = preview.get(p.row.row_number)
        if shown is None or shown.action != "Change":
            p.error("This row was not a price change in the preview; upload the file again to include it.")
            continue
        was = {"selling": shown.old_selling, "purchase": shown.old_purchase, "mrp": shown.old_mrp}
        moved = [
            _LABELS[k] for k in p.changed()
            if not (p.old.get(k) is None and was[k] is None) and not _same(p.old.get(k), was[k])
        ]  # fmt: skip
        if moved:
            p.error(f"{', '.join(moved)} changed since the preview; upload the file again to see the new comparison.")


def _who(employee: Any, user: Any) -> Any:
    name = func.coalesce(employee.first_name, "") + " " + func.coalesce(employee.last_name, "")
    return func.coalesce(func.nullif(func.trim(name), ""), user.username)


def _line_out(line: PriceImportLine) -> PriceImportLineOut:
    return PriceImportLineOut(
        id=line.id,
        row_number=line.row_number,
        item_code=line.item_code,
        item_id=line.item_id,
        item_name=line.item_name,
        action=line.action,
        outcome=line.outcome,
        old_selling=line.old_selling,
        new_selling=line.new_selling,
        old_purchase=line.old_purchase,
        new_purchase=line.new_purchase,
        old_mrp=line.old_mrp,
        new_mrp=line.new_mrp,
        max_change_pct=line.max_change_pct,
        over_limit=bool(line.over_limit),
        reason=line.reason,
        messages=json.loads(line.messages) if line.messages else [],
    )
