import { HttpClient, HttpHeaders, HttpParams } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { Observable } from 'rxjs';
import { ApiConfiguration, withRowVersion } from '@trishul/core-api';

/** Create/update/deactivate shifts and shift assignments. Not implied by HR/ADMIN role. */
export const ATTENDANCE_SHIFT_MANAGE_PERMISSION = 'hr.attendance.shift.manage';
/** Edit organization attendance rules. Not implied by HR/ADMIN role. */
export const ATTENDANCE_RULES_MANAGE_PERMISSION = 'hr.attendance.rules.manage';
/** Finalize and lock monthly attendance. Not implied by HR/ADMIN role. */
export const ATTENDANCE_FINALIZE_PERMISSION = 'hr.attendance.finalize';

export type AttendanceStatus =
  | 'Present'
  | 'Late'
  | 'In Progress'
  | 'Missing Punch'
  | 'Absent'
  | 'On Leave'
  | 'Off Day'
  | 'Holiday';

export type AttendanceStatusTab = 'all' | 'present' | 'absent' | 'leave' | 'offDay';
export type AttendancePunchKind = 'IN' | 'OUT';

/** Where a mobile face punch was made; null for biometric punches. */
export interface AttendancePunchLocation {
  latitude: number;
  longitude: number;
  accuracyM: number | null;
  /** Nearest work location of the employee's attendance policy. */
  place: string | null;
  insideOffice: boolean | null;
  distanceM: number | null;
  fakeGps: boolean;
}

export interface AttendancePunch {
  kind: AttendancePunchKind;
  at: string;
  device: string;
  location?: AttendancePunchLocation | null;
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
  /** e.g. "2h 21m + 0h 50m" when multiple IN–OUT sessions. */
  workingHoursDetail?: string | null;
  currentPunch?: 'IN' | 'OUT' | null;
  currentPunchSince?: string | null;
  requiredHours?: string | null;
  shortfall?: string | null;
  openInAt?: string | null;
  closedWorkedMinutes?: number;
  status: AttendanceStatus;
  remarks: string;
  lateArrivalMinutes: number | null;
  earlyExitMinutes: number | null;
  punches: AttendancePunch[];
  history: AttendanceHistoryItem[];
}

export interface AttendanceSummary {
  total: number;
  present: number;
  late: number;
  missingPunch: number;
  absent: number;
  onLeave: number;
  offDay: number;
  holiday: number;
}

export interface AttendanceFilterOptions {
  departments: string[];
  locations: string[];
  shifts: string[];
  employeeTypes: string[];
  managers: string[];
  statuses: AttendanceStatus[];
}

export interface DailyAttendancePage {
  date: string;
  summary: AttendanceSummary;
  filterOptions: AttendanceFilterOptions;
  items: DailyAttendanceRow[];
  total: number;
  page: number;
  pageSize: number;
}

export interface DailyAttendanceQuery {
  date: string;
  page?: number;
  pageSize?: number;
  search?: string;
  statusTab?: AttendanceStatusTab;
  department?: string;
  location?: string;
  shift?: string;
  status?: AttendanceStatus | '';
  employeeType?: string;
  reportingManager?: string;
  includeHistory?: boolean;
  includePunches?: boolean;
}

@Injectable({ providedIn: 'root' })
export class AttendanceApi {
  private readonly http = inject(HttpClient);
  private readonly config = inject(ApiConfiguration);

  private get base(): string {
    return `${this.config.rootUrl}/hr/attendance`;
  }

  dashboard(date?: string, department?: string, location?: string): Observable<AttendanceDashboard> {
    let params = new HttpParams();
    if (date) params = params.set('date', date);
    if (department) params = params.set('department', department);
    if (location) params = params.set('location', location);
    return this.http.get<AttendanceDashboard>(`${this.base}/dashboard`, { params });
  }

  mine(year: number, month: number, employeeId?: number): Observable<MineAttendancePage> {
    let params = new HttpParams().set('year', String(year)).set('month', String(month));
    if (employeeId) params = params.set('employeeId', String(employeeId));
    return this.http.get<MineAttendancePage>(`${this.base}/mine`, { params });
  }

  reportsSummary(year: number, month: number): Observable<AttendanceReportsSummary> {
    const params = new HttpParams().set('year', String(year)).set('month', String(month));
    return this.http.get<AttendanceReportsSummary>(`${this.base}/reports/summary`, { params });
  }

