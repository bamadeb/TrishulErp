"""Face attendance routes: HR set-up and the signed-in employee's day.

Paths sit under /hr/attendance next to the Daily Attendance page's /hr/attendance/daily
(modules/hr/attendance), which shows these punches together with the biometric ones.
"""

import logging
from datetime import date
from pathlib import Path as FsPath
from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, Path, Query, Request, Response, UploadFile
from pydantic import ValidationError

from trishul_api.auth import CurrentUserDep, DbSession, require_permission
from trishul_api.common.concurrency import if_match_row_version
from trishul_api.common.errors import CONCURRENCY_RESPONSES, NOT_FOUND_RESPONSE, ApiError
from trishul_api.config import Settings, get_settings
from trishul_api.modules.hr.face_attendance.engine import FaceEngine, FaceEngineUnavailable, load_engine
from trishul_api.modules.hr.face_attendance.faces import MAX_PHOTO_BYTES, FaceRegistrationService
from trishul_api.modules.hr.face_attendance.protect import FaceDataKeyMissing, FaceVault, load_key
from trishul_api.modules.hr.face_attendance.punches import MAX_FRAME_BYTES, MAX_FRAMES, Frame, PunchService
from trishul_api.modules.hr.face_attendance.review import PunchReviewService
from trishul_api.modules.hr.face_attendance.schemas import (
    AttendanceEmployeeOut,
    AttendancePolicyCreate,
    AttendancePolicyOut,
    AttendancePolicyUpdate,
    ChallengeOut,
    ChallengeRequest,
    EmployeePolicyAssign,
    EmployeePolicyOut,
    FaceModelOut,
    FaceRecordStatus,
    FaceRegistrationOut,
    FaceRejectIn,
    FaceTemplateOut,
    MyAttendanceTodayOut,
    MyMonthOut,
    PunchEvidence,
    PunchListItemOut,
    PunchResultOut,
    PunchReviewIn,
    PunchStatus,
    WorkLocationCreate,
    WorkLocationOut,
    WorkLocationUpdate,
)
from trishul_api.modules.hr.face_attendance.service import FaceAttendanceService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/hr/attendance", tags=["face-attendance"])

CAN_MARK = Depends(require_permission("hr.attendance.mark"))
CAN_VIEW_SETUP = Depends(
    require_permission("hr.attendance.manage", "hr.attendance.view.team", "hr.face.register", "hr.face.approve")
)
CAN_MANAGE = Depends(require_permission("hr.attendance.manage"))


def get_face_attendance_service(db: DbSession) -> FaceAttendanceService:
    return FaceAttendanceService(db)


FaceAttendance = Annotated[FaceAttendanceService, Depends(get_face_attendance_service)]


class FaceAttendanceUnavailable(ApiError):
    status = 503
    title = "Face attendance not available"


def _settings(request: Request) -> Settings:
    settings = getattr(request.app.state, "settings", None)
    return settings if isinstance(settings, Settings) else get_settings()


def get_face_engine(request: Request) -> FaceEngine:
    settings = _settings(request)
    try:
        return load_engine(FsPath(settings.face_models_dir) if settings.face_models_dir else None)
    except FaceEngineUnavailable as error:
        logger.error("face engine unavailable: %s", error)
        raise FaceAttendanceUnavailable("The face models are not installed on the server.") from error


def get_face_vault(request: Request) -> FaceVault:
    try:
        return FaceVault(load_key(_settings(request), getattr(request.app.state, "secret_provider", None)))
    except FaceDataKeyMissing as error:
        logger.error("face data key unavailable: %s", error)
        raise FaceAttendanceUnavailable("Face data encryption is not configured on the server.") from error


def get_face_registration_service(
    db: DbSession,
    engine: Annotated[FaceEngine, Depends(get_face_engine)],
    vault: Annotated[FaceVault, Depends(get_face_vault)],
) -> FaceRegistrationService:
    return FaceRegistrationService(db, engine, vault)


