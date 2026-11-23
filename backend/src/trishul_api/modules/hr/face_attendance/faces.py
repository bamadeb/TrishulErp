"""Face registration by HR, approval by a second HR user, removal, and audited photo access.

A registration photo must show exactly one clear, well-lit face of a usable size, and must not match
another employee's registered face (one person registered twice, or the wrong employee chosen).
"""

from __future__ import annotations

import hashlib
import json
import logging
from collections.abc import Sequence
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from trishul_api.auth import CurrentUser
from trishul_api.common.concurrency import check_row_version
from trishul_api.common.errors import ApiError, Conflict, Forbidden, NotFound
from trishul_api.db.models import AttendanceAudit, Employee, EmployeeFace, FaceModel
from trishul_api.modules.hr.face_attendance.engine import FaceAnalysis, FaceEngine, ImageUnreadable, similarity
from trishul_api.modules.hr.face_attendance.protect import FaceVault
from trishul_api.modules.hr.face_attendance.schemas import FaceModelOut, FaceRecordStatus, FaceRegistrationOut
from trishul_api.modules.hr.face_attendance.service import utc_now

logger = logging.getLogger(__name__)

MAX_PHOTO_BYTES = 8 * 1024 * 1024

# Registration photo quality. A registered face is compared with every punch for months, so it must be
# better than a punch selfie. Starting values; the pilot tunes them.
MIN_CONFIDENCE = 0.85
MIN_FACE_WIDTH_PX = 100
# Laplacian variance of the 112x112 aligned face (engine.py). Measured 2026-11-23: sharp faces 300-1250 at any
# photo size, a webcam frame about 640, clearly blurred ones 7-45; 30 refuses only what is too soft to match.
MIN_SHARPNESS = 30.0
BRIGHTNESS_RANGE = (50.0, 215.0)

_LIVE = ("Pending approval", "Active")


