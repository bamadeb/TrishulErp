import { Injectable, inject } from '@angular/core';
import { Observable } from 'rxjs';
import {
  ApiClient,
  GetTadaEmployees$Params,
  GetTadaReport$Params,
  TadaBulkResult,
  TadaDecisionCreate,
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
  getTadaEmployees,
  getTadaReport,
  getTadaTrip,
  listTadaEmployeeTrips,
} from '@trishul/core-api';

/** TA/DA employee summary, trip lines, rates and approval actions. */
@Injectable({ providedIn: 'root' })
export class TadaApi {
  private readonly api = inject(ApiClient);

  employees(params: GetTadaEmployees$Params): Observable<TadaEmployeeReport> {
    return this.api.call(getTadaEmployees, params);
  }

  employeeTrips(employeeId: number, month: string): Observable<TadaTripItem[]> {
    return this.api.call(listTadaEmployeeTrips, { employeeId, month });
  }

  report(params: GetTadaReport$Params): Observable<TadaReport> {
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
}
