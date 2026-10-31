import { Injectable, inject } from '@angular/core';
import { Observable, map } from 'rxjs';
import {
  ApiClient,
  CustomerListItem,
  EngineerOption,
  LookupValueOut,
  MachineUnitOption,
  PageServiceCallListItem,
  ServiceCallCreate,
  ServiceCallDetail,
  ServiceCallListItem,
  ServiceCallTriageUpdate,
  createServiceCall,
  getServiceCall,
  listCustomers,
  listEngineerOptions,
  listLookupValues,
  listMachineOptions,
  listServiceCalls,
  updateServiceCallTriage,
  withRowVersion,
} from '@trishul/core-api';
import { ServiceCallQuery } from './service-call.models';

@Injectable({ providedIn: 'root' })
export class ServiceCallApi {
  private readonly api = inject(ApiClient);

  list(query: ServiceCallQuery): Observable<PageServiceCallListItem> {
    return this.api.call(listServiceCalls, query);
  }

  get(callId: number): Observable<ServiceCallDetail> {
    return this.api.call(getServiceCall, { callId });
  }

  create(body: ServiceCallCreate): Observable<ServiceCallListItem> {
    return this.api.call(createServiceCall, { body });
  }

  /** Machines to pick for a new call; narrowed to the selected brand, optionally to one customer. */
  machineOptions(
    search: string,
    customerId?: number,
  ): Observable<MachineUnitOption[]> {
    return this.api.call(listMachineOptions, { search, customerId });
  }

  /** Customers matching a search, for the call form's customer picker. */
  customers(search: string): Observable<CustomerListItem[]> {
    return this.api
      .call(listCustomers, { search, page: 1, pageSize: 20, status: 'active' })
      .pipe(map((page) => page.items));
  }

  /** Values of an editable dropdown (e.g. CALL_TYPE, CALL_SOURCE). */
  lookups(typeCode: string): Observable<LookupValueOut[]> {
    return this.api.call(listLookupValues, { typeCode });
  }

  /** Engineers a team lead can assign a call to (the selected branch). */
  engineerOptions(search = ''): Observable<EngineerOption[]> {
    return this.api.call(listEngineerOptions, { search });
  }

  /** Team-lead triage: reassign and/or re-prioritise. rowVersion guards against a stale change (409). */
  updateTriage(
    callId: number,
    rowVersion: string,
    body: ServiceCallTriageUpdate,
  ): Observable<ServiceCallListItem> {
    return this.api.call(
      updateServiceCallTriage,
      { callId, body },
      withRowVersion(rowVersion),
    );
  }
}
