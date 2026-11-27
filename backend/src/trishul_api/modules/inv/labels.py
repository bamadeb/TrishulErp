"""Barcode labels as a PDF: bins (and yard spots), racks, items and GRN batches.

  roll   one 50 x 25 mm label per page, for a roll label printer;
  sheet  A4 sticker sheet, 3 columns x 8 rows of 70 x 37 mm.

A bin or rack label carries its code as Code128. An item label carries the item's primary barcode in its own
symbology (EAN-13, EAN-8, UPC-A, QR), else its item code as Code128: an item never needs a barcode to be labelled.
A GRN batch label carries the batch (lot) number as Code128 with the item and its GRN number and date: scanning it
finds that very receipt, so its age is counted from its own GRN date.
"""

from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO

from reportlab.graphics import renderPDF
from reportlab.graphics.barcode import createBarcodeDrawing
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.pdfgen import canvas
from sqlalchemy import select
from sqlalchemy.orm import Session

from trishul_api.auth import CurrentUser
from trishul_api.common.errors import ApiError
from trishul_api.db.models import Bin, Item, ItemBarcode, Location, Principal, StockLot, StorageRack
from trishul_api.modules.inv.barcode_schemas import LabelQuery
from trishul_api.modules.inv.common import visible_item, visible_location

_ROLL = (50 * mm, 25 * mm)
_SHEET_CELL = (70 * mm, 37 * mm)
_SHEET_COLS, _SHEET_ROWS = 3, 8
_MAX_LABELS = 2000
_SYMBOLOGY = {"EAN13": "EAN13", "EAN8": "EAN8", "UPCA": "UPCA", "QR": "QR"}


@dataclass
class Label:
    title: str
    lines: list[str]
    value: str
    symbology: str = "Code128"
    count: int = 1


def labels_pdf(db: Session, actor: CurrentUser, query: LabelQuery) -> tuple[str, bytes]:
    labels = _collect(db, actor, query)
    if not labels:
        raise ApiError("Nothing to label: choose bins, racks, items or GRN batches.")
    labels = [label for label in labels for _ in range(query.copies * label.count)]
    if len(labels) > _MAX_LABELS:
        raise ApiError(f"At most {_MAX_LABELS} labels at a time; choose fewer or print fewer copies.")
    buffer = BytesIO()
    if query.layout == "roll":
        pdf = canvas.Canvas(buffer, pagesize=_ROLL)
        for label in labels:
            _draw(pdf, label, 0, 0, *_ROLL)
            pdf.showPage()
    else:
        pdf = canvas.Canvas(buffer, pagesize=A4)
        width, height = _SHEET_CELL
        left = (A4[0] - _SHEET_COLS * width) / 2
        top = A4[1] - (A4[1] - _SHEET_ROWS * height) / 2
        for index, label in enumerate(labels):
            slot = index % (_SHEET_COLS * _SHEET_ROWS)
            if index and slot == 0:
                pdf.showPage()
            column, row = slot % _SHEET_COLS, slot // _SHEET_COLS
            _draw(pdf, label, left + column * width, top - (row + 1) * height, width, height)
        pdf.showPage()
    pdf.save()
    return f"{query.kind.lower()}-labels.pdf", buffer.getvalue()


