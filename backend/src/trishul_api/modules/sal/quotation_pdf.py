"""The sales quotation as a PDF, in the same OEM layout as the web print page
(frontend quotation-print.page.ts): logo / branch block, quotation number and date, billing and delivery
address, customer code and GSTIN, the line grid with CGST / SGST / IGST, charge rows, totals and the amount
in words. A4 landscape. The numbers come from QuotationDetail (the same data the web page prints); only the
per-line split into gross / discount / GST parts is worked out here, with the same rules as the web page.
"""

import io
import re
from dataclasses import dataclass
from typing import Any
from decimal import ROUND_HALF_UP, Decimal
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_RIGHT
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfgen.canvas import Canvas
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from trishul_api.modules.sal.quotation_schemas import QuotationDetail

_BLUE = colors.HexColor("#00338d")
_RED = colors.HexColor("#cc0000")
_CENT = Decimal("0.01")
_ZERO = Decimal(0)
_MARGIN = 8 * mm
_WIDTH = landscape(A4)[0] - 2 * _MARGIN

_BASE = ParagraphStyle("base", fontName="Helvetica", fontSize=7.4, leading=9.2)
_BOLD = ParagraphStyle("bold", parent=_BASE, fontName="Helvetica-Bold")
_CENTER = ParagraphStyle("center", parent=_BASE, alignment=TA_CENTER)
_RIGHT = ParagraphStyle("right", parent=_BASE, alignment=TA_RIGHT)
_HEAD = ParagraphStyle("head", parent=_BASE, alignment=TA_CENTER, fontSize=6.8, leading=8)
_TITLE = ParagraphStyle("title", parent=_BASE, fontName="Helvetica-Bold", fontSize=15, leading=18, alignment=TA_RIGHT)
_COMPANY = ParagraphStyle("company", parent=_CENTER, fontName="Helvetica-Bold", fontSize=9, leading=11)


def _round2(value: Decimal) -> Decimal:
    return value.quantize(_CENT, rounding=ROUND_HALF_UP)


def inr(value: Decimal | None) -> str:
    """Indian price format: 12,34,567.89."""
    number = _round2(value or _ZERO)
    sign = "-" if number < 0 else ""
    whole, _, cents = f"{abs(number):.2f}".partition(".")
    if len(whole) > 3:
        head, tail = whole[:-3], whole[-3:]
        head = re.sub(r"(\d)(?=(\d{2})+$)", r"\1,", head)
        whole = f"{head},{tail}"
    return f"{sign}{whole}.{cents}"


def _plain(value: Decimal, places: int) -> str:
    """12.5 -> '12.5', 9.0 -> '9' (at most `places` decimals, no trailing zeros)."""
    text = f"{value:.{places}f}".rstrip("0").rstrip(".")
    return text or "0"


def _p(text: object, style: ParagraphStyle = _BASE) -> Paragraph:
    return Paragraph(escape("" if text is None else str(text)), style)


def _lines_of(address: str | None) -> list[str]:
    """An address entered on one line with commas prints one part per line (as on the web page)."""
    return [part.strip() for part in re.split(r"\r?\n|,\s*", address or "") if part.strip()]


@dataclass
class _Line:
    gross: Decimal
    discount: Decimal
    net: Decimal
    rate: Decimal
    cgst: Decimal
    sgst: Decimal
    igst: Decimal
    total: Decimal


def _split(quotation: QuotationDetail) -> list[_Line]:
    inter_state = quotation.igst > 0
    rows: list[_Line] = []
    for line in quotation.lines:
        gross = _round2(line.quantity * line.unit_price)
        tax = line.tax_amount
        half = _round2(tax / 2)
        rows.append(
            _Line(
                gross=gross,
                discount=_round2(gross - line.taxable_value),
                net=line.taxable_value,
                rate=line.gst_pct,
                cgst=_ZERO if inter_state else half,
                sgst=_ZERO if inter_state else _round2(tax - half),
                igst=tax if inter_state else _ZERO,
                total=line.line_total,
            )
        )
    return rows


def file_name_of(quotation_no: str) -> str:
    return "Quotation-" + re.sub(r"[^A-Za-z0-9._-]+", "-", quotation_no).strip("-") + ".pdf"