def get_face_vault_service(
    db: DbSession, vault: Annotated[FaceVault, Depends(get_face_vault)]
) -> FaceRegistrationService:
    return FaceRegistrationService(db, vault=vault)


def get_face_read_service(db: DbSession) -> FaceRegistrationService:
    return FaceRegistrationService(db)


Faces = Annotated[FaceRegistrationService, Depends(get_face_registration_service)]
FacesWithVault = Annotated[FaceRegistrationService, Depends(get_face_vault_service)]
FacesRead = Annotated[FaceRegistrationService, Depends(get_face_read_service)]
FaceId = Annotated[int, Path(alias="faceId", gt=0)]
CAN_REGISTER = Depends(require_permission("hr.face.register"))
CAN_APPROVE = Depends(require_permission("hr.face.approve"))
CAN_SEE_FACES = Depends(require_permission("hr.face.register", "hr.face.approve"))
CAN_SEE_PHOTO = Depends(require_permission("hr.attendance.photo.view", "hr.face.approve"))


def _ip(request: Request) -> str | None:
    return request.client.host if request.client else None


LocationId = Annotated[int, Path(alias="locationId", gt=0)]
PolicyId = Annotated[int, Path(alias="policyId", gt=0)]
EmployeeId = Annotated[int, Path(alias="employeeId", gt=0)]
IncludeInactive = Annotated[bool, Query(alias="includeInactive")]
Match = Annotated[bytes, Depends(if_match_row_version)]


# --- the employee's day (mobile) -----------------------------------------------------


@router.get(
    "/me/today",
    summary="My attendance today: policy, work locations, face registration and today's punches",
    dependencies=[CAN_MARK],
)
def get_my_attendance_today(actor: CurrentUserDep, service: FaceAttendance) -> MyAttendanceTodayOut:
    return service.my_today(actor)


@router.get(
    "/me/month",
    summary="My attendance calendar for a month (same day status as HR's Daily Attendance)",
    dependencies=[CAN_MARK],
)
def get_my_attendance_month(
    actor: CurrentUserDep,
    service: FaceAttendance,
    year: Annotated[int, Query(ge=2020, le=2100)],
    month: Annotated[int, Query(ge=1, le=12)],
) -> MyMonthOut:
    return service.my_month(actor, year, month)


# --- work locations --------------------------------------------------------------------


@router.get("/work-locations", summary="List attendance work locations (geofences)", dependencies=[CAN_VIEW_SETUP])
def list_work_locations(
    service: FaceAttendance,
    branch_id: Annotated[int | None, Query(alias="branchId", gt=0)] = None,
    include_inactive: IncludeInactive = False,
) -> list[WorkLocationOut]:
    return service.list_work_locations(branch_id, include_inactive)


@router.post(
    "/work-locations",
    summary="Add an attendance work location",
    status_code=201,
    dependencies=[CAN_MANAGE],
    responses=NOT_FOUND_RESPONSE,
)
def create_work_location(data: WorkLocationCreate, actor: CurrentUserDep, service: FaceAttendance) -> WorkLocationOut:
    return service.create_work_location(actor, data)


@router.patch(
    "/work-locations/{locationId}",
    summary="Update an attendance work location (If-Match: its rowVersion)",
    dependencies=[CAN_MANAGE],
    responses={**NOT_FOUND_RESPONSE, **CONCURRENCY_RESPONSES},
)
def update_work_location(
    location_id: LocationId,
    data: WorkLocationUpdate,
    row_version: Match,
    actor: CurrentUserDep,
    service: FaceAttendance,
) -> WorkLocationOut:
    return service.update_work_location(actor, location_id, data, row_version)


# --- policies --------------------------------------------------------------------------


@router.get("/policies", summary="List attendance policies", dependencies=[CAN_VIEW_SETUP])
def list_attendance_policies(
    service: FaceAttendance, include_inactive: IncludeInactive = False
) -> list[AttendancePolicyOut]:
    return service.list_policies(include_inactive)


