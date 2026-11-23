"""Mobile face punches: the online challenge, online and offline punches, and the accept/review/reject rules.

The phone does its own face check (advisory, device_score); the server re-checks the photos against the
registered face and decides. Every punch is kept, Rejected ones too, with its evidence.

Decision, in order:
  Rejected  fake GPS, no face / several faces, score below the review line, challenge failed,
            nonce missing / expired / reused (online)
  Pending   score between the review and match lines, phone and server scores far apart, GPS weaker than
            the policy allows or missing, outside the office geofence, challenge not done when required,
            offline punch the policy doesn't auto-accept, offline punch older than allowed, phone clock ahead
  Present   everything passed
"""

from __future__ import annotations

import hashlib
import logging
import secrets
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from trishul_api.auth import CurrentUser
from trishul_api.common.errors import ApiError, Conflict, Forbidden
from trishul_api.db.models import (
    AttendanceChallenge,
    AttendancePolicy,
    AttendancePunch,
    EmployeeFace,
    FaceModel,
    WorkLocation,
)
from trishul_api.modules.hr.face_attendance.engine import (
    FaceAnalysis,
    FaceEngine,
    FloatVector,
    ImageUnreadable,
    similarity,
)
from trishul_api.modules.hr.face_attendance.protect import FaceVault
from trishul_api.modules.hr.face_attendance.rules import Geofence, india_date, nearest_geofence
from trishul_api.modules.hr.face_attendance.schemas import (
    ChallengeOut,
    PunchEvidence,
    PunchResultOut,
)
from trishul_api.modules.hr.face_attendance.service import FaceAttendanceService, utc_now

logger = logging.getLogger(__name__)

CHALLENGE_TTL = timedelta(minutes=2)
MAX_FRAMES = 3
MAX_FRAME_BYTES = 3 * 1024 * 1024
# A phone clock this far ahead of the server is not trusted for an offline punch.
CLOCK_AHEAD_LIMIT = timedelta(minutes=5)

_INSTRUCTIONS = {
    "None": "Look at the camera.",
    "Blink": "Look at the camera and blink.",
    "Blink, then turn left": "Look at the camera, blink, then turn your head to the left.",
    "Blink, then turn right": "Look at the camera, blink, then turn your head to the right.",
}


# --- the decision (pure) ------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Thresholds:
    match: float
    review: float
    max_score_gap: float
    max_gps_accuracy_m: float


@dataclass(slots=True)
class Facts:
    """What is known about one punch when the decision is made."""

    face_count: int
    server_score: float | None
    device_score: float | None = None
    challenge_required: bool = True
    challenge_result: str = "Not done"
    nonce_problem: str | None = None
    is_mock_location: bool = False
    has_location: bool = True
    gps_accuracy_m: float | None = None
    geofence_required: bool = False
    inside_geofence: bool | None = None
    offline: bool = False
    offline_auto_accept: bool = True
    offline_too_old: bool = False
    clock_ahead: bool = False
    reasons: list[str] = field(default_factory=list)


def decide(facts: Facts, limits: Thresholds) -> tuple[str, list[str]]:
    """("Present" | "Pending" | "Rejected", reasons in plain language)."""
    rejected: list[str] = []
    pending: list[str] = []

    if facts.nonce_problem:
        rejected.append(facts.nonce_problem)
    if facts.is_mock_location:
        rejected.append("A fake-location app was detected.")
    if facts.face_count == 0:
        rejected.append("No face was found in the photo.")
    elif facts.face_count > 1:
        rejected.append("More than one face was in the photo.")
    elif facts.server_score is None:
        rejected.append("The face could not be checked.")
    elif facts.server_score < limits.review:
        rejected.append("The face does not match the registered face.")
    elif facts.server_score < limits.match:
        pending.append("The face match is not certain.")
    if facts.challenge_result == "Failed":
        rejected.append("The blink / head-turn check failed.")
    elif facts.challenge_required and facts.challenge_result != "Passed":
        pending.append("The blink / head-turn check was not completed.")

    if (
        facts.device_score is not None
        and facts.server_score is not None
        and abs(facts.device_score - facts.server_score) > limits.max_score_gap
    ):
        pending.append("The phone's and the server's face scores differ.")
    if not facts.has_location:
        pending.append("No GPS location was sent.")
    elif facts.gps_accuracy_m is None or facts.gps_accuracy_m > limits.max_gps_accuracy_m:
        pending.append("The GPS signal was weak.")
    if facts.geofence_required and facts.has_location and not facts.inside_geofence:
        pending.append("The punch was outside the office area.")

    if facts.offline:
        if facts.clock_ahead:
            pending.append("The phone's clock was ahead of the real time.")
        if facts.offline_too_old:
            pending.append("The offline punch was sent too late.")
        if not facts.offline_auto_accept:
            pending.append("Offline punches are checked by HR.")

    if rejected:
        return "Rejected", rejected
    if pending:
        return "Pending", pending
    return "Present", []