def _collect(db: Session, actor: CurrentUser, query: LabelQuery) -> list[Label]:
    if query.kind == "Bin":
        statement = (
            select(Bin, Location.code, StorageRack.code)
            .join(Location, Location.id == Bin.location_id)
            .outerjoin(StorageRack, StorageRack.id == Bin.storage_rack_id)
            .where(Bin.is_active, visible_location(actor))
        )
        if query.storage_rack_ids:
            statement = statement.where(Bin.storage_rack_id.in_(query.storage_rack_ids))
        elif query.location_id is not None:
            statement = statement.where(Bin.location_id == query.location_id, Bin.storage_rack_id.is_(None))
        else:
            statement = statement.where(Bin.id.in_(query.ids or [0]))
        rows = db.execute(statement.order_by(Bin.storage_rack_id, Bin.level_no, Bin.position_no, Bin.code)).all()
        out = []
        for bin_, location_code, rack_code in rows:
            if rack_code:
                where = (
                    f"{location_code} · rack {bin_.rack or rack_code} · level {bin_.level_no} · bin {bin_.position_no}"
                )
            else:
                where = f"{location_code} · {bin_.bin_type.lower()}"
            out.append(Label(bin_.code, [where, bin_.description or ""], bin_.code))
        return out
    if query.kind == "Rack":
        racks = db.execute(
            select(StorageRack, Location.code)
            .join(Location, Location.id == StorageRack.location_id)
            .where(StorageRack.id.in_(query.ids or [0]), visible_location(actor))
            .order_by(StorageRack.code)
        ).all()
        return [
            Label(
                rack.code,
                [f"{location_code} · {rack.rack_type} {rack.short_code}", rack.name or f"{rack.levels} levels"],
                rack.code,
            )
            for rack, location_code in racks
        ]
    if query.kind == "Lot":
        statement = (
            select(StockLot, Item)
            .join(Item, Item.id == StockLot.item_id)
            .where(visible_item(actor))
            .order_by(StockLot.grn_date, StockLot.id)
        )
        if query.grn_id is not None:
            statement = statement.where(StockLot.grn_id == query.grn_id)
        else:
            statement = statement.where(StockLot.id.in_(query.ids or [0]))
        out = []
        for lot, item in db.execute(statement).all():
            units = max(1, min(500, int(lot.qty_received))) if query.one_per_unit else 1
            grn = f"GRN {lot.grn_no} · {lot.grn_date:%d-%m-%Y}"
            out.append(Label(f"{item.item_code} · {lot.lot_no}", [item.description, grn], lot.lot_no, count=units))
        return out
    items = db.execute(
        select(Item, Principal.code)
        .outerjoin(Principal, Principal.id == Item.principal_id)
        .where(Item.id.in_(query.ids or [0]), visible_item(actor))
        .order_by(Item.item_code)
    ).all()
    primary = {
        b.item_id: b
        for b in db.scalars(
            select(ItemBarcode).where(
                ItemBarcode.item_id.in_([i.id for i, _ in items] or [0]), ItemBarcode.is_primary, ItemBarcode.is_active
            )
        )
    }
    out = []
    for item, brand in items:
        barcode = primary.get(item.id)
        extra = " · ".join(x for x in (brand, f"Part {item.oem_part_number}" if item.oem_part_number else None) if x)
        if barcode is not None:
            out.append(
                Label(
                    item.item_code,
                    [item.description, extra],
                    barcode.barcode,
                    _SYMBOLOGY.get(barcode.barcode_type, "Code128"),
                )
            )
        else:
            out.append(Label(item.item_code, [item.description, extra], item.item_code))
    return out


def _fit(text: str, font: str, size: float, width: float) -> str:
    if stringWidth(text, font, size) <= width:
        return text
    while text and stringWidth(text + "…", font, size) > width:
        text = text[:-1]
    return text + "…"


def _draw(pdf: canvas.Canvas, label: Label, x: float, y: float, width: float, height: float) -> None:
    pad = 2.5 * mm
    inner = width - 2 * pad
    title_size = 10 if height < 30 * mm else 12
    pdf.setFont("Helvetica-Bold", title_size)
    pdf.drawString(x + pad, y + height - pad - title_size * 0.8, _fit(label.title, "Helvetica-Bold", title_size, inner))
    small = 6.5 if height < 30 * mm else 7.5
    pdf.setFont("Helvetica", small)
    line_y = y + height - pad - title_size - small * 0.9
    for line in label.lines[:2]:
        if line:
            pdf.drawString(x + pad, line_y, _fit(line, "Helvetica", small, inner))
            line_y -= small + 1
    bar_top = line_y - 1
    bar_height = max(bar_top - (y + pad), 6 * mm)
    try:
        if label.symbology == "QR":
            side = min(bar_height, inner)
            drawing = createBarcodeDrawing("QR", value=label.value, width=side, height=side)
            renderPDF.draw(drawing, pdf, x + pad, y + pad)
            return
        # No built-in quiet zones: the label's padding is the margin, which leaves the bars wider.
        drawing = createBarcodeDrawing(
            label.symbology, value=label.value, humanReadable=False, barHeight=bar_height, quiet=False
        )
    except Exception:  # an unprintable value in that symbology: fall back to Code128
        drawing = createBarcodeDrawing(
            "Code128", value=label.value, humanReadable=False, barHeight=bar_height, quiet=False
        )
    scale = min(1.0, inner / drawing.width) if drawing.width else 1.0
    drawing.scale(scale, 1)
    renderPDF.draw(drawing, pdf, x + pad + (inner - drawing.width * scale) / 2, y + pad)