@router.post("/policies", summary="Add an attendance policy", status_code=201, dependencies=[CAN_MANAGE])
def create_attendance_policy(
    data: AttendancePolicyCreate, actor: CurrentUserDep, service: FaceAttendance
) -> AttendancePolicyOut:
    return service.create_policy(actor, data)


@router.patch(
    "/policies/{policyId}",
    summary="Update an attendance policy (If-Match: its rowVersion)",
    dependencies=[CAN_MANAGE],
    responses={**NOT_FOUND_RESPONSE, **CONCURRENCY_RESPONSES},
)
def update_attendance_policy(
    policy_id: PolicyId,
    data: AttendancePolicyUpdate,
    row_version: Match,
    actor: CurrentUserDep,
    service: FaceAttendance,
) -> AttendancePolicyOut:
    return service.update_policy(actor, policy_id, data, row_version)


# --- employee assignment ---------------------------------------------------------------


@router.get(
    "/employees",
    summary="Active employees with today's attendance policy, work locations and face registration status",
    dependencies=[CAN_VIEW_SETUP],
)
def list_attendance_employees(
    service: FaceAttendance, branch_id: Annotated[int | None, Query(alias="branchId", gt=0)] = None
) -> list[AttendanceEmployeeOut]:
    return service.list_employees(branch_id)


@router.get(
    "/employees/{employeeId}/policy",
    summary="The attendance policy and work locations in force for an employee today",
    dependencies=[CAN_VIEW_SETUP],
    responses=NOT_FOUND_RESPONSE,
)
def get_employee_attendance_policy(employee_id: EmployeeId, service: FaceAttendance) -> EmployeePolicyOut:
    return service.get_employee_policy(employee_id)


@router.post(
    "/employees/{employeeId}/policy",
    summary="Assign an attendance policy and work locations to an employee from a date (closes the previous one)",
    dependencies=[CAN_MANAGE],
    responses=NOT_FOUND_RESPONSE,
)
def assign_employee_attendance_policy(
    employee_id: EmployeeId, data: EmployeePolicyAssign, actor: CurrentUserDep, service: FaceAttendance
) -> EmployeePolicyOut:
    return service.assign_employee_policy(actor, employee_id, data)


# --- face registration (HR) -------------------------------------------------------------


@router.post(
    "/employees/{employeeId}/face",
    summary="Register an employee's face from a photo (waits for a second HR user's approval)",
    dependencies=[CAN_REGISTER],
    responses=NOT_FOUND_RESPONSE,
)
def register_employee_face(
    employee_id: EmployeeId,
    photo: Annotated[UploadFile, File(description="JPEG or PNG, up to 8 MB")],
    consent: Annotated[bool, Form(description="The employee agreed to their face being stored for attendance")],
    request: Request,
    actor: CurrentUserDep,
    faces: Faces,
) -> FaceRegistrationOut:
    # Read one byte past the limit so an oversized upload is refused without loading all of it.
    raw = photo.file.read(MAX_PHOTO_BYTES + 1)
    return faces.register(actor, employee_id, raw, consent, _ip(request))


@router.delete(
    "/faces/{faceId}",
    summary="Delete a face registration's data: photo and face vector (If-Match: its rowVersion)",
    status_code=204,
    dependencies=[CAN_REGISTER],
    responses={**NOT_FOUND_RESPONSE, **CONCURRENCY_RESPONSES},
)
def delete_face_registration(
    face_id: FaceId, row_version: Match, request: Request, actor: CurrentUserDep, faces: FacesWithVault
) -> Response:
    faces.remove_face(actor, face_id, row_version, _ip(request))
    return Response(status_code=204)


@router.get("/faces", summary="List face registrations", dependencies=[CAN_SEE_FACES])
def list_face_registrations(
    faces: FacesRead,
    status: Annotated[FaceRecordStatus | None, Query()] = None,
    employee_id: Annotated[int | None, Query(alias="employeeId", gt=0)] = None,
) -> list[FaceRegistrationOut]:
    return faces.list_faces(status, employee_id)


