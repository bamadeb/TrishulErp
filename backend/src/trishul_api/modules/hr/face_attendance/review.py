"""HR's side of punches: the list / review queue, the decision on a doubtful punch, the audited punch photo,
and the employee's own face template for offline matching on the phone.

Who sees which punches: hr.attendance.manage sees everyone; hr.attendance.view.team sees their own punches
and the employees who report to them; hr.attendance.mark alone sees only the signed-in employee.
"""

from __future__ import annotations

import base64
import json
from datetime import date
from decimal import Decimal

import numpy as np
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from trishul_api.auth import CurrentUser
from trishul_api.common.errors import Conflict, Forbidden, NotFound
from trishul_api.db.models import (
    AttendanceAudit,
    AttendancePolicy,
    AttendancePunch,
    Branch,
    Department,
    Employee,
    EmployeeFace,
    FaceModel,
    WorkLocation,
)
from trishul_api.modules.hr.face_attendance.protect import FaceVault
from trishul_api.modules.hr.face_attendance.rules import india_date
from trishul_api.modules.hr.face_attendance.schemas import FaceTemplateOut, PunchListItemOut, PunchStatus
from trishul_api.modules.hr.face_attendance.service import FaceAttendanceService, utc_now

MANAGE = "hr.attendance.manage"


