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


@dataclass(frozen=True)
class DocumentTarget:
    entity_type: str
    can_view: Check
    can_edit: Check
    max_documents: int = 20


_TARGETS: dict[str, DocumentTarget] = {}


def register_target(target: DocumentTarget) -> None:
    _TARGETS[target.entity_type] = target


def target_for(entity_type: str) -> DocumentTarget | None:
    return _TARGETS.get(entity_type)
