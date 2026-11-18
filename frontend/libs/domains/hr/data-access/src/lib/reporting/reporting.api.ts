import { HttpClient } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { Observable } from 'rxjs';
import { ApiConfiguration, withoutErrorToast } from '@trishul/core-api';

export interface ReportingPerson {
  id: number;
  code: string;
  name: string;
  designation: string;
  department: string;
  location: string;
  managerId: number | null;
  level: string;
  status: 'Active' | 'Inactive';
  /** Set when the live manager change starts after today. */
  managerEffectiveFrom?: string | null;
}

export interface ReportingAssignmentWrite {
  employeeId: number;
  reportingManagerId: number;
  effectiveFrom: string;
  remarks: string | null;
}

export interface ReportingAssignmentSaved {
  employeeId: number;
  previousManagerId: number | null;
  managerId: number | null;
  effectiveFrom: string;
  remarks: string | null;
}

export interface ReportingRemovalWrite {
  employeeId: number;
  effectiveFrom: string;
  remarks: string;
}

export interface ReportingHistoryItem {
  id: number;
  previousManagerId: number | null;
  previousManagerName: string | null;
  managerId: number | null;
  managerName: string | null;
  effectiveFrom: string;
  effectiveTo: string | null;
  remarks: string | null;
  changedBy: string | null;
  status: 'Active' | 'Closed';
  createdAt: string;
}

/** Live reporting employees and the save-assignment call. */
@Injectable({ providedIn: 'root' })
export class ReportingApi {
  private readonly http = inject(HttpClient);
  private readonly config = inject(ApiConfiguration);

  list(): Observable<ReportingPerson[]> {
    return this.http.get<ReportingPerson[]>(`${this.config.rootUrl}/hr/reporting/employees`);
  }

  history(employeeId: number): Observable<ReportingHistoryItem[]> {
    return this.http.get<ReportingHistoryItem[]>(`${this.config.rootUrl}/hr/reporting/employees/${employeeId}/history`);
  }

  /** Writes core.employee.reporting_manager_id and the assignment history. */
  assign(body: ReportingAssignmentWrite): Observable<ReportingAssignmentSaved> {
    return this.http.post<ReportingAssignmentSaved>(
      `${this.config.rootUrl}/hr/reporting/assignments`,
      body,
      { context: withoutErrorToast() },
    );
  }

  /** Clears the live manager and keeps the closed assignment in history. */
  remove(body: ReportingRemovalWrite): Observable<ReportingAssignmentSaved> {
    return this.http.post<ReportingAssignmentSaved>(`${this.config.rootUrl}/hr/reporting/removals`, body, {
      context: withoutErrorToast(),
    });
  }
}