@router.post(
    "/faces/{faceId}/approve",
    summary="Approve a face registration (not one you registered)",
    dependencies=[CAN_APPROVE],
    responses=NOT_FOUND_RESPONSE,
)
def approve_face_registration(
    face_id: FaceId, request: Request, actor: CurrentUserDep, faces: FacesRead
) -> FaceRegistrationOut:
    return faces.approve(actor, face_id, _ip(request))


@router.post(
    "/faces/{faceId}/reject",
    summary="Reject a face registration with a reason",
    dependencies=[CAN_APPROVE],
    responses=NOT_FOUND_RESPONSE,
)
def reject_face_registration(
    face_id: FaceId, data: FaceRejectIn, request: Request, actor: CurrentUserDep, faces: FacesRead
) -> FaceRegistrationOut:
    return faces.reject(actor, face_id, data.reason, _ip(request))


@router.get(
    "/faces/{faceId}/photo",
    summary="The registration photo (each view is written to the audit log)",
    dependencies=[CAN_SEE_PHOTO],
    responses={**NOT_FOUND_RESPONSE, 200: {"content": {"image/jpeg": {}}}},
    response_class=Response,
)
def get_face_registration_photo(
    face_id: FaceId, request: Request, actor: CurrentUserDep, faces: FacesWithVault
) -> Response:
    raw = faces.photo(actor, face_id, _ip(request))
    return Response(
        content=raw,
        media_type="image/jpeg",
        headers={"Cache-Control": "private, no-store", "X-Content-Type-Options": "nosniff"},
    )


@router.get("/face-models", summary="Face and anti-spoof model versions", dependencies=[CAN_VIEW_SETUP])
def list_face_models(faces: FacesRead) -> list[FaceModelOut]:
    return faces.face_models()


# --- punching (mobile) ---------------------------------------------------------------------


def get_punch_service(
    db: DbSession,
    engine: Annotated[FaceEngine, Depends(get_face_engine)],
    vault: Annotated[FaceVault, Depends(get_face_vault)],
) -> PunchService:
    return PunchService(db, engine, vault)


Punches = Annotated[PunchService, Depends(get_punch_service)]
_EVIDENCE_HELP = (
    "PunchEvidence as JSON: clientUuid, punchType, nonce, challengeResult, deviceScore, GPS, device details"
)


def _frames(files: list[UploadFile]) -> list[Frame]:
    if len(files) > MAX_FRAMES:
        raise ApiError(f"Send at most {MAX_FRAMES} photos.")
    return [Frame(data=f.file.read(MAX_FRAME_BYTES + 1)) for f in files]


def _evidence(raw: str) -> PunchEvidence:
    try:
        return PunchEvidence.model_validate_json(raw)
    except ValidationError as error:
        problems = [f"{'.'.join(str(p) for p in e['loc']) or 'evidence'}: {e['msg']}" for e in error.errors()]
        raise ApiError("The punch details are not valid.", errors={"evidence": problems}) from error


@router.post(
    "/challenges",
    summary="Start an online punch: a one-time code and the blink / head-turn to ask for (valid 2 minutes)",
    status_code=201,
    dependencies=[CAN_MARK],
)
def create_attendance_challenge(data: ChallengeRequest, actor: CurrentUserDep, punches: Punches) -> ChallengeOut:
    return punches.challenge(actor, data.punch_type)


@router.post(
    "/punches",
    summary="Online check-in / check-out with 1 to 3 photos (resending the same clientUuid is safe)",
    dependencies=[CAN_MARK],
)
def create_attendance_punch(
    evidence: Annotated[str, Form(description=_EVIDENCE_HELP)],
    frames: Annotated[list[UploadFile], File(description="1 to 3 JPEG photos from the face check")],
    request: Request,
    actor: CurrentUserDep,
    punches: Punches,
) -> PunchResultOut:
    return punches.punch(actor, _evidence(evidence), _frames(frames), offline=False, ip_address=_ip(request))


