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
}
