import { Injectable, inject } from '@angular/core';
import { Observable } from 'rxjs';
import {
  ApiClient,
  PageCustomerListItem,
  activateCustomer,
  createCustomer,
  deactivateCustomer,
  getCustomer,
  getCustomerFormOptions,
  listCustomers,
  updateCustomer,
  withRowVersion,
} from '@trishul/core-api';
import {
  CustomerCreate,
  CustomerDetail,
  CustomerFormOptions,
  CustomerQuery,
  CustomerUpdate,
} from './customers.models';

/** /core/customers and the form's option lists, through ApiClient and the generated functions. */
@Injectable({ providedIn: 'root' })
export class CustomersApi {
  private readonly api = inject(ApiClient);

  list(query: CustomerQuery): Observable<PageCustomerListItem> {
    return this.api.call(listCustomers, query);
  }

  get(customerId: number): Observable<CustomerDetail> {
    return this.api.call(getCustomer, { customerId });
  }

  create(body: CustomerCreate): Observable<CustomerDetail> {
    return this.api.call(createCustomer, { body });
  }

  /** rowVersion from when the customer was loaded; a newer change by someone else gives 409. */
  update(
    customerId: number,
    rowVersion: string,
    body: CustomerUpdate,
  ): Observable<CustomerDetail> {
    return this.api.call(
      updateCustomer,
      { customerId, body },
      withRowVersion(rowVersion),
    );
  }

  deactivate(customerId: number): Observable<CustomerDetail> {
    return this.api.call(deactivateCustomer, { customerId });
  }

  activate(customerId: number): Observable<CustomerDetail> {
    return this.api.call(activateCustomer, { customerId });
  }

  formOptions(): Observable<CustomerFormOptions> {
    return this.api.call(getCustomerFormOptions);
  }
}
