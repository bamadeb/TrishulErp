"""Encode/decode regularization request metadata into hr.attendance_regularization.reason.

The table has no dedicated columns for request type / requested times / rejection text,
so we keep a compact prefix and leave the free-text reason readable.
"""

from __future__ import annotations

from trishul_api.modules.hr.attendance.schemas import RegularizationRequestType

_TYPES: tuple[RegularizationRequestType, ...] = (
    "Missed Punch",
    "Wrong Attendance",
    "Early Exit",
    "WFH Correction",
    "Late Arrival",
    "Holiday Work",
)

_TYPE_TO_STATUS = {
    "Missed Punch": "Present",
    "Wrong Attendance": "Present",
    "Early Exit": "Present",
    "WFH Correction": "On duty",
    "Late Arrival": "Present",
    "Holiday Work": "Present",
}


def requested_status_for(request_type: RegularizationRequestType) -> str:
    return _TYPE_TO_STATUS[request_type]


def encode_reason(
    *,
    request_type: RegularizationRequestType,
    requested_in: str | None,
    requested_out: str | None,
    reason: str,
    rejection_reason: str | None = None,
) -> str:
    head = f"[{request_type}|{requested_in or ''}|{requested_out or ''}]"
    body = reason.strip()
    if rejection_reason and rejection_reason.strip():
        body = f"{body}\n[RJ]{rejection_reason.strip()}"
    text = f"{head}{body}"
    return text[:300]


def decode_reason(raw: str) -> tuple[RegularizationRequestType, str | None, str | None, str, str | None]:
    text = (raw or "").strip()
    request_type: RegularizationRequestType = "Missed Punch"
    requested_in: str | None = None
    requested_out: str | None = None
    rejection: str | None = None
    body = text

    if text.startswith("[") and "]" in text:
        meta, body = text[1:].split("]", 1)
        parts = meta.split("|")
        if parts and parts[0] in _TYPES:
            request_type = parts[0]  # type: ignore[assignment]
        if len(parts) > 1 and parts[1].strip():
            requested_in = parts[1].strip()
        if len(parts) > 2 and parts[2].strip():
            requested_out = parts[2].strip()

    if "\n[RJ]" in body:
        body, _, rej = body.partition("\n[RJ]")
        rejection = rej.strip() or None
    elif body.startswith("[RJ]"):
        rejection = body[4:].strip() or None
        body = ""

    return request_type, requested_in, requested_out, body.strip(), rejection
