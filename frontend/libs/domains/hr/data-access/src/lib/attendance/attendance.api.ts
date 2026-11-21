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

export interface AttendancePunch {
  kind: AttendancePunchKind;
  at: string;
  device: string;
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
}

@Injectable({ providedIn: 'root' })
export class AttendanceApi {
  private readonly http = inject(HttpClient);
  private readonly config = inject(ApiConfiguration);

  private get base(): string {
    return `${this.config.rootUrl}/hr/attendance`;
  }

  listDaily(query: DailyAttendanceQuery): Observable<DailyAttendancePage> {
    let params = new HttpParams()
      .set('date', query.date)
      .set('page', String(query.page ?? 1))
      .set('pageSize', String(query.pageSize ?? 20))
      .set('statusTab', query.statusTab ?? 'all');
    if (query.search?.trim()) params = params.set('search', query.search.trim());
    if (query.department) params = params.set('department', query.department);
    if (query.location) params = params.set('location', query.location);
    if (query.shift) params = params.set('shift', query.shift);
    if (query.status) params = params.set('status', query.status);
    if (query.employeeType) params = params.set('employeeType', query.employeeType);
    if (query.reportingManager) params = params.set('reportingManager', query.reportingManager);
    return this.http.get<DailyAttendancePage>(`${this.base}/daily`, { params });
  }
}
