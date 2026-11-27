"""Item barcodes and the scan / find lookup.

Barcodes are optional. An item is always found by its item code (which also prints as a Code128 barcode);
manufacturer and supplier barcodes are registered as they are, and an internal barcode is generated only when
someone asks for one. Every code people scan or type resolves to exactly one kind of thing because a barcode
may never equal an item code, a bin, rack or location code (checked here) or another barcode (unique index).

Scan lookup order: bin code, rack code, location code, item code, item barcode, manufacturer part number.
Every lookup is written to inv.scan_log.
"""

from __future__ import annotations

import re
from collections import defaultdict
from decimal import Decimal

from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from trishul_api.auth import CurrentUser
from trishul_api.common.concurrency import check_row_version
from trishul_api.common.errors import AlreadyExists, ApiError, NotFound
from trishul_api.db.models import (
    Bin,
    Item,
    ItemBarcode,
    Location,
    LotBalance,
    ScanLog,
    StockLot,
    StorageRack,
    Supplier,
    Uom,
)
from trishul_api.modules.inv.barcode_schemas import (
    BatchAge,
    ItemBarcodeCreate,
    ItemBarcodeOut,
    ItemBarcodeUpdate,
    ScanMatch,
    ScanResult,
)
from trishul_api.modules.inv.common import age_parts, age_text, now, today, visible_item, visible_location
from trishul_api.modules.inv.storage_schemas import BinStockQuery
from trishul_api.modules.inv.storage_service import StorageService

BARCODE_MANAGE = "inv.barcode.manage"
BARCODE_LINK = "inv.barcode.link"

_DIGITS = {"EAN13": 13, "EAN8": 8, "UPCA": 12}
_PRINTABLE = re.compile(r"^[\x20-\x7e]+$")
_STOCK_ROWS = 200


def _check_digit_ok(digits: str) -> bool:
    """GS1 check digit (EAN-13, EAN-8, UPC-A): weights 3 and 1 from the right, the last digit excluded."""
    body, check = digits[:-1], int(digits[-1])
    total = sum(int(d) * (3 if i % 2 == 0 else 1) for i, d in enumerate(reversed(body)))
    return (10 - total % 10) % 10 == check


def validate_barcode(value: str, barcode_type: str) -> str:
    """The barcode as it is kept (trimmed), or a 400 saying what is wrong with it."""
    text = value.strip()
    if not text:
        raise ApiError("Enter the barcode.", errors={"barcode": ["Required."]})
    length = _DIGITS.get(barcode_type)
    if length is not None:
        if not text.isdigit() or len(text) != length:
            raise ApiError(f"An {barcode_type} barcode is {length} digits.", errors={"barcode": [f"{length} digits."]})
        if not _check_digit_ok(text):
            raise ApiError(
                f"{text} is not a valid {barcode_type} barcode (its check digit is wrong). Scan it again.",
                errors={"barcode": ["Check digit does not match."]},
            )
    elif barcode_type == "Code128" and not _PRINTABLE.match(text):
        raise ApiError("A Code128 barcode holds letters, digits and symbols only.", errors={"barcode": ["Invalid."]})
    return text


