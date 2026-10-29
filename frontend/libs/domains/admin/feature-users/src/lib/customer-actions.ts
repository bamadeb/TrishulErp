import { Injectable, inject } from '@angular/core';
import { MatDialog } from '@angular/material/dialog';
import { MatSnackBar } from '@angular/material/snack-bar';
import { Observable, filter, switchMap, tap } from 'rxjs';
import {
  CustomerDetail,
  CustomerRow,
  CustomersApi,
} from '@trishul/admin-data-access';
import { confirmAction } from '@trishul/shared-ui';

/** Deactivate / activate a customer, with confirmation and feedback; used by list and form. */
@Injectable({ providedIn: 'root' })
export class CustomerActions {
  private readonly api = inject(CustomersApi);
  private readonly dialog = inject(MatDialog);
  private readonly snackBar = inject(MatSnackBar);

  deactivate(customer: CustomerRow): Observable<CustomerDetail> {
    return confirmAction(this.dialog, {
      title: 'Deactivate customer?',
      message: `${customer.name} (${customer.code}) will be hidden from active lists. You can activate them again later.`,
      confirmText: 'Deactivate',
      destructive: true,
    }).pipe(
      filter(Boolean),
      switchMap(() => this.api.deactivate(customer.id)),
      tap(() => this.notify(`${customer.name} deactivated`)),
    );
  }

  activate(customer: CustomerRow): Observable<CustomerDetail> {
    return this.api
      .activate(customer.id)
      .pipe(tap(() => this.notify(`${customer.name} is active again`)));
  }

  notify(message: string): void {
    this.snackBar.open(message, 'OK', { duration: 5000 });
  }
}