@router.post(
    "/punches/offline",
    summary="A punch taken without network, sent later (resending the same clientUuid is safe)",
    dependencies=[CAN_MARK],
)
def create_offline_attendance_punch(
    evidence: Annotated[str, Form(description=_EVIDENCE_HELP + "; deviceCapturedAt is required")],
    frames: Annotated[list[UploadFile], File(description="1 to 3 JPEG photos from the face check")],
    request: Request,
    actor: CurrentUserDep,
    punches: Punches,
) -> PunchResultOut:
    return punches.punch(actor, _evidence(evidence), _frames(frames), offline=True, ip_address=_ip(request))


# --- review queue and photos (HR / team lead) ----------------------------------------------

CAN_SEE_PUNCHES = Depends(
    require_permission("hr.attendance.manage", "hr.attendance.view.team", "hr.attendance.mark")
)


def get_review_service(db: DbSession) -> PunchReviewService:
    return PunchReviewService(db)


def get_review_vault_service(db: DbSession, vault: Annotated[FaceVault, Depends(get_face_vault)]) -> PunchReviewService:
    return PunchReviewService(db, vault)


Reviews = Annotated[PunchReviewService, Depends(get_review_service)]
ReviewsWithVault = Annotated[PunchReviewService, Depends(get_review_vault_service)]
PunchId = Annotated[int, Path(alias="punchId", gt=0)]


@router.get(
    "/punches",
    summary="Face punches (HR: everyone; team lead: their team). status=Pending is the review queue",
    dependencies=[CAN_SEE_PUNCHES],
)
def list_attendance_punches(
    actor: CurrentUserDep,
    reviews: Reviews,
    status: Annotated[PunchStatus | None, Query()] = None,
    from_date: Annotated[date | None, Query(alias="fromDate")] = None,
    to_date: Annotated[date | None, Query(alias="toDate")] = None,
    employee_id: Annotated[int | None, Query(alias="employeeId", gt=0)] = None,
    mine_only: Annotated[bool, Query(alias="mineOnly")] = False,
    limit: Annotated[int, Query(ge=1, le=1000)] = 200,
) -> list[PunchListItemOut]:
    return reviews.list_punches(
        actor, status, from_date, to_date, employee_id, limit, mine_only=mine_only
    )


@router.post(
    "/punches/{punchId}/review",
    summary="Accept or reject a punch waiting for review",
    dependencies=[CAN_MANAGE],
    responses=NOT_FOUND_RESPONSE,
)
def review_attendance_punch(
    punch_id: PunchId, data: PunchReviewIn, request: Request, actor: CurrentUserDep, reviews: Reviews
) -> PunchListItemOut:
    return reviews.review(actor, punch_id, data.decision, data.remarks, _ip(request))


@router.get(
    "/punches/{punchId}/photo",
    summary="The punch photo (each view is written to the audit log)",
    dependencies=[Depends(require_permission("hr.attendance.photo.view"))],
    responses={**NOT_FOUND_RESPONSE, 200: {"content": {"image/jpeg": {}}}},
    response_class=Response,
)
def get_attendance_punch_photo(
    punch_id: PunchId, request: Request, actor: CurrentUserDep, reviews: ReviewsWithVault
) -> Response:
    raw = reviews.photo(actor, punch_id, _ip(request))
    return Response(
        content=raw,
        media_type="image/jpeg",
        headers={"Cache-Control": "private, no-store", "X-Content-Type-Options": "nosniff"},
    )


@router.get(
    "/me/face-template",
    summary="My registered face (for matching on the phone when offline); each download is logged",
    dependencies=[CAN_MARK],
    responses=NOT_FOUND_RESPONSE,
)
def get_my_face_template(request: Request, actor: CurrentUserDep, reviews: ReviewsWithVault) -> FaceTemplateOut:
    return reviews.my_template(actor, _ip(request))
