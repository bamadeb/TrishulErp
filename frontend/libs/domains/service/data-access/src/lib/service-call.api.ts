import { Injectable, inject } from '@angular/core';
import { Observable } from 'rxjs';
import {
  ApiClient,
  PageServiceCallListItem,
  listServiceCalls,
} from '@trishul/core-api';
import { ServiceCallQuery } from './service-call.models';

@Injectable({ providedIn: 'root' })
export class ServiceCallApi {
  private readonly api = inject(ApiClient);

  list(query: ServiceCallQuery): Observable<PageServiceCallListItem> {
    return this.api.call(listServiceCalls, query);
  }
}
