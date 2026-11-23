"""Face attendance set-up (work locations, policies, employee assignment) and the employee's day."""

from __future__ import annotations

import json
import logging
from collections.abc import Iterable
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from typing import Any

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from trishul_api.auth import CurrentUser
from trishul_api.common.concurrency import check_row_version
from trishul_api.common.errors import AlreadyExists, ApiError, Forbidden, NotFound
from trishul_api.db.models import (
    AttendanceAudit,
    AttendancePolicy,
    AttendancePunch,
    Branch,
    Employee,
    EmployeeAttendanceLocation,
    EmployeeAttendancePolicy,
    EmployeeFace,
    FaceModel,
    WorkLocation,
)
from trishul_api.modules.hr.face_attendance.rules import india_date
from trishul_api.modules.hr.face_attendance.schemas import (
    AttendancePolicyCreate,
    AttendancePolicyOut,
    AttendancePolicyUpdate,
    EmployeePolicyAssign,
    EmployeePolicyOut,
    MyAttendanceTodayOut,
    MyFaceOut,
    MyPunchOut,
    WorkLocationCreate,
    WorkLocationOut,
    WorkLocationUpdate,
    _check_thresholds,
)

logger = logging.getLogger(__name__)

# Faces that still stand for the employee (newest first decides what the phone shows).
_LIVE_FACE = ("Pending approval", "Active", "Rejected")


def utc_now() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