  /** Load one selected date. Prefer statusTab=all + large pageSize; filter tabs client-side. */
  listDaily(query: DailyAttendanceQuery): Observable<DailyAttendancePage> {
    let params = new HttpParams()
      .set('date', query.date)
      .set('page', String(query.page ?? 1))
      .set('pageSize', String(query.pageSize ?? 20))
      .set('statusTab', query.statusTab ?? 'all')
      .set('includeHistory', String(query.includeHistory ?? false))
      .set('includePunches', String(query.includePunches ?? true));
    if (query.search?.trim()) params = params.set('search', query.search.trim());
    if (query.department) params = params.set('department', query.department);
    if (query.location) params = params.set('location', query.location);
    if (query.shift) params = params.set('shift', query.shift);
    if (query.status) params = params.set('status', query.status);
    if (query.employeeType) params = params.set('employeeType', query.employeeType);
    if (query.reportingManager) params = params.set('reportingManager', query.reportingManager);
    return this.http.get<DailyAttendancePage>(`${this.base}/daily`, { params });
  }

  /** Lazy history for the attendance drawer (does not block the main table). */
  employeeHistory(employeeId: number, before: string, days = 7): Observable<AttendanceHistoryItem[]> {
    const params = new HttpParams().set('before', before).set('days', String(days));
    return this.http.get<AttendanceHistoryItem[]>(
      `${this.base}/daily/employees/${employeeId}/history`,
      { params },
    );
  }

  /** Monthly muster matrix for one calendar month. */
  listMuster(query: MonthlyMusterQuery): Observable<MonthlyMusterPage> {
    let params = new HttpParams()
      .set('year', String(query.year))
      .set('month', String(query.month))
      .set('page', String(query.page ?? 1))
      .set('pageSize', String(query.pageSize ?? 200));
    if (query.search?.trim()) params = params.set('search', query.search.trim());
    if (query.department) params = params.set('department', query.department);
    if (query.location) params = params.set('location', query.location);
    if (query.employmentStatus) params = params.set('employmentStatus', query.employmentStatus);
    return this.http.get<MonthlyMusterPage>(`${this.base}/muster`, { params });
  }

  /** Attendance exceptions for a date range. */
  listExceptions(query: AttendanceExceptionsQuery): Observable<AttendanceExceptionsList> {
    let params = new HttpParams()
      .set('from', query.from)
      .set('to', query.to)
      .set('page', String(query.page ?? 1))
      .set('pageSize', String(query.pageSize ?? 200))
      .set('statusTab', query.statusTab ?? 'all');
    if (query.search?.trim()) params = params.set('search', query.search.trim());
    if (query.department) params = params.set('department', query.department);
    if (query.location) params = params.set('location', query.location);
    if (query.exceptionType) params = params.set('exceptionType', query.exceptionType);
    if (query.status) params = params.set('status', query.status);
    return this.http.get<AttendanceExceptionsList>(`${this.base}/exceptions`, { params });
  }

  /** Mark exception resolved (sets hr.attendance status + is_regularized). */
  resolveException(
    exceptionId: number,
    remark?: string,
    resolvedStatus?: 'Present' | 'Absent' | 'Half day' | 'On duty',
  ): Observable<AttendanceExceptionRow> {
    const body: { remark?: string; resolvedStatus?: string } = {};
    if (remark) body.remark = remark;
    if (resolvedStatus) body.resolvedStatus = resolvedStatus;
    return this.http.post<AttendanceExceptionRow>(
      `${this.base}/exceptions/${exceptionId}/resolve`,
      body,
    );
  }

  /** Attendance regularization requests from hr.attendance_regularization. */
  listRegularizations(query: RegularizationQuery): Observable<RegularizationPage> {
    let params = new HttpParams()
      .set('from', query.from)
      .set('to', query.to)
      .set('page', String(query.page ?? 1))
      .set('pageSize', String(query.pageSize ?? 200))
      .set('statusTab', query.statusTab ?? 'all');
    if (query.search?.trim()) params = params.set('search', query.search.trim());
    if (query.department) params = params.set('department', query.department);
    if (query.location) params = params.set('location', query.location);
    if (query.requestType) params = params.set('requestType', query.requestType);
    if (query.scope) params = params.set('scope', query.scope);
    return this.http.get<RegularizationPage>(`${this.base}/regularizations`, { params });
  }