class PunchReviewService:
    def __init__(self, db: Session, vault: FaceVault | None = None) -> None:
        self._db = db
        self._maybe_vault = vault

    @property
    def _vault(self) -> FaceVault:
        assert self._maybe_vault is not None, "built without a face vault"
        return self._maybe_vault

    # --- list -----------------------------------------------------------------------------

    def list_punches(
        self,
        actor: CurrentUser,
        status: PunchStatus | None,
        from_date: date | None,
        to_date: date | None,
        employee_id: int | None,
        limit: int,
    ) -> list[PunchListItemOut]:
        query = select(AttendancePunch).where(AttendancePunch.is_active == True)  # noqa: E712
        if status is not None:
            query = query.where(AttendancePunch.status == status)
        if from_date is not None:
            query = query.where(AttendancePunch.attendance_date >= from_date)
        if to_date is not None:
            query = query.where(AttendancePunch.attendance_date <= to_date)
        if employee_id is not None:
            query = query.where(AttendancePunch.employee_id == employee_id)
        if MANAGE not in actor.permissions and "*" not in actor.permissions:
            if "hr.attendance.view.team" in actor.permissions:
                team = select(Employee.id).where(
                    or_(
                        Employee.reporting_manager_id == (actor.employee_id or 0),
                        Employee.id == (actor.employee_id or 0),
                    )
                )
                query = query.where(AttendancePunch.employee_id.in_(team))
            else:
                query = query.where(AttendancePunch.employee_id == (actor.employee_id or 0))
        rows = self._db.scalars(
            query.order_by(AttendancePunch.effective_at.desc(), AttendancePunch.id.desc()).limit(limit)
        ).all()
        return self._outs(list(rows))

    # --- review -----------------------------------------------------------------------------

    def review(
        self, actor: CurrentUser, punch_id: int, decision: str, remarks: str, ip_address: str | None
    ) -> PunchListItemOut:
        row = self._require(punch_id)
        if row.status != "Pending":
            raise Conflict(f"This punch is {row.status.lower()}; only punches waiting for review can be decided.")
        if actor.employee_id is not None and actor.employee_id == row.employee_id:
            raise Forbidden("You cannot review your own punch.")
        now = utc_now()
        old = row.status
        row.status = decision
        row.reviewed_by_user_id = actor.id
        row.reviewed_at = now
        row.review_remarks = remarks
        row.updated_at = now
        row.updated_by_user_id = actor.id
        self._audit(
            actor, "punch", row.id, "Reviewed", {"status": old}, {"status": decision, "remarks": remarks}, ip_address
        )
        self._db.commit()
        return self._outs([row])[0]

    # --- photos and templates ----------------------------------------------------------------

    def photo(self, actor: CurrentUser, punch_id: int, ip_address: str | None) -> bytes:
        row = self._require(punch_id)
        if MANAGE not in actor.permissions and "*" not in actor.permissions:
            manager = self._db.scalar(select(Employee.reporting_manager_id).where(Employee.id == row.employee_id))
            if manager is None or manager != actor.employee_id:
                raise NotFound("Punch not found.")
        raw = self._vault.read_photo(row.photo_s3_key) if row.photo_s3_key else None
        if raw is None:
            raise NotFound("The photo is no longer stored.")
        self._audit(actor, "punch", row.id, "Photo viewed", None, None, ip_address)
        self._db.commit()
        return raw

    def my_template(self, actor: CurrentUser, ip_address: str | None) -> FaceTemplateOut:
        if actor.employee_id is None:
            raise Forbidden("Your sign-in is not linked to an employee.")
        face = self._db.scalars(
            select(EmployeeFace).where(
                EmployeeFace.employee_id == actor.employee_id,
                EmployeeFace.status == "Active",
                EmployeeFace.is_active == True,  # noqa: E712
            )
        ).first()
        if face is None or face.face_vector is None or face.face_model_id is None:
            raise NotFound("Your face is not registered yet.")
        model = self._db.get(FaceModel, face.face_model_id)
        assert model is not None
        vector = self._vault.open_vector(face.face_vector)
        policy_out = FaceAttendanceService(self._db)._employee_policy(actor.employee_id, india_date(utc_now()))
        policy = self._db.get(AttendancePolicy, policy_out.policy.id) if policy_out else None
        match = (policy.match_threshold if policy else None) or model.default_match_threshold or Decimal("0.363")
        review = (policy.review_threshold if policy else None) or model.default_review_threshold or Decimal("0.30")
        self._audit(actor, "face", face.id, "Template downloaded", None, None, ip_address)
        self._db.commit()
        return FaceTemplateOut(
            face_id=face.id,
            model_code=model.code,
            model_version=model.version,
            vector_size=int(vector.size),
            vector=base64.b64encode(np.asarray(vector, dtype="<f4").tobytes()).decode("ascii"),
            match_threshold=match,
            review_threshold=review,
        )

    # --- helpers ------------------------------------------------------------------------------

    def _require(self, punch_id: int) -> AttendancePunch:
        row = self._db.get(AttendancePunch, punch_id)
        if row is None or not row.is_active:
            raise NotFound("Punch not found.")
        return row

    def _outs(self, rows: list[AttendancePunch]) -> list[PunchListItemOut]:
        employee_ids = {r.employee_id for r in rows} or {0}
        location_ids = {r.work_location_id for r in rows if r.work_location_id} or {0}
        employees = {
            r[0]: (r[1], " ".join(p for p in (r[2], r[3]) if p) or None, r[4], r[5])
            for r in self._db.execute(
                select(
                    Employee.id,
                    Employee.employee_code,
                    Employee.first_name,
                    Employee.last_name,
                    Department.name,
                    Branch.name,
                )
                .outerjoin(Department, Department.id == Employee.department_id)
                .outerjoin(Branch, Branch.id == Employee.branch_id)
                .where(Employee.id.in_(employee_ids))
            )
        }
        locations = {
            r[0]: r[1]
            for r in self._db.execute(
                select(WorkLocation.id, WorkLocation.name).where(WorkLocation.id.in_(location_ids))
            )
        }
        return [
            PunchListItemOut(
                id=r.id,
                employee_id=r.employee_id,
                employee_code=employees.get(r.employee_id, (None, None, None, None))[0],
                employee_name=employees.get(r.employee_id, (None, None, None, None))[1],
                attendance_date=r.attendance_date,
                punch_type=r.punch_type,
                effective_at=r.effective_at,
                capture_mode=r.capture_mode,
                status=r.status,
                status_reason=r.status_reason,
                face_status=r.face_status,
                server_score=r.server_score,
                device_score=r.device_score,
                challenge=r.challenge,
                challenge_result=r.challenge_result,
                latitude=r.latitude,
                longitude=r.longitude,
                gps_accuracy_m=r.gps_accuracy_m,
                is_mock_location=r.is_mock_location,
                inside_geofence=r.inside_geofence,
                distance_m=r.distance_m,
                work_location_name=locations.get(r.work_location_id or 0),
                platform=r.platform,
                department_name=employees.get(r.employee_id, (None, None, None, None))[2],
                branch_name=employees.get(r.employee_id, (None, None, None, None))[3],
                time_trust=r.time_trust,
                has_photo=bool(r.photo_s3_key),
                reviewed_by_user_id=r.reviewed_by_user_id,
                reviewed_at=r.reviewed_at,
                review_remarks=r.review_remarks,
            )
            for r in rows
        ]

    def _audit(
        self,
        actor: CurrentUser,
        entity: str,
        entity_id: int,
        action: str,
        old: dict[str, object] | None,
        new: dict[str, object] | None,
        ip_address: str | None,
    ) -> None:
        self._db.add(
            AttendanceAudit(
                entity=entity,
                entity_id=entity_id,
                action=action,
                old_json=json.dumps(old, default=str) if old is not None else None,
                new_json=json.dumps(new, default=str) if new is not None else None,
                by_user_id=actor.id,
                at=utc_now(),
                ip_address=ip_address,
            )
        )
