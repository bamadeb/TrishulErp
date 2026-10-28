"""Reads a Tata Hitachi SAP C4C / BYD service export (.xlsx) into normalized rows.

Two exports are supported, told apart by their columns:
  * "Service requests" - the "Before call assign" list (ticket logged, no engineer yet).
  * "Service orders"   - the "CALL_ASSIGNMENT List of Service Orders" (engineer assigned).

Both carry the C4C Ticket ID, which is the key the importer upserts on. The real header is not the
first row: a title and an "Last Updated On" line sit above it, so the header row is found by content.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
from io import BytesIO
from itertools import islice
from typing import Any, Literal

from openpyxl import load_workbook

from trishul_api.common.errors import ApiError

SourceKind = Literal["Service requests", "Service orders"]

# Columns that mark the header row (present in at least one of the two exports).
_HEADER_MARKERS = ("account", "subject")
_ORDER_MARKER = "service order id"
_REQUEST_MARKER = "service request id"
_MAX_HEADER_SCAN = 15


@dataclass(frozen=True)
class BydCallRow:
    """One service call from the export, with only the fields the importer uses."""

    row_number: int  # 1-based row in the sheet, for error messages
    c4c_ticket_id: str | None
    external_reference: str | None  # Service Order ID / Service Request ID, kept for traceability
    subject: str | None
    account: str | None
    registered_product_id: str | None
    reference_product: str | None
    priority: str | None
    is_breakdown: bool
    is_warranty: bool
    call_type_text: str | None
    is_cancelled: bool
    engineer_name: str | None
    caller_name: str | None
    caller_phone: str | None
    received_at: dt.datetime | None
    sla_due_at: dt.datetime | None


def parse_byd_export(content: bytes, *, max_rows: int = 5000) -> tuple[SourceKind, list[BydCallRow]]:
    """Returns the export kind and its rows. Raises ApiError if the file is not a recognizable export."""
    try:
        workbook = load_workbook(BytesIO(content), read_only=True, data_only=True)
    except Exception as exc:  # openpyxl raises a grab-bag of errors on a bad file
        raise ApiError("That file could not be read as an Excel (.xlsx) workbook.") from exc
    try:
        sheet = workbook.worksheets[0]
        grid = list(islice(sheet.iter_rows(values_only=True), max_rows + _MAX_HEADER_SCAN))
    finally:
        workbook.close()

    header_index = _find_header_row(grid)
    headers = _header_map(grid[header_index])
    kind: SourceKind = "Service orders" if _ORDER_MARKER in headers else "Service requests"

    rows: list[BydCallRow] = []
    for offset, raw in enumerate(grid[header_index + 1 :]):
        if raw is None or not any(_clean(cell) for cell in raw):
            continue  # blank spacer / trailing row
        rows.append(_build_row(raw, headers, kind, row_number=header_index + 2 + offset))
    return kind, rows


def _find_header_row(grid: list[tuple[Any, ...]]) -> int:
    for index, raw in enumerate(grid[:_MAX_HEADER_SCAN]):
        if raw is None:
            continue
        labels = {str(cell).strip().lower() for cell in raw if cell not in (None, "")}
        if all(marker in labels for marker in _HEADER_MARKERS) and (
            _ORDER_MARKER in labels or _REQUEST_MARKER in labels
        ):
            return index
    raise ApiError(
        "This doesn't look like a BYD service export. Upload the 'List of Service Orders' "
        "or 'Before call assign' file downloaded from the OEM portal."
    )


def _header_map(header: tuple[Any, ...]) -> dict[str, int]:
    mapping: dict[str, int] = {}
    for index, cell in enumerate(header):
        label = str(cell).strip().lower() if cell not in (None, "") else ""
        if label and label not in mapping:
            mapping[label] = index
    return mapping


def _build_row(raw: tuple[Any, ...], headers: dict[str, int], kind: SourceKind, *, row_number: int) -> BydCallRow:
    def value(*names: str) -> Any:
        for name in names:
            index = headers.get(name)
            if index is not None and index < len(raw):
                cell = raw[index]
                if cell not in (None, ""):
                    return cell
        return None

    external = value("service order id") if kind == "Service orders" else value("service request id")
    return BydCallRow(
        row_number=row_number,
        c4c_ticket_id=_clean(value("c4c ticket id")),
        external_reference=_clean(external),
        subject=_clean(value("subject")),
        account=_clean(value("account")),
        registered_product_id=_clean(value("registered product id")),
        reference_product=_clean(value("reference product", "registered product")),
        priority=_clean(value("priority")),
        is_breakdown=_is_yes(value("breakdown")),
        is_warranty=_is_yes(value("warranty")),
        call_type_text=_clean(value("type", "service category", "incident category")),
        is_cancelled=_is_yes(value("cancelled call")) or _is_canceled_status(value("cancellation status")),
        engineer_name=_clean_name(value("engineer name", "service performer")),
        caller_name=_clean(value("incoming caller name", "incoming caller", "reported by", "contact")),
        caller_phone=_clean_phone(value("incoming phone number")),
        received_at=_as_datetime(value("malfunction actual date & time", "reported on", "requested date")),
        sla_due_at=_as_datetime(value("completion by")),
    )


def _clean(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _clean_name(value: Any) -> str | None:
    """BYD engineer names carry trailing dots ('Satyajit Tung .'); drop them."""
    text = _clean(value)
    return text.rstrip(". ").strip() or None if text else None


def _clean_phone(value: Any) -> str | None:
    text = _clean(value)
    if text is None:
        return None
    digits = "".join(ch for ch in text if ch.isdigit())
    return (digits or text)[:15] or None


def _is_yes(value: Any) -> bool:
    return _clean(value) is not None and str(value).strip().lower() in {"yes", "y", "true", "1"}


def _is_canceled_status(value: Any) -> bool:
    text = _clean(value)
    return text is not None and "cancel" in text.lower() and "not" not in text.lower()


def _as_datetime(value: Any) -> dt.datetime | None:
    if isinstance(value, dt.datetime):
        return value.replace(tzinfo=None)
    if isinstance(value, dt.date):
        return dt.datetime(value.year, value.month, value.day)
    return None
