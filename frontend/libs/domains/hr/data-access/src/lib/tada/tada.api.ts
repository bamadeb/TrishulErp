import { HttpClient, HttpParams } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { Observable } from 'rxjs';
import {
  ApiClient,
  ApiConfiguration,
  GetTadaEmployees$Params,
  GetTadaReport$Params,
  TadaBulkResult,
  TadaDecisionCreate,
  TadaDecisionHistoryItem,
  TadaEmployeeReport,
  TadaRates,
  TadaRatesUpdate,
  TadaReport,
  TadaSettlementCreate,
  TadaTripDetail,
  TadaTripItem,
  createTadaDecisions,
  createTadaRates,
  createTadaSettlements,
  createTadaTripDecision,
  getTadaEmployees,
  getTadaReport,
  getTadaTrip,
  listTadaEmployeeHistory,
  listTadaEmployeeTrips,
} from '@trishul/core-api';

/** TA/DA employee summary, trip lines, rates and approval actions. */
@Injectable({ providedIn: 'root' })
export class TadaApi {
  private readonly api = inject(ApiClient);
  private readonly http = inject(HttpClient);
  private readonly config = inject(ApiConfiguration);

  employees(params: GetTadaEmployees$Params & { includeSummary?: boolean }): Observable<TadaEmployeeReport> {
    if (params.includeSummary === false) {
      return this.http.get<TadaEmployeeReport>(`${this.config.rootUrl}/hr/tada/employees`, {
        params: this.queryParams(params),
      });
    }
    return this.api.call(getTadaEmployees, params);
  }

  employeeTrips(employeeId: number, month: string): Observable<TadaTripItem[]> {
    return this.api.call(listTadaEmployeeTrips, { employeeId, month });
  }

  /** Same trips endpoint, narrowed inside the payroll month. */
  filterEmployeeTrips(
    employeeId: number,
    month: string,
    filters: { fromDate: string; toDate: string; status: string; search: string },
  ): Observable<TadaTripItem[]> {
    let params = new HttpParams().set('month', month).set('fromDate', filters.fromDate).set('toDate', filters.toDate);
    if (filters.status && filters.status !== 'All') params = params.set('status', filters.status);
    if (filters.search) params = params.set('search', filters.search);
    return this.http.get<TadaTripItem[]>(`${this.config.rootUrl}/hr/tada/employees/${employeeId}/trips`, { params });
  }

  history(employeeId: number, month: string): Observable<TadaDecisionHistoryItem[]> {
    return this.api.call(listTadaEmployeeHistory, { employeeId, month });
  }

  report(params: GetTadaReport$Params & { includeSummary?: boolean }): Observable<TadaReport> {
    if (params.includeSummary === false) {
      return this.http.get<TadaReport>(`${this.config.rootUrl}/hr/tada/report`, {
        params: this.queryParams(params),
      });
    }
    return this.api.call(getTadaReport, params);
  }

  trip(tripId: number): Observable<TadaTripDetail> {
    return this.api.call(getTadaTrip, { tripId });
  }

  saveRates(body: TadaRatesUpdate): Observable<TadaRates> {
    return this.api.call(createTadaRates, { body });
  }

  decide(body: TadaDecisionCreate): Observable<TadaBulkResult> {
    return this.api.call(createTadaDecisions, { body });
  }

  settle(body: TadaSettlementCreate): Observable<TadaBulkResult> {
    return this.api.call(createTadaSettlements, { body });
  }

  decideTrip(tripId: number, decision: 'Approved' | 'Rejected', remarks: string | null): Observable<TadaTripDetail> {
    return this.api.call(createTadaTripDecision, { tripId, body: { decision, remarks } });
  }

  document(attachmentId: number): Observable<Blob> {
    return this.http.get(`${this.config.rootUrl}/hr/tada/documents/${attachmentId}`, { responseType: 'blob' });
  }

  private queryParams(values: object): HttpParams {
    let params = new HttpParams();
    for (const [key, value] of Object.entries(values)) {
      if (value != null && value !== '') params = params.set(key, String(value));
    }
    return params;
  }
}