class BarcodeService:
    def __init__(self, db: Session, actor: CurrentUser) -> None:
        self._db = db
        self._actor = actor

    # ------------------------------------------------------------------ item barcodes

    def list(self, item_id: int) -> list[ItemBarcodeOut]:
        item = self._item(item_id)
        rows = self._db.scalars(
            select(ItemBarcode)
            .where(ItemBarcode.item_id == item.id)
            .order_by(ItemBarcode.is_active.desc(), ItemBarcode.is_primary.desc(), ItemBarcode.id)
        ).all()
        return [ItemBarcodeOut.model_validate(r) for r in rows]

    def add(self, item_id: int, data: ItemBarcodeCreate) -> ItemBarcodeOut:
        item = self._item(item_id)
        value = validate_barcode(data.barcode, data.barcode_type)
        self._check_free(value, item)
        return self._insert(item, value, data.barcode_type, data.source, data.pack_qty, data.is_primary)

    def generate(self, item_id: int) -> ItemBarcodeOut:
        """An internal Code128 barcode TR + 8-digit item id, only for an item that has no active barcode."""
        item = self._item(item_id)
        existing = self._db.scalars(
            select(ItemBarcode).where(ItemBarcode.item_id == item.id, ItemBarcode.is_active)
        ).first()
        if existing is not None:
            raise ApiError(
                f"{item.item_code} already has the barcode {existing.barcode}; an internal one is only made for items "
                "without any. Its item code also prints as a barcode."
            )
        value = f"TR{item.id:08d}"
        self._check_free(value, item)
        return self._insert(item, value, "Code128", "Internal", Decimal(1), True)

    def update(self, barcode_id: int, expected: bytes, data: ItemBarcodeUpdate) -> ItemBarcodeOut:
        row = self._db.get(ItemBarcode, barcode_id)
        if row is None:
            raise NotFound("Barcode not found.")
        item = self._item(row.item_id)
        check_row_version(row.row_version, expected)
        if data.barcode_type is not None and data.barcode_type != row.barcode_type:
            validate_barcode(row.barcode, data.barcode_type)
            row.barcode_type = data.barcode_type
        if data.pack_qty is not None:
            row.pack_qty = data.pack_qty
        if data.is_active is not None:
            row.is_active = data.is_active
            if not data.is_active:
                row.is_primary = False
        if data.is_primary is True:
            if not row.is_active:
                raise ApiError("Only an active barcode can be the one printed on labels.")
            self._clear_primary(item.id, row.id)
            row.is_primary = True
        elif data.is_primary is False:
            row.is_primary = False
        row.updated_at = now()
        row.updated_by_user_id = self._actor.id
        self._commit("Another barcode of this item is already the primary one.")
        return ItemBarcodeOut.model_validate(row)

    def _insert(
        self, item: Item, value: str, barcode_type: str, source: str, pack_qty: Decimal, primary: bool
    ) -> ItemBarcodeOut:
        has_primary = self._db.scalar(
            select(ItemBarcode.id)
            .where(ItemBarcode.item_id == item.id, ItemBarcode.is_primary, ItemBarcode.is_active)
            .limit(1)
        )
        if primary:
            self._clear_primary(item.id, None)
        row = ItemBarcode(
            item_id=item.id,
            barcode=value,
            barcode_type=barcode_type,
            source=source,
            pack_qty=pack_qty,
            is_primary=primary or has_primary is None,  # the first barcode is printed unless another is chosen
            created_by_user_id=self._actor.id,
        )
        self._db.add(row)
        self._commit(f"The barcode {value} is already registered.")
        self._db.refresh(row)
        return ItemBarcodeOut.model_validate(row)

    def _clear_primary(self, item_id: int, keep_id: int | None) -> None:
        statement = update(ItemBarcode).where(ItemBarcode.item_id == item_id, ItemBarcode.is_primary)
        if keep_id is not None:
            statement = statement.where(ItemBarcode.id != keep_id)
        self._db.execute(statement.values(is_primary=False))

    def _check_free(self, value: str, item: Item) -> None:
        """A barcode may not equal another barcode, an item code, or a bin, rack or location code."""
        taken = self._db.execute(
            select(ItemBarcode.item_id, Item.item_code)
            .join(Item, Item.id == ItemBarcode.item_id)
            .where(ItemBarcode.barcode == value)
        ).first()
        if taken is not None:
            owner = "this item" if taken.item_id == item.id else f"item {taken.item_code}"
            raise AlreadyExists(f"The barcode {value} is already registered for {owner}.")
        upper = value.upper()
        code_of = self._db.scalar(select(Item.item_code).where(Item.item_code == upper).limit(1))
        if code_of is not None:
            if code_of == item.item_code:
                raise ApiError(f"{value} is this item's code, which already works as its barcode; nothing to add.")
            raise ApiError(f"{value} is the item code of {code_of}; it cannot also be a barcode.")
        for model, label in ((Bin, "bin"), (StorageRack, "rack"), (Location, "location")):
            if self._db.scalar(select(model.id).where(model.code == upper).limit(1)) is not None:
                raise ApiError(f"{value} is a {label} code; it cannot also be an item barcode.")

    def _item(self, item_id: int) -> Item:
        item = self._db.scalar(select(Item).where(Item.id == item_id, visible_item(self._actor)))
        if item is None:
            raise NotFound("Item not found.")
        return item

    def _commit(self, duplicate: str) -> None:
        try:
            self._db.flush()
            self._db.commit()
        except IntegrityError as error:
            self._db.rollback()
            raise AlreadyExists(duplicate) from error

    # ------------------------------------------------------------------ scan / find

    def scan(self, code: str, screen: str | None) -> ScanResult:
        value = code.strip()
        if not value:
            raise ApiError("Scan or type a code.", errors={"code": ["Required."]})
        upper = value.upper()
        matches: list[ScanMatch] = []

        for row in self._db.execute(
            select(Bin.id, Bin.code, Bin.description, Bin.location_id)
            .join(Location, Location.id == Bin.location_id)
            .where(Bin.code == upper, visible_location(self._actor))
        ).all():
            matches.append(ScanMatch(kind="Bin", id=row.id, code=row.code, name=row.description, via="Bin code",
                                     location_id=row.location_id))  # fmt: skip
        for rack in self._db.execute(
            select(StorageRack.id, StorageRack.code, StorageRack.name, StorageRack.location_id)
            .join(Location, Location.id == StorageRack.location_id)
            .where(StorageRack.code == upper, visible_location(self._actor))
        ).all():
            matches.append(ScanMatch(kind="Rack", id=rack.id, code=rack.code, name=rack.name, via="Rack code",
                                     location_id=rack.location_id))  # fmt: skip
        for place in self._db.execute(
            select(Location.id, Location.code, Location.name).where(
                Location.code == upper, visible_location(self._actor)
            )
        ).all():
            matches.append(ScanMatch(kind="Location", id=place.id, code=place.code, name=place.name,
                                     via="Location code", location_id=place.id))  # fmt: skip

        seen: set[int] = set()

        def add_item(item_id: int, item_code: str, name: str, via: str, pack: Decimal | None = None) -> None:
            if item_id not in seen:
                seen.add(item_id)
                matches.append(ScanMatch(kind="Item", id=item_id, code=item_code, name=name, via=via, pack_qty=pack))

        items = select(Item.id, Item.item_code, Item.description).where(visible_item(self._actor))
        for by_code in self._db.execute(items.where(Item.item_code == upper)).all():
            add_item(by_code.id, by_code.item_code, by_code.description, "Item code")
        for by_barcode in self._db.execute(
            select(Item.id, Item.item_code, Item.description, ItemBarcode.pack_qty, ItemBarcode.source)
            .join(ItemBarcode, ItemBarcode.item_id == Item.id)
            .where(ItemBarcode.barcode == value, ItemBarcode.is_active, visible_item(self._actor))
        ).all():
            add_item(
                by_barcode.id,
                by_barcode.item_code,
                by_barcode.description,
                f"{by_barcode.source} barcode",
                by_barcode.pack_qty,
            )
        for by_part in self._db.execute(items.where(Item.oem_part_number == value, Item.is_active).limit(20)).all():
            add_item(by_part.id, by_part.item_code, by_part.description, "Part number")
        # A GRN batch label carries the batch (lot) number.
        for lot in self._db.execute(
            select(StockLot.id, StockLot.lot_no, Item.item_code, Item.description)
            .join(Item, Item.id == StockLot.item_id)
            .where(StockLot.lot_no == upper, visible_item(self._actor))
        ).all():
            matches.append(
                ScanMatch(
                    kind="Lot",
                    id=lot.id,
                    code=lot.lot_no,
                    name=f"{lot.item_code} · {lot.description}",
                    via="Batch number",
                )
            )

        resolved = matches[0].kind if len(matches) == 1 else ("Many" if matches else "Unknown")
        stock, total, batches = [], 0, []
        if len(matches) == 1:
            one = matches[0]
            query = BinStockQuery(page_size=_STOCK_ROWS, sort="locationCode")
            if one.kind == "Lot":
                lot_item = self._db.scalar(select(StockLot.item_id).where(StockLot.id == one.id))
                query.item_id = lot_item
                batches = self.batch_ages(item_id=lot_item, lot_id=one.id)
            elif one.kind == "Item":
                batches = self.batch_ages(item_id=one.id)
                query.item_id = one.id
            elif one.kind == "Bin":
                query.bin_id, query.sort = one.id, "itemCode"
            elif one.kind == "Rack":
                query.storage_rack_id = one.id
            else:
                query.location_id = one.id
            page = StorageService(self._db, self._actor).bin_stock(query)
            stock, total = page.items, page.total
        self._db.add(
            ScanLog(
                scanned_at=now(),
                user_id=self._actor.id,
                scanned_value=value[:100],
                resolved_type=resolved,
                resolved_id=matches[0].id if len(matches) == 1 else None,
                match_count=len(matches),
                screen=(screen or "")[:40] or None,
            )
        )
        self._db.commit()
        return ScanResult(
            code=value, resolved_type=resolved, matches=matches, stock=stock, stock_total=total, batches=batches
        )

    def batch_ages(self, *, item_id: int, lot_id: int | None = None, limit: int = 100) -> list[BatchAge]:
        """An item's receipt batches still in stock where the user may see, oldest GRN first; each is aged from
        its own GRN date (never the item's creation date or its latest receipt)."""
        available = func.sum(LotBalance.qty_on_hand)
        statement = (
            select(
                StockLot.id,
                StockLot.lot_no,
                StockLot.item_id,
                Item.item_code,
                Item.description,
                Uom.code,
                StockLot.source_type,
                StockLot.grn_no,
                StockLot.grn_date,
                Supplier.name,
                StockLot.qty_received,
                available.label("available"),
            )
            .join(LotBalance, LotBalance.stock_lot_id == StockLot.id)
            .join(Location, Location.id == LotBalance.location_id)
            .join(Item, Item.id == StockLot.item_id)
            .join(Uom, Uom.id == Item.uom_id)
            .outerjoin(Supplier, Supplier.id == StockLot.supplier_id)
            .where(StockLot.item_id == item_id, LotBalance.qty_on_hand > 0, visible_location(self._actor))
            .group_by(
                StockLot.id,
                StockLot.lot_no,
                StockLot.item_id,
                Item.item_code,
                Item.description,
                Uom.code,
                StockLot.source_type,
                StockLot.grn_no,
                StockLot.grn_date,
                Supplier.name,
                StockLot.qty_received,
            )
            .order_by(StockLot.grn_date, StockLot.id)
            .limit(limit)
        )
        if lot_id is not None:
            statement = statement.where(StockLot.id == lot_id)
        rows = self._db.execute(statement).all()
        places: dict[int, list[str]] = defaultdict(list)
        for lot, location_code, bin_code, qty in self._db.execute(
            select(LotBalance.stock_lot_id, Location.code, Bin.code, LotBalance.qty_on_hand)
            .join(Location, Location.id == LotBalance.location_id)
            .outerjoin(Bin, Bin.id == LotBalance.bin_id)
            .where(
                LotBalance.stock_lot_id.in_([r[0] for r in rows] or [0]),
                LotBalance.qty_on_hand > 0,
                visible_location(self._actor),
            )
            .order_by(Location.code, Bin.code)
        ).all():
            places[lot].append(f"{location_code}{' · ' + bin_code if bin_code else ''}: {qty.normalize():f}")
        day = today()
        out = []
        for row in rows:
            years, months, days = age_parts(row.grn_date, day)
            out.append(
                BatchAge(
                    stock_lot_id=row[0],
                    lot_no=row.lot_no,
                    item_id=row.item_id,
                    item_code=row.item_code,
                    item_description=row.description,
                    uom_code=row.code,
                    source_type=row.source_type,
                    grn_no=row.grn_no,
                    grn_date=row.grn_date,
                    supplier_name=row.name,
                    qty_received=row.qty_received,
                    qty_available=row.available,
                    places=places[row[0]],
                    age_days=(day - row.grn_date).days,
                    age_years=years,
                    age_months=months,
                    age_rest_days=days,
                    age_text=age_text(row.grn_date, day),
                )
            )
        return out