  createRegularization(body: RegularizationCreate): Observable<RegularizationRow> {
    return this.http.post<RegularizationRow>(`${this.base}/regularizations`, body);
  }

  /** ESS: regularization for authenticated employee (server ignores client employeeId). */
  createMineRegularization(body: RegularizationCreate): Observable<RegularizationRow> {
    return this.http.post<RegularizationRow>(`${this.base}/mine/regularizations`, body);
  }

  approveRegularization(regularizationId: number, remark?: string): Observable<RegularizationRow> {
    return this.http.post<RegularizationRow>(
      `${this.base}/regularizations/${regularizationId}/approve`,
      remark ? { remark } : {},
    );
  }

  rejectRegularization(regularizationId: number, remark: string): Observable<RegularizationRow> {
    return this.http.post<RegularizationRow>(
      `${this.base}/regularizations/${regularizationId}/reject`,
      { remark },
    );
  }

  // ---- Shift & Attendance Rules --------------------------------------------

  listShifts(query: ShiftListQuery = {}): Observable<ShiftPage> {
    let params = new HttpParams()
      .set('page', String(query.page ?? 1))
      .set('pageSize', String(query.pageSize ?? 200));
    if (query.search?.trim()) params = params.set('search', query.search.trim());
    if (query.activeOnly === true) params = params.set('activeOnly', 'true');
    if (query.activeOnly === false) params = params.set('activeOnly', 'false');
    return this.http.get<ShiftPage>(`${this.base}/shifts`, { params });
  }

  createShift(body: ShiftWrite): Observable<ShiftItem> {
    return this.http.post<ShiftItem>(`${this.base}/shifts`, body);
  }

  updateShift(shiftId: number, rowVersion: string, body: ShiftWrite): Observable<ShiftItem> {
    return this.http.patch<ShiftItem>(`${this.base}/shifts/${shiftId}`, body, {
      context: withRowVersion(rowVersion),
    });
  }

  deleteShift(shiftId: number, rowVersion: string): Observable<void> {
    return this.http.delete<void>(`${this.base}/shifts/${shiftId}`, {
      context: withRowVersion(rowVersion),
    });
  }

  leaveYear(): Observable<LeaveYearInfo> {
    return this.http.get<LeaveYearInfo>(`${this.base}/leave-year`);
  }

  holidaysForLeaveYear(): Observable<AttendanceHolidayPage> {
    return this.http.get<AttendanceHolidayPage>(`${this.base}/holidays`);
  }

  finalization(query: FinalizationQuery): Observable<FinalizationPage> {
    const params = new HttpParams()
      .set('year', String(query.year))
      .set('month', String(query.month))
      .set('groupBy', query.groupBy ?? 'department');
    return this.http.get<FinalizationPage>(`${this.base}/finalization`, { params });
  }

  lockFinalization(year: number, month: number): Observable<FinalizationLockResult> {
    const params = new HttpParams().set('year', String(year)).set('month', String(month));
    return this.http.post<FinalizationLockResult>(`${this.base}/finalization/lock`, {}, { params });
  }

  saveFinalizationFollowup(body: FinalizationFollowupWrite): Observable<FinalizationChecklistItem> {
    return this.http.put<FinalizationChecklistItem>(`${this.base}/finalization/follow-up`, body);
  }

  remindFinalization(body: FinalizationRemindWrite): Observable<FinalizationRemindResult> {
    return this.http.post<FinalizationRemindResult>(`${this.base}/finalization/reminders`, body);
  }

  getRules(): Observable<AttendanceRules> {
    return this.http.get<AttendanceRules>(`${this.base}/rules`);
  }

  saveRules(body: AttendanceRulesWrite, rowVersion?: string | null): Observable<AttendanceRules> {
    const headers =
      rowVersion != null && rowVersion !== ''
        ? new HttpHeaders({ 'If-Match': `"${rowVersion}"` })
        : undefined;
    return this.http.put<AttendanceRules>(`${this.base}/rules`, body, { headers });
  }

  shiftAssignmentOptions(): Observable<ShiftAssignmentOptions> {
    return this.http.get<ShiftAssignmentOptions>(`${this.base}/shift-assignments/options`);
  }

