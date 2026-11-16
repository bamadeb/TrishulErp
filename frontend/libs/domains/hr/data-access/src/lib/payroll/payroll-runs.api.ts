import { HttpClient } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { Observable } from 'rxjs';
import { ApiConfiguration } from '@trishul/core-api';

export interface PayrollRunItem {
  id: number;
  periodMonth: string;
  runDate: string;
  status: 'Draft' | 'Processed' | 'Approved' | 'Paid' | 'Locked';
  employees: number;
  gross: string;
  deductions: string;
  netPay: string;
}

export interface PayrollLine {
  code: string;
  name: string;
  amount: string;
  source: string;
}

export interface PayrollEmployeeDetail {
  employeeId: number;
  employeeCode: string;
  fullName: string;
  department: string | null;
  designation: string | null;
  paidDays: string;
  lopDays: string;
  gross: string;
  deductions: string;
  netPay: string;
  lines: PayrollLine[];
}

export interface PayrollDifference {
  employeeCode: string;
  fullName: string;
  previousNet: string | null;
  nextNet: string | null;
  change: string;
}

export interface PayrollPreview {
  runId: number;
  status: PayrollRunItem['status'];
  previousEmployees: number;
  nextEmployees: number;
  previousGross: string;
  nextGross: string;
  previousDeductions: string;
  nextDeductions: string;
  previousNet: string;
  nextNet: string;
  differences: PayrollDifference[];
}

/** Payroll months calculated from saved salary structures. */
@Injectable({ providedIn: 'root' })
export class PayrollRunsApi {
  private readonly http = inject(HttpClient);
  private readonly config = inject(ApiConfiguration);

  list(): Observable<PayrollRunItem[]> {
    return this.http.get<PayrollRunItem[]>(`${this.config.rootUrl}/hr/payroll-runs`);
  }

  process(month: string): Observable<PayrollRunItem[]> {
    return this.http.post<PayrollRunItem[]>(`${this.config.rootUrl}/hr/payroll-runs`, { month });
  }

  details(runId: number): Observable<PayrollEmployeeDetail[]> {
    return this.http.get<PayrollEmployeeDetail[]>(`${this.config.rootUrl}/hr/payroll-runs/${runId}`);
  }

  preview(runId: number): Observable<PayrollPreview> {
    return this.http.get<PayrollPreview>(`${this.config.rootUrl}/hr/payroll-runs/${runId}/preview`);
  }

  recalculate(runId: number): Observable<PayrollRunItem> {
    return this.http.post<PayrollRunItem>(`${this.config.rootUrl}/hr/payroll-runs/${runId}/recalculate`, {});
  }
}