def render(quotation: QuotationDetail) -> bytes:
    """The quotation as PDF bytes."""
    q = quotation
    parts = _split(q)
    story: list[object] = []

    # Logo (brand name in a blue box when there is no logo image), our branch, title
    brand = Table(
        [[_p(q.principal_name.upper(), ParagraphStyle("brand", parent=_BOLD, textColor=colors.white, fontSize=11))]],
        colWidths=[_WIDTH * 0.2],
        hAlign="LEFT",
    )
    brand.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), _BLUE), ("LEFTPADDING", (0, 0), (-1, -1), 8)]))
    company: list[object] = [_p(q.company_name, _COMPANY), _p(q.company_name, _CENTER)]
    company += [_p(part, _CENTER) for part in _lines_of(q.branch_address or q.company_address)]
    if q.branch_phone:
        company.append(_p(f"Mobile: {q.branch_phone}", _CENTER))
    if q.branch_email:
        company.append(_p(f"Email : {q.branch_email}", _CENTER))
    title: list[object] = [_p("Sales Quotation", _TITLE)]
    if q.state in ("Draft", "Pending approval"):
        stamp = Table(
            [[_p("DRAFT", ParagraphStyle("stamp", parent=_BOLD, textColor=_RED, fontSize=10))]],
            colWidths=[18 * mm],
            hAlign="RIGHT",
        )
        stamp.setStyle(TableStyle([("BOX", (0, 0), (-1, -1), 1.5, _RED)]))
        title.append(stamp)
    top = Table([[brand, company, title]], colWidths=[_WIDTH * 0.22, _WIDTH * 0.40, _WIDTH * 0.38])
    top.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("BOX", (0, 0), (-1, -1), 0.6, colors.black)]))
    story.append(top)

    # Quotation number / date / customer ref
    number = q.quotation_no + (f" (Rev {q.current_version})" if q.current_version > 1 else "")
    ids = Table(
        [
            ["", _p("Quotation Number", _BOLD), _p("Quotation Date", _BOLD), _p("Customer Ref No", _BOLD)],
            [
                "",
                _p(number, _CENTER),
                _p(q.quotation_date.strftime("%d-%b-%y"), _CENTER),
                _p(q.customer_oem_code or "", _CENTER),
            ],
        ],
        colWidths=[_WIDTH * 0.50, _WIDTH * 0.20, _WIDTH * 0.15, _WIDTH * 0.15],
    )
    ids.setStyle(
        TableStyle([("GRID", (1, 0), (-1, -1), 0.5, colors.black), ("BOX", (0, 0), (-1, -1), 0.6, colors.black)])
    )
    story.append(ids)

    # Billing / delivery / customer / terms
    attention = f" Mr. {q.customer_contact_name}" if q.customer_contact_name else ""
    billing: list[object] = [_p(f"Billing Address :{attention}"), _p(q.customer_name)]
    billing += [_p(part) for part in _lines_of(q.billing_address)]
    delivery: list[object] = [_p(f"Delivery Address : {q.customer_site_name or q.customer_name}")]
    delivery += [_p(part) for part in _lines_of(q.delivery_address)]
    customer: list[object] = [
        Paragraph(f"<b>Customer Code :</b> {escape(q.customer_code)}", _BASE),
        Paragraph(f"<b>Customer Name :</b> {escape(q.customer_name)}", _BASE),
        Spacer(1, 14),
        Paragraph(f"<b>GST Registration Number:</b> {escape(q.customer_gstin or '')}", _BASE),
        Paragraph(f"<b>GST Registration Type :</b> {escape(q.customer_gst_type or '')}", _BASE),
    ]
    terms: list[object] = [
        _p("Shipping Terms:", _BOLD),
        Paragraph(f"<b>Payment Terms:</b> {escape(q.payment_terms or '')}", _BASE),
        Spacer(1, 8),
        _p("Contact Details :", _BOLD),
        Paragraph(f"<b>Name :</b> {escape(q.contact_name or q.created_by or '')}", _BASE),
        Paragraph(f"<b>Contact Number :</b> {escape(q.contact_phone or '')}", _BASE),
        Paragraph(f"<b>E-Mail:</b> {escape(q.contact_email or '')}", _BASE),
    ]
    parties = Table(
        [[billing, delivery, customer, terms]],
        colWidths=[_WIDTH * 0.22, _WIDTH * 0.24, _WIDTH * 0.28, _WIDTH * 0.26],
        rowHeights=[None],
    )
    parties.setStyle(TableStyle([("GRID", (0, 0), (-1, -1), 0.5, colors.black), ("VALIGN", (0, 0), (-1, -1), "TOP")]))
    story.append(parties)

    # The line grid: 17 columns, two header rows
    widths_mm = [9, 44, 16, 11, 10, 20, 22, 17, 12, 20, 10, 16, 10, 16, 10, 16, 22]
    widths = [w * mm * (_WIDTH / (sum(widths_mm) * mm)) for w in widths_mm]
    head = [
        "Sno", "Item Code/Product Description", "HSN/SAC Code", "Qty", "UOM", "Unit Price [INR]",
        "Total Before Discount [INR]", "Discount [INR]", "Discount (%)", "Net Price (INR)",
        "CGST [INR]", "", "SGST [INR]", "", "IGST [INR]", "", "Line Total [INR]",
    ]  # fmt: skip
    sub = ["", "", "", "", "", "", "", "", "", "", "Rate", "Amount", "Rate", "Amount", "Rate", "Amount", ""]
    rows: list[list[Any]] = [[_p(h, _HEAD) if h else "" for h in head], [_p(s, _HEAD) if s else "" for s in sub]]
    for line, calc in zip(q.lines, parts, strict=True):
        code = f"{line.item_code}/" if line.item_code else ""
        rows.append(
            [
                _p(line.line_no, _CENTER),
                _p(f"{code}{line.description}", _CENTER),
                _p(line.hsn_code or "", _CENTER),
                _p(_plain(line.quantity, 3), _CENTER),
                _p(line.uom_code or "", _CENTER),
                _p(inr(line.unit_price), _RIGHT),
                _p(inr(calc.gross), _RIGHT),
                _p(inr(-calc.discount) if calc.discount else "", _RIGHT),
                _p(f"{-line.discount_pct:.2f}" if line.discount_pct else "", _RIGHT),
                _p(inr(calc.net), _RIGHT),
                _p(_plain(calc.rate / 2, 2) if calc.cgst else "", _CENTER),
                _p(inr(calc.cgst) if calc.cgst else "", _RIGHT),
                _p(_plain(calc.rate / 2, 2) if calc.sgst else "", _CENTER),
                _p(inr(calc.sgst) if calc.sgst else "", _RIGHT),
                _p(_plain(calc.rate, 2) if calc.igst else "", _CENTER),
                _p(inr(calc.igst) if calc.igst else "", _RIGHT),
                _p(inr(calc.total), _RIGHT),
            ]
        )
    body_end = len(rows)

    def total_of(pick: str) -> Decimal:
        return _round2(sum((getattr(c, pick) for c in parts), _ZERO))

    blank: list[Any] = [""] * 17
    charges: list[Any] = list(blank)
    charges[1] = [_p("Frieght [INR]"), Spacer(1, 4), _p("Insurance [INR]"), Spacer(1, 4), _p("TCS%")]
    charges[16] = _p(inr(q.other_charges) if q.other_charges else "", _RIGHT)
    packing: list[Any] = list(blank)
    packing[1] = _p("Packing and Forwarding Expenses [INR]")
    totals: list[Any] = list(blank)
    totals[0] = _p("Total Amount [INR]", _BOLD)
    totals[6] = _p(inr(total_of("gross")), ParagraphStyle("r1", parent=_RIGHT, fontName="Helvetica-Bold"))
    totals[7] = _p(inr(total_of("discount")), ParagraphStyle("r2", parent=_RIGHT, fontName="Helvetica-Bold"))
    totals[9] = _p(inr(total_of("net")), ParagraphStyle("r3", parent=_RIGHT, fontName="Helvetica-Bold"))
    bold_right = ParagraphStyle("br", parent=_RIGHT, fontName="Helvetica-Bold")
    totals[10] = _p(inr(total_of("cgst")) if total_of("cgst") else "", bold_right)
    totals[12] = _p(inr(total_of("sgst")) if total_of("sgst") else "", bold_right)
    totals[14] = _p(inr(total_of("igst")) if total_of("igst") else "", bold_right)
    totals[16] = _p(inr(q.rounded_total), bold_right)
    remarks: list[Any] = list(blank)
    remarks[0] = _p(f"Remarks : {q.terms or ''}")
    words: list[Any] = list(blank)
    words[0] = _p(f"Amount In Words : (INR) {q.amount_in_words}")
    words[10] = _p("Total [INR]", _BOLD)
    words[14] = _p(inr(q.rounded_total), bold_right)
    rows += [blank, charges, packing, totals, blank, remarks, words]

    grid = Table(rows, colWidths=widths, repeatRows=2)
    t = body_end  # the first row after the lines
    grid.setStyle(
        TableStyle(
            [
                ("GRID", (0, 0), (-1, -1), 0.5, colors.black),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("VALIGN", (0, 0), (-1, 1), "MIDDLE"),
                ("LEFTPADDING", (0, 0), (-1, -1), 3),
                ("RIGHTPADDING", (0, 0), (-1, -1), 3),
                ("TOPPADDING", (0, 0), (-1, -1), 2),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
                # header: spanned cells
                *[("SPAN", (c, 0), (c, 1)) for c in (0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 16)],
                ("SPAN", (10, 0), (11, 0)),
                ("SPAN", (12, 0), (13, 0)),
                ("SPAN", (14, 0), (15, 0)),
                # charge rows have no inner horizontal lines, like the web page
                ("LINEBELOW", (0, t), (-1, t), 0.5, colors.white),
                ("LINEBELOW", (0, t + 1), (-1, t + 1), 0.5, colors.white),
                ("LINEABOVE", (0, t + 2), (-1, t + 2), 0.5, colors.white),
                # totals row
                ("SPAN", (0, t + 3), (5, t + 3)),
                ("SPAN", (10, t + 3), (11, t + 3)),
                ("SPAN", (12, t + 3), (13, t + 3)),
                ("SPAN", (14, t + 3), (15, t + 3)),
                ("SPAN", (0, t + 4), (16, t + 4)),
                ("SPAN", (0, t + 5), (9, t + 5)),
                ("SPAN", (10, t + 5), (16, t + 5)),
                ("SPAN", (0, t + 6), (9, t + 6)),
                ("SPAN", (10, t + 6), (13, t + 6)),
                ("SPAN", (14, t + 6), (16, t + 6)),
            ]
        )
    )
    story.append(grid)

    footer = "  ".join(
        part
        for part in (
            f"Ph No : {q.branch_phone}" if q.branch_phone else "",
            f"Email ID : {q.branch_email}" if q.branch_email else "",
        )
        if part
    )
    if footer:
        story.append(Spacer(1, 4))
        story.append(_p(footer, _CENTER))

    buffer = io.BytesIO()
    document = SimpleDocTemplate(
        buffer,
        pagesize=landscape(A4),
        leftMargin=_MARGIN,
        rightMargin=_MARGIN,
        topMargin=_MARGIN,
        bottomMargin=_MARGIN + 6 * mm,
        title=f"Quotation {q.quotation_no}",
        author=q.company_name,
    )
    document.build(story, canvasmaker=_NumberedCanvas)
    return buffer.getvalue()


class _NumberedCanvas(Canvas):  # type: ignore[misc]
    """Writes "Page n of N" bottom right on every page."""

    def __init__(self, *args: object, **kwargs: object) -> None:
        super().__init__(*args, **kwargs)
        self._saved: list[dict[str, object]] = []

    def showPage(self) -> None:
        self._saved.append(dict(self.__dict__))
        self._startPage()

    def save(self) -> None:
        total = len(self._saved)
        for state in self._saved:
            self.__dict__.update(state)
            self.setFont("Helvetica", 7.4)
            self.drawRightString(landscape(A4)[0] - _MARGIN, _MARGIN, f"Page {self._pageNumber} of {total}")
            super().showPage()
        super().save()
