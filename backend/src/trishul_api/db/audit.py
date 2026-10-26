"""Writes core.audit_log for models marked Audited.

The schema has no triggers (docs/Trishul_DB_Gap_Analysis.md, 2.11), so the API records changes itself:
after each flush, one row per inserted, updated or deleted object, in the same transaction as the
change. A rollback therefore removes the audit rows too.
"""

import base64
import json
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any, Literal, TypedDict

from sqlalchemy import event, insert
from sqlalchemy.orm import Mapper, Session, UOWTransaction
from sqlalchemy.orm.attributes import instance_state

from trishul_api.db.models import AuditLog
from trishul_api.db.models.base import Audited

AuditSource = Literal["Web", "Android", "iOS", "API", "Sync", "System"]
Action = Literal["Insert", "Update", "Delete"]

_CONTEXT_KEY = "trishul.audit"
_MASK = "***"


class AuditContext(TypedDict):
    user_id: int | None
    source: AuditSource
    ip_address: str | None


def set_audit_context(session: Session, *, user_id: int | None, source: AuditSource, ip_address: str | None) -> None:
    """Turns auditing on for this session. Sessions without a context are not audited."""
    session.info[_CONTEXT_KEY] = AuditContext(user_id=user_id, source=source, ip_address=ip_address)


def _ignore_set(target: object, value: object, oldvalue: object, initiator: object) -> None:
    return None


@event.listens_for(Mapper, "mapper_configured")
def _keep_old_values(mapper: Mapper[Any], cls: type) -> None:
    # active_history loads an attribute's current value before it is overwritten, even when it
    # was expired (e.g. after a commit), so updates always record what they replaced.
    if issubclass(cls, Audited):
        for attr in mapper.column_attrs:
            event.listen(getattr(cls, attr.key), "set", _ignore_set, active_history=True)


@event.listens_for(Session, "after_flush")
def _write_audit_rows(session: Session, _flush: UOWTransaction) -> None:
    context: AuditContext | None = session.info.get(_CONTEXT_KEY)
    if context is None:
        return
    # In after_flush, new / dirty / deleted and attribute history still describe this flush,
    # and new objects already have their ids.
    changes: list[tuple[Audited, Action]] = [
        *((obj, "Insert") for obj in session.new if isinstance(obj, Audited)),
        *((obj, "Update") for obj in session.dirty if isinstance(obj, Audited)),
        *((obj, "Delete") for obj in session.deleted if isinstance(obj, Audited)),
    ]
    rows = [row for obj, action in changes if (row := _audit_row(obj, action, context)) is not None]
    if rows:
        session.execute(insert(AuditLog), rows)


def _audit_row(obj: Audited, action: Action, context: AuditContext) -> dict[str, Any] | None:
    state = instance_state(obj)
    loaded = state.dict  # read values without triggering loads in the middle of a flush
    old: dict[str, Any] = {}
    new: dict[str, Any] = {}
    for attr in state.mapper.column_attrs:
        column = attr.columns[0].name
        if column in obj.__audit_ignored__:
            continue
        if action == "Insert":
            if attr.key in loaded:  # server defaults (is_active, ...) are not loaded yet
                new[column] = loaded[attr.key]
            continue
        if action == "Delete":
            if attr.key in loaded:
                old[column] = loaded[attr.key]
            continue
        history = state.attrs[attr.key].history
        if history.has_changes():
            old[column] = history.deleted[0] if history.deleted else None
            new[column] = history.added[0] if history.added else None
    if action == "Update" and not new:
        return None  # only housekeeping columns changed
    for values in (old, new):
        for column in obj.__audit_masked__ & values.keys():
            values[column] = _MASK if values[column] is not None else None
    table = state.mapper.persist_selectable
    return {
        "entity_type": getattr(table, "fullname", str(table)),
        "entity_id": state.identity[0] if state.identity else getattr(obj, "id", None),
        "action": action,
        "old_values": _to_json(old) if old else None,
        "new_values": _to_json(new) if new else None,
        "changed_by_user_id": context["user_id"],
        "changed_at": datetime.now(UTC).replace(tzinfo=None),
        "source": context["source"],
        "ip_address": context["ip_address"],
    }


def _json_default(value: object) -> object:
    if isinstance(value, datetime | date):
        return value.isoformat()
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, bytes):
        return base64.b64encode(value).decode("ascii")
    return str(value)


def _to_json(values: dict[str, Any]) -> str:
    return json.dumps(values, default=_json_default, ensure_ascii=False, sort_keys=True)