class FaceAttendanceService:
    def __init__(self, db: Session) -> None:
        self._db = db

    # --- work locations ----------------------------------------------------------

    def list_work_locations(
        self, branch_id: int | None = None, include_inactive: bool = False
    ) -> list[WorkLocationOut]:
        query = select(WorkLocation).order_by(WorkLocation.name, WorkLocation.id)
        if branch_id is not None:
            query = query.where(WorkLocation.branch_id == branch_id)
        if not include_inactive:
            query = query.where(WorkLocation.is_active == True)  # noqa: E712
        return self._location_outs(self._db.scalars(query).all())

    def create_work_location(self, actor: CurrentUser, data: WorkLocationCreate) -> WorkLocationOut:
        self._require_branch(data.branch_id)
        row = WorkLocation(**data.model_dump(), created_by_user_id=actor.id, created_at=utc_now(), is_active=True)
        self._db.add(row)
        self._db.flush()
        self._audit(actor, "location", row.id, "Created", None, data.model_dump(mode="json"))
        self._db.commit()
        return self._location_outs([row])[0]

    def update_work_location(
        self, actor: CurrentUser, location_id: int, data: WorkLocationUpdate, row_version: bytes
    ) -> WorkLocationOut:
        row = self._db.get(WorkLocation, location_id)
        if row is None:
            raise NotFound("Work location not found.")
        check_row_version(row.row_version, row_version)
        changes = data.model_dump(exclude_unset=True)
        if "branch_id" in changes:
            self._require_branch(changes["branch_id"])
        old = {key: _jsonable(getattr(row, key)) for key in changes}
        for key, value in changes.items():
            setattr(row, key, value)
        row.updated_at = utc_now()
        row.updated_by_user_id = actor.id
        self._audit(actor, "location", row.id, "Updated", old, data.model_dump(mode="json", exclude_unset=True))
        self._db.commit()
        return self._location_outs([row])[0]

    def _location_outs(self, rows: Iterable[WorkLocation]) -> list[WorkLocationOut]:
        rows = list(rows)
        branch_ids = {row.branch_id for row in rows if row.branch_id is not None}
        names: dict[int, str] = {}
        if branch_ids:
            names = {
                r[0]: r[1] for r in self._db.execute(select(Branch.id, Branch.name).where(Branch.id.in_(branch_ids)))
            }
        return [
            WorkLocationOut.model_validate(row).model_copy(update={"branch_name": names.get(row.branch_id or 0)})
            for row in rows
        ]

    def _require_branch(self, branch_id: int | None) -> None:
        if branch_id is not None and self._db.get(Branch, branch_id) is None:
            raise NotFound("Branch not found.")

    # --- policies ----------------------------------------------------------------

    def list_policies(self, include_inactive: bool = False) -> list[AttendancePolicyOut]:
        query = select(AttendancePolicy).order_by(AttendancePolicy.code)
        if not include_inactive:
            query = query.where(AttendancePolicy.is_active == True)  # noqa: E712
        rows = self._db.scalars(query).all()
        today = india_date(utc_now())
        counts: dict[int, int] = {
            r[0]: r[1]
            for r in self._db.execute(
                select(EmployeeAttendancePolicy.policy_id, func.count())
                .where(_assignment_on(today))
                .group_by(EmployeeAttendancePolicy.policy_id)
            )
        }
        return [_policy_out(row, counts.get(row.id, 0)) for row in rows]

    def create_policy(self, actor: CurrentUser, data: AttendancePolicyCreate) -> AttendancePolicyOut:
        exists = self._db.scalar(select(AttendancePolicy.id).where(AttendancePolicy.code == data.code))
        if exists is not None:
            raise AlreadyExists(f"An attendance policy with code '{data.code}' already exists.")
        row = AttendancePolicy(**data.model_dump(), created_by_user_id=actor.id, created_at=utc_now(), is_active=True)
        self._db.add(row)
        self._db.flush()
        self._audit(actor, "policy", row.id, "Created", None, data.model_dump(mode="json"))
        self._db.commit()
        return _policy_out(row, 0)

    def update_policy(
        self, actor: CurrentUser, policy_id: int, data: AttendancePolicyUpdate, row_version: bytes
    ) -> AttendancePolicyOut:
        row = self._db.get(AttendancePolicy, policy_id)
        if row is None:
            raise NotFound("Attendance policy not found.")
        check_row_version(row.row_version, row_version)
        changes = data.model_dump(exclude_unset=True)
        try:
            _check_thresholds(
                changes.get("match_threshold", row.match_threshold),
                changes.get("review_threshold", row.review_threshold),
            )
        except ValueError as error:
            raise ApiError(str(error), errors={"reviewThreshold": [str(error)]}) from error
        old = {key: _jsonable(getattr(row, key)) for key in changes}
        for key, value in changes.items():
            setattr(row, key, value)
        row.updated_at = utc_now()
        row.updated_by_user_id = actor.id
        self._audit(actor, "policy", row.id, "Updated", old, data.model_dump(mode="json", exclude_unset=True))
        self._db.commit()
        return _policy_out(row, 0)

    # --- employee assignment -----------------------------------------------------

    def get_employee_policy(self, employee_id: int, day: date | None = None) -> EmployeePolicyOut:
        self._require_employee(employee_id)
        out = self._employee_policy(employee_id, day or india_date(utc_now()))
        if out is None:
            raise NotFound("No attendance policy is set for this employee.")
        return out

    def assign_employee_policy(
        self, actor: CurrentUser, employee_id: int, data: EmployeePolicyAssign
    ) -> EmployeePolicyOut:
        self._require_employee(employee_id)
        policy = self._db.get(AttendancePolicy, data.policy_id)
        if policy is None or not policy.is_active:
            raise NotFound("Attendance policy not found.")
        location_ids = sorted(set(data.work_location_ids))
        if location_ids:
            found = self._db.scalars(
                select(WorkLocation.id).where(WorkLocation.id.in_(location_ids), WorkLocation.is_active == True)  # noqa: E712
            ).all()
            missing = sorted(set(location_ids) - set(found))
            if missing:
                raise NotFound(f"Work location not found: {', '.join(map(str, missing))}.")
        if policy.mode == "Office" and not location_ids:
            message = "An Office policy needs at least one work location."
            raise ApiError(message, errors={"workLocationIds": [message]})

        now = utc_now()
        # Close what was in force on the new start date; drop assignments that hadn't started yet.
        for row in self._db.scalars(
            select(EmployeeAttendancePolicy).where(
                EmployeeAttendancePolicy.employee_id == employee_id,
                EmployeeAttendancePolicy.is_active == True,  # noqa: E712
                or_(EmployeeAttendancePolicy.to_date.is_(None), EmployeeAttendancePolicy.to_date >= data.from_date),
            )
        ).all():
            if row.from_date >= data.from_date:
                row.is_active = False
            else:
                row.to_date = data.from_date - timedelta(days=1)
            row.updated_at = now
            row.updated_by_user_id = actor.id

        assignment = EmployeeAttendancePolicy(
            employee_id=employee_id,
            policy_id=policy.id,
            from_date=data.from_date,
            created_by_user_id=actor.id,
            created_at=now,
            is_active=True,
        )
        self._db.add(assignment)
        self._db.flush()
        for location_id in location_ids:
            self._db.add(
                EmployeeAttendanceLocation(employee_attendance_policy_id=assignment.id, work_location_id=location_id)
            )
        self._audit(
            actor,
            "assignment",
            assignment.id,
            "Assigned",
            None,
            data.model_dump(mode="json") | {"employeeId": employee_id},
        )
        self._db.commit()
        out = self._employee_policy(employee_id, data.from_date)
        assert out is not None
        return out

    def _employee_policy(self, employee_id: int, day: date) -> EmployeePolicyOut | None:
        assignment = self._db.scalars(
            select(EmployeeAttendancePolicy)
            .where(EmployeeAttendancePolicy.employee_id == employee_id, _assignment_on(day))
            .order_by(EmployeeAttendancePolicy.from_date.desc(), EmployeeAttendancePolicy.id.desc())
            .limit(1)
        ).first()
        if assignment is None:
            return None
        policy = self._db.get(AttendancePolicy, assignment.policy_id)
        assert policy is not None
        locations = self._db.scalars(
            select(WorkLocation)
            .join(EmployeeAttendanceLocation, EmployeeAttendanceLocation.work_location_id == WorkLocation.id)
            .where(
                EmployeeAttendanceLocation.employee_attendance_policy_id == assignment.id,
                WorkLocation.is_active == True,  # noqa: E712
            )
            .order_by(WorkLocation.name)
        ).all()
        return EmployeePolicyOut(
            id=assignment.id,
            employee_id=employee_id,
            policy=_policy_out(policy, 0),
            from_date=assignment.from_date,
            to_date=assignment.to_date,
            work_locations=self._location_outs(locations),
        )

    def _require_employee(self, employee_id: int) -> Employee:
        employee = self._db.get(Employee, employee_id)
        if employee is None:
            raise NotFound("Employee not found.")
        return employee

    # --- the employee's day ------------------------------------------------------

    def my_today(self, actor: CurrentUser) -> MyAttendanceTodayOut:
        if actor.employee_id is None:
            raise Forbidden("Your sign-in is not linked to an employee, so attendance cannot be marked.")
        now = utc_now()
        today = india_date(now)
        assignment = self._employee_policy(actor.employee_id, today)
        face = self._my_face(actor.employee_id)
        model = self._db.scalars(
            select(FaceModel).where(
                FaceModel.kind == "Face",
                FaceModel.is_current == True,  # noqa: E712
                FaceModel.is_active == True,  # noqa: E712
            )
        ).first()
        punches = self._db.scalars(
            select(AttendancePunch)
            .where(
                AttendancePunch.employee_id == actor.employee_id,
                AttendancePunch.attendance_date == today,
                AttendancePunch.is_active == True,  # noqa: E712
            )
            .order_by(AttendancePunch.effective_at, AttendancePunch.id)
        ).all()
        location_names = {loc.id: loc.name for loc in (assignment.work_locations if assignment else [])}
        counted = [p for p in punches if p.status != "Rejected"]
        next_type = "Out" if counted and counted[-1].punch_type == "In" else "In"

        blocked: str | None = None
        if assignment is None:
            blocked = "HR has not set an attendance policy for you yet."
        elif face.status == "Not registered":
            blocked = "Your face is not registered yet. Please contact HR."
        elif face.status == "Pending approval":
            blocked = "Your face registration is waiting for HR approval."
        elif face.status == "Rejected":
            blocked = "Your face registration was rejected. Please contact HR to register again."
        elif model is None:
            blocked = "Face attendance is not switched on yet."

        return MyAttendanceTodayOut(
            server_time=now,
            attendance_date=today,
            employee_id=actor.employee_id,
            can_punch=blocked is None,
            blocked_reason=blocked,
            next_punch_type=next_type,
            policy=assignment.policy if assignment else None,
            work_locations=assignment.work_locations if assignment else [],
            face=face,
            face_model_version=f"{model.code} {model.version}" if model else None,
            punches=[
                MyPunchOut(
                    id=p.id,
                    punch_type=p.punch_type,
                    effective_at=p.effective_at,
                    status=p.status,
                    status_reason=p.status_reason,
                    capture_mode=p.capture_mode,
                    inside_geofence=p.inside_geofence,
                    work_location_name=location_names.get(p.work_location_id or 0),
                )
                for p in punches
            ],
        )

    def _my_face(self, employee_id: int) -> MyFaceOut:
        face = self._db.scalars(
            select(EmployeeFace)
            .where(
                EmployeeFace.employee_id == employee_id,
                EmployeeFace.is_active == True,  # noqa: E712
                EmployeeFace.status.in_(_LIVE_FACE),
            )
            .order_by(EmployeeFace.created_at.desc(), EmployeeFace.id.desc())
            .limit(1)
        ).first()
        if face is None:
            return MyFaceOut(status="Not registered")
        return MyFaceOut(
            status=face.status,
            registered_at=face.created_at,
            rejection_reason=face.rejection_reason if face.status == "Rejected" else None,
        )

    # --- audit -------------------------------------------------------------------

    def _audit(
        self,
        actor: CurrentUser,
        entity: str,
        entity_id: int,
        action: str,
        old: dict[str, Any] | None,
        new: dict[str, Any] | None,
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
            )
        )


def _assignment_on(day: date) -> Any:
    return (
        (EmployeeAttendancePolicy.is_active == True)  # noqa: E712
        & (EmployeeAttendancePolicy.from_date <= day)
        & or_(EmployeeAttendancePolicy.to_date.is_(None), EmployeeAttendancePolicy.to_date >= day)
    )


def _policy_out(row: AttendancePolicy, employee_count: int) -> AttendancePolicyOut:
    return AttendancePolicyOut.model_validate(row).model_copy(update={"employee_count": employee_count})


def _jsonable(value: Any) -> Any:
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, date | datetime):
        return value.isoformat()
    return value