class FaceRegistrationService:
    def __init__(self, db: Session, engine: FaceEngine | None = None, vault: FaceVault | None = None) -> None:
        """Listing needs neither; registering needs both, reading a photo or the vectors needs the vault."""
        self._db = db
        self._maybe_engine = engine
        self._maybe_vault = vault

    @property
    def _engine(self) -> FaceEngine:
        assert self._maybe_engine is not None, "built without a face engine"
        return self._maybe_engine

    @property
    def _vault(self) -> FaceVault:
        assert self._maybe_vault is not None, "built without a face vault"
        return self._maybe_vault

    # --- register -----------------------------------------------------------------

    def register(
        self, actor: CurrentUser, employee_id: int, photo: bytes, consent: bool, ip_address: str | None
    ) -> FaceRegistrationOut:
        employee = self._db.get(Employee, employee_id)
        if employee is None or not employee.is_active:
            raise NotFound("Employee not found.")
        if not consent:
            message = "The employee's consent to store their face for attendance is required."
            raise ApiError(message, errors={"consent": [message]})
        if not photo:
            raise ApiError("The photo is empty.")
        if len(photo) > MAX_PHOTO_BYTES:
            raise ApiError("The photo must be 8 MB or smaller.")
        model = self.current_model()

        try:
            analysis = self._engine.analyse(photo)
        except ImageUnreadable as error:
            raise ApiError(str(error), errors={"photo": [str(error)]}) from error
        problems = quality_problems(analysis)
        if problems:
            raise ApiError(" ".join(problems), errors={"photo": problems})
        assert analysis.vector is not None

        clash = self._matching_employee(employee_id, analysis, model)
        if clash is not None:
            code, score = clash
            message = (
                f"This face already matches the registered face of employee {code} (score {score:.2f}). "
                "Check that the right employee is selected."
            )
            raise ApiError(message, errors={"photo": [message]})

        now = utc_now()
        # A newer registration replaces one still waiting for approval; an Active face stays until approval.
        for old in self._faces(employee_id, ("Pending approval",)):
            old.status = "Superseded"
            old.updated_at = now
            old.updated_by_user_id = actor.id

        row = EmployeeFace(
            employee_id=employee_id,
            photo_s3_key=self._vault.store_photo("registered", employee_id, analysis.jpeg),
            photo_sha256=_sha256(analysis.jpeg),
            face_vector=self._vault.seal_vector(analysis.vector),
            face_model_id=model.id,
            face_confidence=_dec(analysis.confidence, 4),
            sharpness=_dec(analysis.sharpness, 2),
            brightness=_dec(analysis.brightness, 2),
            face_count=analysis.face_count,
            status="Pending approval",
            registered_by_user_id=actor.id,
            consent_at=now,
            created_at=now,
            created_by_user_id=actor.id,
            is_active=True,
        )
        self._db.add(row)
        self._db.flush()
        self._audit(actor, row.id, "Registered", {"employeeId": employee_id, "modelId": model.id}, ip_address)
        self._db.commit()
        logger.info("face.registered id=%s employee=%s actor=%s", row.id, employee_id, actor.id)
        return self._out(row)

    # --- approve / reject / remove ----------------------------------------------------

    def approve(self, actor: CurrentUser, face_id: int, ip_address: str | None) -> FaceRegistrationOut:
        row = self._require(face_id)
        if row.status != "Pending approval":
            raise Conflict(f"This registration is {row.status.lower()}, not waiting for approval.")
        if row.registered_by_user_id == actor.id:
            raise Forbidden("A different HR user must approve a face you registered.")
        now = utc_now()
        for old in self._faces(row.employee_id, ("Active",)):
            old.status = "Superseded"
            old.updated_at = now
            old.updated_by_user_id = actor.id
        self._db.flush()  # the filtered unique index allows one Active face per employee
        row.status = "Active"
        row.approved_by_user_id = actor.id
        row.approved_at = now
        row.updated_at = now
        row.updated_by_user_id = actor.id
        self._audit(actor, row.id, "Approved", {"employeeId": row.employee_id}, ip_address)
        self._db.commit()
        return self._out(row)

    def reject(self, actor: CurrentUser, face_id: int, reason: str, ip_address: str | None) -> FaceRegistrationOut:
        row = self._require(face_id)
        if row.status != "Pending approval":
            raise Conflict(f"This registration is {row.status.lower()}, not waiting for approval.")
        now = utc_now()
        row.status = "Rejected"
        row.rejection_reason = reason
        row.updated_at = now
        row.updated_by_user_id = actor.id
        self._audit(actor, row.id, "Rejected", {"reason": reason}, ip_address)
        self._db.commit()
        return self._out(row)

    def remove_face(self, actor: CurrentUser, face_id: int, row_version: bytes, ip_address: str | None) -> None:
        """Deletes one registration's face data (photo and vector); the row stays as history, status Deleted.
        Deleting the Active face leaves the employee unable to punch until a new face is approved."""
        row = self._require(face_id)
        if row.status == "Deleted":
            raise NotFound("This face registration is already deleted.")
        check_row_version(row.row_version, row_version)
        if row.photo_s3_key:
            self._vault.remove_photo(row.photo_s3_key)
        now = utc_now()
        row.photo_s3_key = None
        row.face_vector = None
        row.status = "Deleted"
        row.updated_at = now
        row.updated_by_user_id = actor.id
        self._audit(actor, row.id, "Deleted", {"employeeId": row.employee_id}, ip_address)
        self._db.commit()

    # --- read -------------------------------------------------------------------------

    def list_faces(self, status: FaceRecordStatus | None, employee_id: int | None) -> list[FaceRegistrationOut]:
        query = select(EmployeeFace).where(EmployeeFace.is_active == True)  # noqa: E712
        if status is not None:
            query = query.where(EmployeeFace.status == status)
        if employee_id is not None:
            query = query.where(EmployeeFace.employee_id == employee_id)
        rows = self._db.scalars(query.order_by(EmployeeFace.created_at.desc(), EmployeeFace.id.desc()).limit(500)).all()
        return self._outs(rows)

    def photo(self, actor: CurrentUser, face_id: int, ip_address: str | None) -> bytes:
        row = self._require(face_id)
        raw = self._vault.read_photo(row.photo_s3_key) if row.photo_s3_key else None
        if raw is None:
            raise NotFound("The photo is no longer stored.")
        self._audit(actor, row.id, "Photo viewed", None, ip_address)
        self._db.commit()
        return raw

    def face_models(self) -> list[FaceModelOut]:
        rows = self._db.scalars(
            select(FaceModel).where(FaceModel.is_active == True).order_by(FaceModel.kind, FaceModel.id)  # noqa: E712
        ).all()
        return [FaceModelOut.model_validate(row) for row in rows]

    def current_model(self) -> FaceModel:
        model = self._db.scalars(
            select(FaceModel).where(
                FaceModel.kind == "Face",
                FaceModel.is_current == True,  # noqa: E712
                FaceModel.is_active == True,  # noqa: E712
            )
        ).first()
        if model is None:
            raise ApiError("No face model is active. Face attendance is not switched on yet.")
        return model

    # --- helpers ----------------------------------------------------------------------

    def _matching_employee(
        self, employee_id: int, analysis: FaceAnalysis, model: FaceModel
    ) -> tuple[str, float] | None:
        """The best match among other employees' live faces (same model) at or above the match line."""
        assert analysis.vector is not None
        line = float(model.default_match_threshold or Decimal("0.363"))
        best: tuple[str, float] | None = None
        rows = self._db.execute(
            select(EmployeeFace.face_vector, Employee.employee_code)
            .join(Employee, Employee.id == EmployeeFace.employee_id)
            .where(
                EmployeeFace.employee_id != employee_id,
                EmployeeFace.status.in_(_LIVE),
                EmployeeFace.face_model_id == model.id,
                EmployeeFace.is_active == True,  # noqa: E712
                EmployeeFace.face_vector.is_not(None),
            )
        ).all()
        for sealed, code in rows:
            if sealed is None:
                continue
            score = similarity(analysis.vector, self._vault.open_vector(sealed))
            if score >= line and (best is None or score > best[1]):
                best = (code, score)
        return best

    def _faces(self, employee_id: int, statuses: tuple[str, ...]) -> list[EmployeeFace]:
        return list(
            self._db.scalars(
                select(EmployeeFace).where(
                    EmployeeFace.employee_id == employee_id,
                    EmployeeFace.status.in_(statuses),
                    EmployeeFace.is_active == True,  # noqa: E712
                )
            ).all()
        )

    def _require(self, face_id: int) -> EmployeeFace:
        row = self._db.get(EmployeeFace, face_id)
        if row is None or not row.is_active:
            raise NotFound("Face registration not found.")
        return row

    def _out(self, row: EmployeeFace) -> FaceRegistrationOut:
        return self._outs([row])[0]

    def _outs(self, rows: Sequence[EmployeeFace]) -> list[FaceRegistrationOut]:
        items = list(rows)
        employee_ids = {row.employee_id for row in items}
        model_ids = {row.face_model_id for row in items if row.face_model_id}
        employees = {
            r[0]: (r[1], " ".join(p for p in (r[2], r[3]) if p))
            for r in self._db.execute(
                select(Employee.id, Employee.employee_code, Employee.first_name, Employee.last_name).where(
                    Employee.id.in_(employee_ids or {0})
                )
            )
        }
        models = {
            r[0]: f"{r[1]} {r[2]}"
            for r in self._db.execute(
                select(FaceModel.id, FaceModel.code, FaceModel.version).where(FaceModel.id.in_(model_ids or {0}))
            )
        }
        return [
            FaceRegistrationOut(
                id=row.id,
                employee_id=row.employee_id,
                employee_code=employees.get(row.employee_id, (None, None))[0],
                employee_name=employees.get(row.employee_id, (None, None))[1] or None,
                status=row.status,
                face_confidence=row.face_confidence,
                sharpness=row.sharpness,
                brightness=row.brightness,
                face_model=models.get(row.face_model_id or 0),
                registered_by_user_id=row.registered_by_user_id,
                registered_at=row.created_at,
                approved_by_user_id=row.approved_by_user_id,
                approved_at=row.approved_at,
                rejection_reason=row.rejection_reason,
                consent_at=row.consent_at,
                row_version=row.row_version,
            )
            for row in items
        ]

    def _audit(
        self, actor: CurrentUser, face_id: int, action: str, details: dict[str, object] | None, ip_address: str | None
    ) -> None:
        self._db.add(
            AttendanceAudit(
                entity="face",
                entity_id=face_id,
                action=action,
                new_json=json.dumps(details, default=str) if details is not None else None,
                by_user_id=actor.id,
                at=utc_now(),
                ip_address=ip_address,
            )
        )


