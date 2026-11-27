/** Daily Attendance UI models (API-backed display). */

export type AttendanceStatus =
  | 'Present'
  | 'Late'
  | 'In Progress'
  | 'Missing Punch'
  | 'Absent'
  | 'On Leave'
  | 'Off Day'
  | 'Holiday'
  | 'WFH';

export type ContentTab = 'records' | 'exceptions' | 'regularization' | 'punches';

export interface AttendancePunch {
  kind: 'IN' | 'OUT';
  at: string;
  device: string;
  /** Mobile face punches: where it was made. Biometric punches: none. */
  location?: {
    latitude: number;
    longitude: number;
    accuracyM: number | null;
    place: string | null;
    insideOffice: boolean | null;
    distanceM: number | null;
    fakeGps: boolean;
  } | null;
}

export interface AttendanceHistoryItem {
  date: string;
  status: AttendanceStatus;
  firstIn: string | null;
  lastOut: string | null;
  workingHours: string | null;
}

export interface DailyAttendanceRow {
  id: number;
  /** Attendance day when a row is one date inside a range. */
  dateIso?: string;
  employeeId: number;
  employeeCode: string;
  employeeName: string;
  department: string;
  location: string;
  shift: string;
  employeeType: string;
  reportingManager: string;
  firstIn: string | null;
  lastOut: string | null;
  firstInLate: boolean;
  workingHours: string | null;
  status: AttendanceStatus;
  remarks: string;
  lateArrivalMinutes: number | null;
  earlyExitMinutes: number | null;
  avatarTone: string;
  punches: AttendancePunch[];
  history: AttendanceHistoryItem[];
}

export interface AttendanceKpi {
  total: number;
  present: number;
  late: number;
  absent: number;
  onLeave: number;
  wfh: number;
}

export interface RegularizationRequest {
  id: number;
  employeeCode: string;
  employeeName: string;
  date: string;
  requestType: string;
  reason: string;
  status: 'Pending' | 'Approved' | 'Rejected';
  avatarTone: string;
}

/** Full Attendance Regularization list models (API-backed display). */
export type RegularizationRequestType =
  | 'Missed Punch'
  | 'Wrong Attendance'
  | 'Early Exit'
  | 'WFH Correction'
  | 'Late Arrival'
  | 'Holiday Work';

export type RegularizationStatus = 'Pending' | 'Approved' | 'Rejected';

export type RegularizationTab = 'pending' | 'approved' | 'rejected' | 'all';

export interface RegularizationKpi {
  total: number;
  pending: number;
  approved: number;
  rejected: number;
}

export interface RegularizationListRow {
  id: number;
  employeeId: number;
  employeeCode: string;
  employeeName: string;
  department: string;
  location: string;
  attendanceDate: string;
  attendanceDateIso: string;
  requestType: RegularizationRequestType;
  originalIn: string | null;
  originalOut: string | null;
  requestedIn: string | null;
  requestedOut: string | null;
  reason: string;
  submittedOn: string;
  status: RegularizationStatus;
  avatarTone: string;
  attachmentName?: string | null;
  rejectionReason?: string | null;
  reviewedBy?: string | null;
  reviewedOn?: string | null;
}

export const REGULARIZATION_REQUEST_TYPES: RegularizationRequestType[] = [
  'Missed Punch',
  'Wrong Attendance',
  'Early Exit',
  'WFH Correction',
  'Late Arrival',
  'Holiday Work',
];

export const ATTENDANCE_STATUSES: AttendanceStatus[] = [
  'Present',
  'Late',
  'Absent',
  'On Leave',
  'WFH',
];

/** Monthly Muster matrix day codes. */
export type MusterDayCode = 'P' | 'L' | 'A' | 'PL' | 'WFH' | 'OFF' | 'H';

export interface MusterDayColumn {
  day: number;
  weekday: string;
  isWeekend: boolean;
}

export interface MusterEmployeeRow {
  id: number;
  employeeCode: string;
  employeeName: string;
  department: string;
  location: string;
  employmentStatus: 'Active' | 'Inactive';
  avatarTone: string;
  days: MusterDayCode[];
  present: number;
  late: number;
  absent: number;
  leave: number;
  wfh: number;
  hours: number;
}

/** Attendance Exceptions UI models (static mock). */
export type ExceptionType =
  | 'Missing Punch'
  | 'Late Arrival'
  | 'Early Exit'
  | 'Short Hours'
  | 'Absent';

export type ExceptionReviewStatus = 'Pending' | 'Resolved';

export type ExceptionTab = 'all' | 'pending' | 'resolved';

export interface ExceptionKpi {
  total: number;
  missingPunch: number;
  lateArrival: number;
  earlyExit: number;
  shortHours: number;
  absent: number;
}

export interface AttendanceExceptionRow {
  id: number;
  employeeId: number;
  employeeCode: string;
  employeeName: string;
  department: string;
  location: string;
  date: string;
  dateIso: string;
  shift: string;
  firstIn: string | null;
  lastOut: string | null;
  exceptionType: ExceptionType;
  expectedHours: string;
  actualHours: string | null;
  status: ExceptionReviewStatus;
  avatarTone: string;
  remark: string;
}

export const EXCEPTION_TYPES: ExceptionType[] = [
  'Missing Punch',
  'Late Arrival',
  'Early Exit',
  'Short Hours',
  'Absent',
];

/** Shift & Attendance Rules UI tab ids (data comes from AttendanceApi / LeaveApi). */
export type RulesTab = 'shifts' | 'rules' | 'assignment' | 'holidays';

/** Attendance Finalization tab ids (data from AttendanceApi.finalization). */
export type FinalizationTab = 'department' | 'location';

/** Attendance Dashboard UI models (static mock). */
export interface DashboardKpiCard {
  id: string;
  label: string;
  value: number;
  percent?: number;
  icon: string;
  tone: 'total' | 'present' | 'absent' | 'late' | 'early' | 'short';
}

export interface DashboardOverviewSlice {
  label: string;
  count: number;
  percent: number;
  color: string;
}

export interface DashboardTrendPoint {
  label: string;
  percent: number;
}

export interface DashboardDepartmentRow {
  id: number;
  department: string;
  employees: number;
  present: number;
  absent: number;
  attendancePct: number;
}

export interface DashboardExceptionItem {
  id: string;
  label: string;
  count: number;
  tone: 'missing' | 'late' | 'early' | 'short';
  icon: string;
  route: string;
}

export interface DashboardQuickAction {
  id: string;
  label: string;
  icon: string;
  route: string;
}