  listShiftAssignments(query: ShiftAssignmentListQuery = {}): Observable<ShiftAssignmentPage> {
    let params = new HttpParams()
      .set('page', String(query.page ?? 1))
      .set('pageSize', String(query.pageSize ?? 200))
      .set('currentOnly', String(query.currentOnly ?? true));
    if (query.search?.trim()) params = params.set('search', query.search.trim());
    if (query.employeeId) params = params.set('employeeId', String(query.employeeId));
    if (query.shiftId) params = params.set('shiftId', String(query.shiftId));
    return this.http.get<ShiftAssignmentPage>(`${this.base}/shift-assignments`, { params });
  }

  createShiftAssignment(body: ShiftAssignmentWrite): Observable<ShiftAssignmentItem> {
    return this.http.post<ShiftAssignmentItem>(`${this.base}/shift-assignments`, body);
  }

  assignShiftToEmployees(body: ShiftAssignmentBulkWrite): Observable<ShiftAssignmentBulkResult> {
    return this.http.post<ShiftAssignmentBulkResult>(`${this.base}/shift-assignments/bulk`, body);
  }

  updateShiftAssignment(
    assignmentId: number,
    rowVersion: string,
    body: ShiftAssignmentWrite,
  ): Observable<ShiftAssignmentItem> {
    return this.http.patch<ShiftAssignmentItem>(`${this.base}/shift-assignments/${assignmentId}`, body, {
      context: withRowVersion(rowVersion),
    });
  }

  deleteShiftAssignment(assignmentId: number, rowVersion: string): Observable<void> {
    return this.http.delete<void>(`${this.base}/shift-assignments/${assignmentId}`, {
      context: withRowVersion(rowVersion),
    });
  }
}

export type MusterDayCode = 'P' | 'L' | 'A' | 'PL' | 'WFH' | 'OFF' | 'H';
export type EmploymentStatus = 'Active' | 'Inactive';

export interface MusterDayColumn {
  day: number;
  weekday: string;
  isWeekend: boolean;
}

export interface MusterEmployeeRow {
  id: number;
  employeeId: number;
  employeeCode: string;
  employeeName: string;
  department: string;
  location: string;
  employmentStatus: EmploymentStatus;
  days: MusterDayCode[];
  present: number;
  late: number;
  absent: number;
  leave: number;
  wfh: number;
  hours: number;
}

export interface MusterKpi {
  total: number;
  present: number;
  late: number;
  absent: number;
  onLeave: number;
  wfh: number;
}

export interface MusterFilterOptions {
  departments: string[];
  locations: string[];
}

export interface MonthlyMusterPage {
  year: number;
  month: number;
  daysInMonth: number;
  dayColumns: MusterDayColumn[];
  summary: MusterKpi;
  filterOptions: MusterFilterOptions;
  items: MusterEmployeeRow[];
  total: number;
  page: number;
  pageSize: number;
}

export interface MonthlyMusterQuery {
  year: number;
  month: number;
  page?: number;
  pageSize?: number;
  search?: string;
  department?: string;
  location?: string;
  employmentStatus?: EmploymentStatus | '';
}

export type ExceptionType =
  | 'Missing Punch'
  | 'Late Arrival'
  | 'Early Exit'
  | 'Short Hours'
  | 'Absent';

export type ExceptionReviewStatus = 'Pending' | 'Resolved';
export type ExceptionTab = 'all' | 'pending' | 'resolved';

export interface AttendanceExceptionRow {
  id: number;
  employeeId: number;
  employeeCode: string;
  employeeName: string;
  department: string;
  location: string;
  date: string;
  shift: string;
  firstIn: string | null;
  lastOut: string | null;
  exceptionType: ExceptionType;
  expectedHours: string;
  actualHours: string | null;
  status: ExceptionReviewStatus;
  remark: string;
}

export interface ExceptionKpi {
  total: number;
  missingPunch: number;
  lateArrival: number;
  earlyExit: number;
  shortHours: number;
  absent: number;
}

export interface ExceptionFilterOptions {
  departments: string[];
  locations: string[];
  exceptionTypes: ExceptionType[];
}

export interface AttendanceExceptionsList {
  dateFrom: string;
  dateTo: string;
  summary: ExceptionKpi;
  filterOptions: ExceptionFilterOptions;
  items: AttendanceExceptionRow[];
  total: number;
  page: number;
  pageSize: number;
  pendingCount: number;
  resolvedCount: number;
}

export interface AttendanceExceptionsQuery {
  from: string;
  to: string;
  page?: number;
  pageSize?: number;
  search?: string;
  department?: string;
  location?: string;
  exceptionType?: ExceptionType | '';
  status?: ExceptionReviewStatus | '';
  statusTab?: ExceptionTab;
}

