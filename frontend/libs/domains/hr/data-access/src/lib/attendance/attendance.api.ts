import { HttpClient, HttpParams } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { Observable } from 'rxjs';
import { ApiConfiguration } from '@trishul/core-api';

export type AttendanceStatus =
  | 'Present'
  | 'Late'
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
  status: AttendanceStatus;
  remarks: string;
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

  /** Mark exception resolved (sets hr.attendance.is_regularized when a row exists). */
  resolveException(exceptionId: number, remark?: string): Observable<AttendanceExceptionRow> {
    return this.http.post<AttendanceExceptionRow>(
      `${this.base}/exceptions/${exceptionId}/resolve`,
      remark ? { remark } : {},
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
    return this.http.get<RegularizationPage>(`${this.base}/regularizations`, { params });
  }

  createRegularization(body: RegularizationCreate): Observable<RegularizationRow> {
    return this.http.post<RegularizationRow>(`${this.base}/regularizations`, body);
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
  | 'Late Arrival';

export type RegularizationStatus = 'Pending' | 'Approved' | 'Rejected';
export type RegularizationTab = 'pending' | 'approved' | 'rejected' | 'all';

export interface RegularizationRow {
  id: number;
  employeeId: number;
  employeeCode: string;
  employeeName: string;
  department: string;
  location: string;
  attendanceDate: string;
  requestType: RegularizationRequestType;
  originalIn: string | null;
  originalOut: string | null;
  requestedIn: string | null;
  requestedOut: string | null;
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
