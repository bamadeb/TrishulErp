"""Complaint attachments use the shared document service (/core/documents, entityType 'core.complaint').

Who may see them: whoever may open the complaint (the person who raised it, the department's leaders, Super
Admins). Who may add or remove them: the person who raised it while it is open, the department's leaders until
it is closed. The file checks (type, content, 10 MB, no macros) are the document service's.
"""

from sqlalchemy import select
from sqlalchemy.orm import Session

from trishul_api.auth import CurrentUser
from trishul_api.db.models import Complaint, Department
from trishul_api.modules.core.documents.registry import DocumentTarget, register_target

ENTITY_TYPE = "core.complaint"


def _complaint(db: Session, complaint_id: int) -> Complaint | None:
    complaint = db.get(Complaint, complaint_id)
    return complaint if complaint is not None and complaint.is_active else None


def _can_view(db: Session, user: CurrentUser, complaint_id: int) -> bool:
    from trishul_api.modules.core.complaints.access import can_open

    complaint = _complaint(db, complaint_id)
    return complaint is not None and can_open(db, user, complaint)


def _can_edit(db: Session, user: CurrentUser, complaint_id: int) -> bool:
    from trishul_api.modules.core.complaints.service import ComplaintService

    complaint = _complaint(db, complaint_id)
    return (
        complaint is not None and _can_view(db, user, complaint_id) and ComplaintService(db, user).can_attach(complaint)
    )


def _exists(db: Session, _user: CurrentUser, complaint_id: int) -> bool:
    return _complaint(db, complaint_id) is not None


def _labels(db: Session, ids: list[int]) -> dict[int, str]:
    rows = db.execute(
        select(Complaint.id, Complaint.complaint_no, Department.name)
        .join(Department, Department.id == Complaint.department_id)
        .where(Complaint.id.in_(ids))
    )
    return {r.id: f"Complaint {r.complaint_no} · {r.name}" for r in rows}


register_target(
    DocumentTarget(
        entity_type=ENTITY_TYPE,
        label="Complaint",
        can_view=_can_view,
        can_edit=_can_edit,
        exists=_exists,
        describe=_labels,
        max_documents=10,
    )
)