export type RegularizationRequestType =
  | 'Missed Punch'
  | 'Wrong Attendance'
  | 'Early Exit'
  | 'WFH Correction'
  | 'Late Arrival'
  | 'Holiday Work';

export type RegularizationStatus = 'Pending' | 'Approved' | 'Rejected';
export type RegularizationTab = 'pending' | 'approved' | 'rejected' | 'all';

export interface RegularizationRow {
  id: number;
  employeeId: number;
  employeeCode: string;
  employeeName: string;
  department: string;
  location: string;
  reportingManager?: string;
  designation?: string;
  shift?: string;
  attendanceDate: string;
  requestType: RegularizationRequestType;
  originalIn: string | null;
  originalOut: string | null;
  originalStatus?: string | null;
  requestedIn: string | null;
  requestedOut: string | null;
  requestedStatus?: string;
  reason: string;
  submittedOn: string;
  status: RegularizationStatus;
  rejectionReason: string | null;
  attachmentName: string | null;
}

export interface RegularizationKpi {
  total: number;
  pending: number;
  approved: number;
  rejected: number;
}

export interface RegularizationFilterOptions {
  departments: string[];
  locations: string[];
  requestTypes: RegularizationRequestType[];
}

export interface RegularizationPage {
  dateFrom: string;
  dateTo: string;
  summary: RegularizationKpi;
  filterOptions: RegularizationFilterOptions;
  items: RegularizationRow[];
  total: number;
  page: number;
  pageSize: number;
  pendingCount: number;
  approvedCount: number;
  rejectedCount: number;
}

export interface RegularizationQuery {
  from: string;
  to: string;
  page?: number;
  pageSize?: number;
  search?: string;
  department?: string;
  location?: string;
  requestType?: RegularizationRequestType | '';
  statusTab?: RegularizationTab;
  /** `team` = employees who report to the signed-in manager. */
  scope?: 'all' | 'team' | 'self';
}

export interface RegularizationCreate {
  employeeId: number;
  attendanceDate: string;
  requestType: RegularizationRequestType;
  requestedIn?: string | null;
  requestedOut?: string | null;
  reason: string;
  attachmentName?: string | null;
}

export type WeekdayCode = 'MON' | 'TUE' | 'WED' | 'THU' | 'FRI' | 'SAT' | 'SUN';

export interface ShiftItem {
  id: number;
  code: string;
  name: string;
  startTime: string;
  endTime: string;
  workHours: string;
  graceMinutes: number;
  halfDayHours: number | null;
  isActive: boolean;
  isOvernight: boolean;
  rowVersion: string;
}

export interface ShiftWrite {
  code: string;
  name: string;
  startTime: string;
  endTime: string;
  graceMinutes: number;
  halfDayHours?: number | null;
  isActive: boolean;
}

export interface ShiftSummary {
  total: number;
  active: number;
  inactive: number;
}

export interface ShiftPage {
  items: ShiftItem[];
  summary: ShiftSummary;
  total: number;
  page: number;
  pageSize: number;
}

export interface ShiftListQuery {
  page?: number;
  pageSize?: number;
  search?: string;
  activeOnly?: boolean | null;
}

export interface AttendanceRules {
  standardWorkHours: number;
  workingDaysPerWeek: number;
  lateArrivalGraceMinutes: number;
  earlyExitGraceMinutes: number;
  graceDaysPerMonth: number;
  otAfterHours: number;
  otApprovalRequired: boolean;
  weeklyOffDays: WeekdayCode[];
  weeklyOffAppliesTo: string;
  autoAttendanceEnabled: boolean;
  manualAttendanceEnabled: boolean;
  leaveYearLabel: string;
  holidayCount: number;
  rowVersion: string | null;
}

export interface AttendanceRulesWrite {
  standardWorkHours: number;
  workingDaysPerWeek: number;
  lateArrivalGraceMinutes: number;
  earlyExitGraceMinutes: number;
  graceDaysPerMonth: number;
  otAfterHours: number;
  otApprovalRequired: boolean;
  weeklyOffDays: WeekdayCode[];
  weeklyOffAppliesTo: string;
  autoAttendanceEnabled: boolean;
  manualAttendanceEnabled: boolean;
}

