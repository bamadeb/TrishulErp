"""Which records can carry documents, and who may see or change them.

The document module knows nothing about travel, calls or invoices. A module registers a DocumentTarget
for its table (entity_type) and the module decides, for a given record, who may view and who may edit.
Adding documents to a new module is one register_target() call plus the shared UI component.
"""

from collections.abc import Callable
from dataclasses import dataclass

from sqlalchemy.orm import Session

from trishul_api.auth import CurrentUser

# (session, user, entity_id) -> allowed. Raise NotFound inside to hide a record the user cannot see.
Check = Callable[[Session, CurrentUser, int], bool]
# (session, entity ids) -> a short human label per id, for the document library ("BHADRAK/SC/00024 · Bus").
Describe = Callable[[Session, list[int]], dict[int, str]]
# (session, user, text typed by the person) -> up to `limit` (id, label) pairs the user may attach documents to.
Search = Callable[[Session, CurrentUser, str, int], list[tuple[int, str]]]


@dataclass(frozen=True)
class DocumentTarget:
    entity_type: str
    can_view: Check
    can_edit: Check
    exists: Check
    """Is there such a record? Administrators skip can_view/can_edit but not this."""
    label: str = ""
    """What the module calls this kind of record, e.g. "Manual travel"."""
    describe: Describe | None = None
    search: Search | None = None
    """Finds records by what the user types; without it the record cannot be chosen on the Documents page."""
    exclude_categories: tuple[str, ...] = ()
    """Attachment categories of this record type that are not documents (e.g. an employee's Photo)."""
    max_documents: int = 20


_TARGETS: dict[str, DocumentTarget] = {}


def register_target(target: DocumentTarget) -> None:
    _TARGETS[target.entity_type] = target


def target_for(entity_type: str) -> DocumentTarget | None:
    return _TARGETS.get(entity_type)


def registered_targets() -> list[DocumentTarget]:
    """Every record type that can carry documents, by name."""
    return sorted(_TARGETS.values(), key=lambda t: t.label or t.entity_type)