# --- the service --------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Frame:
    data: bytes


class PunchService:
    def __init__(self, db: Session, engine: FaceEngine, vault: FaceVault) -> None:
        self._db = db
        self._engine = engine
        self._vault = vault
        self._setup = FaceAttendanceService(db)

    # --- challenge ----------------------------------------------------------------------

    def challenge(self, actor: CurrentUser, punch_type: str) -> ChallengeOut:
        employee_id = self._ready_employee(actor)
        policy = self._policy(employee_id)
        kind = policy.challenge
        if punch_type == "Out" and not policy.challenge_on_check_out:
            kind = "Blink" if kind != "None" else "None"
        if kind == "Blink and turn":
            kind = f"Blink, then turn {secrets.choice(['left', 'right'])}"
        now = utc_now()
        row = AttendanceChallenge(
            employee_id=employee_id,
            nonce=secrets.token_urlsafe(32),
            punch_type=punch_type,
            challenge=kind,
            issued_at=now,
            expires_at=now + CHALLENGE_TTL,
        )
        self._db.add(row)
        self._db.commit()
        return ChallengeOut(
            nonce=row.nonce,
            punch_type=punch_type,
            challenge=kind,
            instruction=_INSTRUCTIONS.get(kind, _INSTRUCTIONS["Blink"]),
            expires_at=row.expires_at,
            server_time=now,
        )

    # --- punches ------------------------------------------------------------------------

    def punch(
        self, actor: CurrentUser, evidence: PunchEvidence, frames: list[Frame], offline: bool, ip_address: str | None
    ) -> PunchResultOut:
        employee_id = self._require_employee(actor)
        existing = self._by_client_uuid(evidence.client_uuid)
        if existing is not None:
            if existing.employee_id != employee_id:
                raise Conflict("This punch id is already used.")
            return self._out(existing, already_received=True)

        today = self._setup.my_today(actor)
        if today.policy is None or today.face.status != "Active":
            raise Forbidden(today.blocked_reason or "Attendance cannot be marked yet.")
        policy = self._policy(employee_id)
        if offline and not policy.allow_offline:
            raise Forbidden("Offline punches are not allowed for you. Punch when the phone is online.")
        if not offline and evidence.punch_type != today.next_punch_type:
            word = "check-in" if today.next_punch_type == "In" else "check-out"
            raise Conflict(f"Your next punch is a {word}.")
        if not frames:
            raise ApiError("At least one photo is required.", errors={"frames": ["At least one photo is required."]})
        if len(frames) > MAX_FRAMES:
            raise ApiError(f"Send at most {MAX_FRAMES} photos.")
        if any(len(f.data) > MAX_FRAME_BYTES for f in frames):
            raise ApiError("Each photo must be 3 MB or smaller.")

        now = utc_now()
        facts = Facts(face_count=0, server_score=None, offline=offline)

        # Challenge: online punches must carry an unused nonce issued to this employee for this punch type.
        challenge_kind: str | None = None
        if not offline:
            challenge_kind, facts.nonce_problem = self._use_nonce(employee_id, evidence, now)
        facts.challenge_required = (challenge_kind or policy.challenge) != "None"
        facts.challenge_result = evidence.challenge_result

        # Face: the best-matching frame decides; a frame already used in an earlier punch is refused.
        model, registered = self._registered_vector(employee_id)
        frame_hashes = [hashlib.sha256(f.data).hexdigest() for f in frames]
        reused = self._reused_frame(employee_id, frame_hashes)
        best: FaceAnalysis | None = None
        best_score: float | None = None
        counts: list[int] = []
        for frame in frames:
            try:
                analysis = self._engine.analyse(frame.data)
            except ImageUnreadable as error:
                raise ApiError(str(error), errors={"frames": [str(error)]}) from error
            counts.append(analysis.face_count)
            if analysis.face_count == 1 and analysis.vector is not None:
                score = similarity(analysis.vector, registered)
                if best_score is None or score > best_score:
                    best, best_score = analysis, score
        facts.face_count = 1 if best is not None else (max(counts) if counts else 0)
        facts.server_score = best_score
        if reused:
            facts.nonce_problem = "A photo from an earlier punch was sent again."
        facts.device_score = float(evidence.device_score) if evidence.device_score is not None else None

        # Location.
        facts.is_mock_location = evidence.is_mock_location
        facts.has_location = evidence.latitude is not None and evidence.longitude is not None
        facts.gps_accuracy_m = float(evidence.gps_accuracy_m) if evidence.gps_accuracy_m is not None else None
        allowed = [loc.id for loc in today.work_locations]
        facts.geofence_required = policy.mode == "Office"
        hit = None
        if facts.has_location:
            assert evidence.latitude is not None and evidence.longitude is not None
            fences = self._fences(allowed if policy.mode != "Field" else None)
            hit = nearest_geofence(float(evidence.latitude), float(evidence.longitude), fences)
            facts.inside_geofence = hit.inside if hit is not None else None

        # Time.
        effective_at = now
        time_trust = "Server"
        if offline:
            captured = _naive_utc(evidence.device_captured_at)
            if captured is None:
                raise ApiError("An offline punch needs the time it was taken (deviceCapturedAt).")
            facts.clock_ahead = captured > now + CLOCK_AHEAD_LIMIT
            facts.offline_too_old = now - captured > timedelta(hours=policy.max_offline_hours)
            facts.offline_auto_accept = policy.offline_auto_accept
            effective_at = min(captured, now)
            time_trust = "Device unverified"

        limits = Thresholds(
            match=float(policy.match_threshold or model.default_match_threshold or Decimal("0.363")),
            review=float(policy.review_threshold or model.default_review_threshold or Decimal("0.30")),
            max_score_gap=float(policy.max_score_gap),
            max_gps_accuracy_m=float(policy.max_gps_accuracy_m),
        )
        status, reasons = decide(facts, limits)

        row = AttendancePunch(
            client_uuid=evidence.client_uuid,
            employee_id=employee_id,
            attendance_date=india_date(effective_at),
            punch_type=evidence.punch_type,
            device_captured_at=_naive_utc(evidence.device_captured_at),
            device_elapsed_ms=evidence.device_elapsed_ms,
            device_boot_id=evidence.device_boot_id,
            server_received_at=now,
            effective_at=effective_at,
            time_trust=time_trust,
            photo_s3_key=self._vault.store_photo("punches", employee_id, best.jpeg) if best is not None else None,
            photo_sha256=frame_hashes[0],
            frame_hashes=",".join(frame_hashes)[:1000],
            employee_face_id=self._active_face_id(employee_id),
            face_model_id=model.id,
            device_score=evidence.device_score,
            server_score=round(Decimal(str(best_score)), 4) if best_score is not None else None,
            face_status=_face_status(facts, limits),
            challenge=challenge_kind or policy.challenge,
            challenge_nonce=evidence.nonce if not offline else None,
            challenge_result=evidence.challenge_result,
            latitude=evidence.latitude,
            longitude=evidence.longitude,
            gps_accuracy_m=evidence.gps_accuracy_m,
            location_captured_at=_naive_utc(evidence.location_captured_at),
            is_mock_location=evidence.is_mock_location,
            work_location_id=hit.work_location_id if hit else None,
            distance_m=round(Decimal(str(hit.distance_m)), 1) if hit else None,
            inside_geofence=hit.inside if hit else None,
            device_id=evidence.device_id,
            platform=evidence.platform,
            os_version=evidence.os_version,
            app_version=evidence.app_version,
            integrity_verdict="Not checked" if evidence.integrity_token else None,
            keystore_signature=evidence.keystore_signature,
            ip_address=ip_address,
            capture_mode="Offline" if offline else "Online",
            status=status,
            status_reason=" ".join(reasons)[:300] or None,
            created_at=now,
            created_by_user_id=actor.id,
            is_active=True,
        )
        self._db.add(row)
        try:
            self._db.commit()
        except IntegrityError:
            # The same clientUuid arrived twice at once: return the one that was saved.
            self._db.rollback()
            existing = self._by_client_uuid(evidence.client_uuid)
            if existing is None:
                raise
            return self._out(existing, already_received=True)
        logger.info(
            "attendance.punch id=%s employee=%s type=%s mode=%s status=%s",
            row.id,
            employee_id,
            row.punch_type,
            row.capture_mode,
            status,
        )
        return self._out(row)

    # --- helpers --------------------------------------------------------------------------

    def _require_employee(self, actor: CurrentUser) -> int:
        if actor.employee_id is None:
            raise Forbidden("Your sign-in is not linked to an employee, so attendance cannot be marked.")
        return actor.employee_id

    def _ready_employee(self, actor: CurrentUser) -> int:
        today = self._setup.my_today(actor)
        if not today.can_punch:
            raise Forbidden(today.blocked_reason or "Attendance cannot be marked yet.")
        return today.employee_id

    def _policy(self, employee_id: int) -> AttendancePolicy:
        assignment = self._setup.get_employee_policy(employee_id)
        policy = self._db.get(AttendancePolicy, assignment.policy.id)
        assert policy is not None
        return policy

    def _use_nonce(self, employee_id: int, evidence: PunchEvidence, now: datetime) -> tuple[str | None, str | None]:
        if not evidence.nonce:
            return None, "The punch was not started from the app's camera screen."
        row = self._db.scalars(select(AttendanceChallenge).where(AttendanceChallenge.nonce == evidence.nonce)).first()
        if row is None or row.employee_id != employee_id or row.punch_type != evidence.punch_type:
            return None, "The punch was not started from the app's camera screen."
        if row.used_at is not None:
            return row.challenge, "This face check was already used. Start the punch again."
        row.used_at = now
        if row.expires_at < now:
            return row.challenge, "The face check took too long. Start the punch again."
        return row.challenge, None

    def _registered_vector(self, employee_id: int) -> tuple[FaceModel, FloatVector]:
        face = self._db.scalars(
            select(EmployeeFace).where(
                EmployeeFace.employee_id == employee_id,
                EmployeeFace.status == "Active",
                EmployeeFace.is_active == True,  # noqa: E712
            )
        ).first()
        if face is None or face.face_vector is None or face.face_model_id is None:
            raise Forbidden("Your face is not registered yet. Please contact HR.")
        model = self._db.get(FaceModel, face.face_model_id)
        assert model is not None
        return model, self._vault.open_vector(face.face_vector)

    def _active_face_id(self, employee_id: int) -> int | None:
        return self._db.scalar(
            select(EmployeeFace.id).where(
                EmployeeFace.employee_id == employee_id,
                EmployeeFace.status == "Active",
                EmployeeFace.is_active == True,  # noqa: E712
            )
        )

    def _reused_frame(self, employee_id: int, hashes: list[str]) -> bool:
        rows = self._db.scalars(
            select(AttendancePunch.frame_hashes).where(
                AttendancePunch.employee_id == employee_id,
                AttendancePunch.frame_hashes.is_not(None),
                AttendancePunch.effective_at >= utc_now() - timedelta(days=30),
            )
        ).all()
        seen = {h for row in rows if row for h in row.split(",")}
        return any(h in seen for h in hashes)

    def _fences(self, location_ids: list[int] | None) -> list[Geofence]:
        query = select(WorkLocation).where(WorkLocation.is_active == True)  # noqa: E712
        if location_ids is not None:
            if not location_ids:
                return []
            query = query.where(WorkLocation.id.in_(location_ids))
        return [
            Geofence(id=row.id, latitude=row.latitude, longitude=row.longitude, radius_m=row.radius_m)
            for row in self._db.scalars(query).all()
        ]

    def _by_client_uuid(self, client_uuid: str) -> AttendancePunch | None:
        return self._db.scalars(select(AttendancePunch).where(AttendancePunch.client_uuid == client_uuid)).first()

    def _out(self, row: AttendancePunch, already_received: bool = False) -> PunchResultOut:
        location_name = None
        if row.work_location_id:
            location_name = self._db.scalar(select(WorkLocation.name).where(WorkLocation.id == row.work_location_id))
        return PunchResultOut(
            id=row.id,
            client_uuid=row.client_uuid,
            punch_type=row.punch_type,
            status=row.status,
            status_reason=row.status_reason,
            message=_message(row),
            effective_at=row.effective_at,
            attendance_date=row.attendance_date,
            capture_mode=row.capture_mode,
            inside_geofence=row.inside_geofence,
            work_location_name=location_name,
            already_received=already_received,
        )


def _face_status(facts: Facts, limits: Thresholds) -> str:
    if facts.face_count == 0:
        return "No face"
    if facts.face_count > 1:
        return "Several faces"
    if facts.server_score is None:
        return "Not checked"
    return "Matched" if facts.server_score >= limits.match else "Below threshold"


def _message(row: AttendancePunch) -> str:
    what = "Check-in" if row.punch_type == "In" else "Check-out"
    if row.status == "Present":
        return f"{what} recorded."
    if row.status == "Pending":
        return f"{what} saved and sent to HR for review. {row.status_reason or ''}".strip()
    return f"{what} not accepted. {row.status_reason or ''}".strip()


def _naive_utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value
    return value.astimezone(UTC).replace(tzinfo=None)