export interface LeaveYearInfo {
  yearBasis: 'FINANCIAL' | 'CALENDAR';
  year: number;
  label: string;
  startDate: string;
  endDate: string;
}

export interface ShiftAssignmentItem {
  id: number;
  employeeId: number;
  employeeCode: string;
  employeeName: string;
  department: string;
  shiftId: number;
  shiftCode: string;
  shiftName: string;
  weeklyOffDays: WeekdayCode[];
  fromDate: string;
  toDate: string | null;
  isCurrent: boolean;
  isActive: boolean;
  rowVersion: string;
}

export interface ShiftAssignmentWrite {
  employeeId: number;
  shiftId: number;
  fromDate: string;
  toDate?: string | null;
  weeklyOffDays?: WeekdayCode[] | null;
  isActive: boolean;
}

export interface ShiftAssignmentBulkWrite {
  shiftId: number;
  fromDate: string;
  toDate?: string | null;
  weeklyOffDays?: WeekdayCode[] | null;
  allEmployees: boolean;
  employeeIds: number[];
}

export interface ShiftAssignmentBulkResult {
  assigned: number;
}

export interface ShiftAssignmentPage {
  items: ShiftAssignmentItem[];
  total: number;
  page: number;
  pageSize: number;
}

export interface ShiftAssignmentListQuery {
  page?: number;
  pageSize?: number;
  search?: string;
  currentOnly?: boolean;
  employeeId?: number;
  shiftId?: number;
}

export interface ShiftAssignmentEmployeeOption {
  id: number;
  employeeCode: string;
  employeeName: string;
  department: string;
}

export interface ShiftAssignmentOptions {
  employees: ShiftAssignmentEmployeeOption[];
  shifts: ShiftItem[];
}

export interface AttendanceHolidayItem {
  id: number;
  holidayDate: string;
  name: string;
  holidayType: 'National' | 'Festival' | 'Optional';
  category: 'National' | 'Festival' | 'Regional' | 'Optional';
  appliesTo: string;
  isActive: boolean;
}

export interface AttendanceHolidayPage {
  leaveYear: LeaveYearInfo;
  items: AttendanceHolidayItem[];
  total: number;
}

export type FinalizationGroupBy = 'department' | 'location';
export type FinalizationRowStatus = 'Ready' | 'Review' | 'Pending';
export type FollowupStatus = 'Pending' | 'In Progress' | 'Completed' | 'Overdue';

export interface FinalizationTarget {
  employeeId: number;
  employeeCode: string;
  employeeName: string;
  detail: string;
  recipientUserId: number | null;
  recipientName: string;
}

export interface FinalizationReminder {
  id: number;
  sentAt: string | null;
  recipientName: string;
  status: string;
  errorMessage: string | null;
  message: string;
}

export interface FinalizationAssignee {
  userId: number;
  name: string;
}

export interface FinalizationQuery {
  year: number;
  month: number;
  groupBy?: FinalizationGroupBy;
}

export interface FinalizationKpi {
  totalEmployees: number;
  attendanceReady: number;
  withExceptions: number;
  pendingRegularization: number;
  finalized: number;
}

export interface FinalizationSummary {
  year: number;
  month: number;
  monthLabel: string;
  totalEmployees: number;
  attendanceReady: number;
  attendanceReadyPct: number;
  withExceptions: number;
  withExceptionsPct: number;
  pendingRegularization: number;
  pendingRegularizationPct: number;
  isFinalized: boolean;
  finalizedAt: string | null;
  finalizedByUserId: number | null;
}

export interface FinalizationChecklistItem {
  id: string;
  label: string;
  done: boolean;
  detail: string;
  route: string;
  status: FollowupStatus;
  ownerUserId: number | null;
  ownerName: string;
  dueDate: string | null;
  comment: string;
  targets: FinalizationTarget[];
  reminders: FinalizationReminder[];
}

export interface FinalizationGroupRow {
  id: number;
  name: string;
  employees: number;
  present: number;
  absent: number;
  leave: number;
  exceptions: number;
  pendingRegularization: number;
  readiness: number;
  status: FinalizationRowStatus;
}

export interface FinalizationPage {
  year: number;
  month: number;
  groupBy: FinalizationGroupBy;
  kpi: FinalizationKpi;
  summary: FinalizationSummary;
  checklist: FinalizationChecklistItem[];
  groups: FinalizationGroupRow[];
  assignees: FinalizationAssignee[];
  canFinalize: boolean;
  isFinalized: boolean;
}

