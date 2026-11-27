import { Injectable, inject } from '@angular/core';
import { Observable } from 'rxjs';
import {
  ApiClient,
  AttendanceEmployeeOut,
  AttendancePolicyCreate,
  AttendancePolicyOut,
  AttendancePolicyUpdate,
  EmployeePolicyAssign,
  EmployeePolicyOut,
  FaceRegistrationOut,
  PunchListItemOut,
  WorkLocationCreate,
  WorkLocationOut,
  WorkLocationUpdate,
  approveFaceRegistration,
  assignEmployeeAttendancePolicy,
  createAttendancePolicy,
  createWorkLocation,
  deleteFaceRegistration,
  getAttendancePunchPhoto,
  getFaceRegistrationPhoto,
  listAttendanceEmployees,
  listAttendancePolicies,
  listAttendancePunches,
  listFaceRegistrations,
  listWorkLocations,
  registerEmployeeFace,
  rejectFaceRegistration,
  reviewAttendancePunch,
  updateAttendancePolicy,
  updateWorkLocation,
  withRowVersion,
  withoutErrorToast,
} from '@trishul/core-api';

/**
 * Mobile face attendance, HR side: work locations, policies, employee set-up, face registration and
 * approval, and the review queue. API: backend modules/hr/face_attendance (under /hr/attendance).
 * Decimal fields (coordinates, scores, thresholds) arrive as strings, as everywhere in the generated client.
 */

/** Any of these opens the Face Attendance screens (each screen and button checks its own permission). */
export const FACE_ATTENDANCE_VIEW_PERMISSIONS = [
  'hr.attendance.manage',
  'hr.attendance.view.team',
  'hr.face.register',
  'hr.face.approve',
] as const;
export const FACE_ATTENDANCE_MANAGE_PERMISSION = 'hr.attendance.manage';
export const FACE_REGISTER_PERMISSION = 'hr.face.register';
export const FACE_APPROVE_PERMISSION = 'hr.face.approve';
export const FACE_PHOTO_PERMISSION = 'hr.attendance.photo.view';
export const FACE_PUNCH_VIEW_PERMISSIONS = [
  'hr.attendance.manage',
  'hr.attendance.view.team',
] as const;

export type WorkLocation = WorkLocationOut;
export type AttendancePolicy = AttendancePolicyOut;
export type AttendanceEmployee = AttendanceEmployeeOut;
export type FaceRegistration = FaceRegistrationOut;
export type FacePunch = PunchListItemOut;
export type FaceRegistrationStatus = FaceRegistrationOut['status'];
export type FacePunchStatus = PunchListItemOut['status'];
export type {
  AttendancePolicyCreate,
  AttendancePolicyUpdate,
  EmployeePolicyAssign,
  WorkLocationCreate,
  WorkLocationUpdate,
};

export interface FacePunchQuery {
  status?: FacePunchStatus | '';
  fromDate?: string;
  toDate?: string;
  employeeId?: number;
  /** ESS My Punch Logs — server forces the signed-in employee's punches. */
  mineOnly?: boolean;
  limit?: number;
}

/** For calls made from dialogs that show the server's reason themselves (no second, global toast). */
const quiet = (): ReturnType<typeof withoutErrorToast> => withoutErrorToast();

@Injectable({ providedIn: 'root' })
export class FaceAttendanceApi {
  private readonly api = inject(ApiClient);

  // --- employees -------------------------------------------------------------------

  listEmployees(): Observable<AttendanceEmployee[]> {
    return this.api.call(listAttendanceEmployees, {});
  }

  assignPolicy(
    employeeId: number,
    body: EmployeePolicyAssign,
  ): Observable<EmployeePolicyOut> {
    return this.api.call(
      assignEmployeeAttendancePolicy,
      { employeeId, body },
      quiet(),
    );
  }

  // --- work locations ------------------------------------------------------------------

  listLocations(includeInactive = true): Observable<WorkLocation[]> {
    return this.api.call(listWorkLocations, { includeInactive });
  }

  createLocation(body: WorkLocationCreate): Observable<WorkLocation> {
    return this.api.call(createWorkLocation, { body }, quiet());
  }