def quality_problems(analysis: FaceAnalysis) -> list[str]:
    """Plain-language reasons a registration photo can't be used; empty when it is fine."""
    if analysis.face_count == 0:
        return ["No face was found. Take the photo facing the camera, with the face fully visible."]
    if analysis.face_count > 1:
        return [f"{analysis.face_count} faces were found. Only the employee may be in the photo."]
    problems: list[str] = []
    if (analysis.confidence or 0) < MIN_CONFIDENCE:
        problems.append("The face is not clear enough. Remove sunglasses, mask or cap and face the camera.")
    if (analysis.face_width_px or 0) < MIN_FACE_WIDTH_PX:
        problems.append("The face is too small. Move closer so the face fills more of the photo.")
    if (analysis.sharpness or 0) < MIN_SHARPNESS:
        problems.append("The photo is blurred. Hold the phone steady and retake it.")
    low, high = BRIGHTNESS_RANGE
    brightness = analysis.brightness or 0
    if brightness < low:
        problems.append("The photo is too dark. Retake it in better light.")
    elif brightness > high:
        problems.append("The photo is too bright. Avoid direct light or a window behind the camera.")
    return problems


def _dec(value: float | None, places: int) -> Decimal | None:
    return None if value is None else round(Decimal(str(value)), places)


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()