export interface FinalizationFollowupWrite {
  year: number;
  month: number;
  checklistId: string;
  ownerUserId: number | null;
  dueDate: string | null;
  comment: string;
}

export interface FinalizationRemindWrite {
  year: number;
  month: number;
  checklistId?: string | null;
}

export interface FinalizationRemindResult {
  sent: number;
  skipped: number;
  failed: number;
  message: string;
}

export interface FinalizationLockResult {
  year: number;
  month: number;
  monthLabel: string;
  isFinalized: boolean;
  finalizedAt: string | null;
  finalizedByUserId: number | null;
  employeeCount: number;
  persistedDays?: number;
  message: string;
}

export interface AttendanceDashboardKpi {
  total: number;
  present: number;
  presentPct: number;
  absent: number;
  absentPct: number;
  onLeave?: number;
  late: number;
  latePct: number;
  earlyExit: number;
  earlyExitPct: number;
  shortHours: number;
  shortHoursPct: number;
}

export interface AttendanceDashboardOverviewSlice {
  label: string;
  count: number;
  percent: number;
  color: string;
}

export interface AttendanceDashboardTrendPoint {
  label: string;
  percent: number;
  date: string;
  present?: number;
  absent?: number;
  onLeave?: number;
}

export interface AttendanceDashboardLocationRow {
  location: string;
  employees: number;
  present: number;
  absent: number;
  attendancePct: number;
}

export interface AttendanceDashboardDepartmentRow {
  id: number;
  department: string;
  employees: number;
  present: number;
  absent: number;
  attendancePct: number;
}

export interface AttendanceDashboardExceptionItem {
  id: string;
  label: string;
  count: number;
  tone: string;
  icon: string;
  route: string;
}

export interface AttendanceDashboardQuickAction {
  id: string;
  label: string;
  icon: string;
  route: string;
}

export interface AttendanceDashboard {
  date: string;
  dateLabel: string;
  attendanceRate: number;
  kpi: AttendanceDashboardKpi;
  overview: AttendanceDashboardOverviewSlice[];
  trend: AttendanceDashboardTrendPoint[];
  departments: AttendanceDashboardDepartmentRow[];
  locations?: AttendanceDashboardLocationRow[];
  departmentOptions?: string[];
  locationOptions?: string[];
  exceptions: AttendanceDashboardExceptionItem[];
  exceptionsTotal: number;
  actions: AttendanceDashboardQuickAction[];
  isMonthFinalized: boolean;
}

export interface MineAttendanceDay {
  date: string;
  status: AttendanceStatus;
  firstIn: string | null;
  lastOut: string | null;
  firstInLate?: boolean;
  workingHours: string | null;
  /** Multi-session breakdown, e.g. `2h 21m + 0h 50m`. */
  workingHoursDetail?: string | null;
  /** Latest punch state — independent of attendance status. */
  currentPunch?: 'IN' | 'OUT' | null;
  currentPunchSince?: string | null;
  requiredHours?: string | null;
  shortfall?: string | null;
  /** Unmatched IN instant for live session ticking. */
  openInAt?: string | null;
  closedWorkedMinutes?: number;
  lateArrivalMinutes?: number | null;
  earlyExitMinutes?: number | null;
  shift: string;
  remarks: string;
  /** Exception for this day was resolved, so a new request is not offered. */
  resolved?: boolean;
  /** Accepted punches for the Attendance Details drawer. */
  punches?: AttendancePunch[];
}

export interface MineAttendanceSummary {
  present: number;
  late: number;
  absent: number;
  onLeave: number;
  offDay: number;
  holiday: number;
  missingPunch: number;
}

export interface MineAttendancePage {
  employeeId: number;
  employeeCode: string;
  employeeName: string;
  year: number;
  month: number;
  monthLabel: string;
  summary: MineAttendanceSummary;
  items: MineAttendanceDay[];
  regularizations: RegularizationRow[];
  isMonthFinalized: boolean;
  canRegularize: boolean;
}

export interface AttendanceReportsSummary {
  year: number;
  month: number;
  monthLabel: string;
  totalEmployees: number;
  present: number;
  late: number;
  absent: number;
  onLeave: number;
  wfh: number;
  pendingExceptions: number;
  pendingRegularizations: number;
  isMonthFinalized: boolean;
  finalizedAt: string | null;
}