  updateLocation(
    row: WorkLocation,
    body: WorkLocationUpdate,
  ): Observable<WorkLocation> {
    return this.api.call(
      updateWorkLocation,
      { locationId: row.id, body },
      withRowVersion(row.rowVersion, quiet()),
    );
  }

  // --- policies ----------------------------------------------------------------------------

  listPolicies(includeInactive = true): Observable<AttendancePolicy[]> {
    return this.api.call(listAttendancePolicies, { includeInactive });
  }

  createPolicy(body: AttendancePolicyCreate): Observable<AttendancePolicy> {
    return this.api.call(createAttendancePolicy, { body }, quiet());
  }

  updatePolicy(
    row: AttendancePolicy,
    body: AttendancePolicyUpdate,
  ): Observable<AttendancePolicy> {
    return this.api.call(
      updateAttendancePolicy,
      { policyId: row.id, body },
      withRowVersion(row.rowVersion, quiet()),
    );
  }

  // --- faces ---------------------------------------------------------------------------------

  listFaces(
    status?: FaceRegistrationStatus | '',
    employeeId?: number,
  ): Observable<FaceRegistration[]> {
    return this.api.call(listFaceRegistrations, {
      status: status || null,
      employeeId: employeeId ?? null,
    });
  }

  /** The photo upload with the employee's consent; the server checks quality and refuses look-alikes. */
  registerFace(
    employeeId: number,
    photo: File,
    consent: boolean,
  ): Observable<FaceRegistration> {
    // The generator types binary form fields as string; the request builder sends a File as the file part.
    const body = { photo: photo as unknown as string, consent };
    return this.api.call(registerEmployeeFace, { employeeId, body }, quiet());
  }

  approveFace(faceId: number): Observable<FaceRegistration> {
    return this.api.call(approveFaceRegistration, { faceId }, quiet());
  }

  rejectFace(faceId: number, reason: string): Observable<FaceRegistration> {
    return this.api.call(
      rejectFaceRegistration,
      { faceId, body: { reason } },
      quiet(),
    );
  }

  deleteFace(row: FaceRegistration): Observable<void> {
    return this.api.call(
      deleteFaceRegistration,
      { faceId: row.id },
      withRowVersion(row.rowVersion, quiet()),
    );
  }

  facePhoto(faceId: number): Observable<Blob> {
    return this.api.call(getFaceRegistrationPhoto, {
      faceId,
    }) as Observable<Blob>;
  }

  // --- punches -------------------------------------------------------------------------------

  listPunches(query: FacePunchQuery = {}): Observable<FacePunch[]> {
    return this.api.call(listAttendancePunches, {
      status: query.status || null,
      fromDate: query.fromDate || null,
      toDate: query.toDate || null,
      employeeId: query.employeeId ?? null,
      mineOnly: query.mineOnly === true ? true : undefined,
      limit: query.limit,
    });
  }

  reviewPunch(
    punchId: number,
    decision: 'Present' | 'Rejected',
    remarks: string,
  ): Observable<FacePunch> {
    return this.api.call(
      reviewAttendancePunch,
      { punchId, body: { decision, remarks } },
      quiet(),
    );
  }

  punchPhoto(punchId: number): Observable<Blob> {
    return this.api.call(getAttendancePunchPhoto, {
      punchId,
    }) as Observable<Blob>;
  }
}

/** The server's plain-language reason from a failed call (problem+json "detail"), else [fallback]. */
export function faceAttendanceError(err: unknown, fallback: string): string {
  const body = (
    err as { error?: { detail?: unknown; errors?: Record<string, string[]> } }
  )?.error;
  const fieldErrors = body?.errors ? Object.values(body.errors).flat() : [];
  if (fieldErrors.length) return fieldErrors.join(' ');
  return typeof body?.detail === 'string' ? body.detail : fallback;
}

/** A decimal string from the API as a number (null stays null). */
export function num(value: string | number | null | undefined): number | null {
  if (value === null || value === undefined || value === '') return null;
  const n = Number(value);
  return Number.isFinite(n) ? n : null;
}
