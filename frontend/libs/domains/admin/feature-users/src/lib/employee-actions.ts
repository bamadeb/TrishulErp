import { Injectable, inject } from '@angular/core';
import { MatDialog } from '@angular/material/dialog';
import { MatSnackBar } from '@angular/material/snack-bar';
import { Observable, filter, switchMap, tap } from 'rxjs';
import {
  EmployeeDetail,
  EmployeeRow,
  EmployeesApi,
} from '@trishul/admin-data-access';
import { confirmAction } from '@trishul/shared-ui';

/** Deactivate / activate an employee, with confirmation and feedback; used by list and form. */
@Injectable({ providedIn: 'root' })
export class EmployeeActions {
  private readonly api = inject(EmployeesApi);
  private readonly dialog = inject(MatDialog);
  private readonly snackBar = inject(MatSnackBar);

  deactivate(employee: EmployeeRow): Observable<EmployeeDetail> {
    return confirmAction(this.dialog, {
      title: 'Deactivate employee?',
      message: `${employee.fullName} (${employee.employeeCode}) will be hidden from active lists. You can activate them again later.`,
      confirmText: 'Deactivate',
      destructive: true,
    }).pipe(
      filter(Boolean),
      switchMap(() => this.api.deactivate(employee.id)),
      tap(() => this.notify(`${employee.fullName} deactivated`)),
    );
  }

  activate(employee: EmployeeRow): Observable<EmployeeDetail> {
    return this.api
      .activate(employee.id)
      .pipe(tap(() => this.notify(`${employee.fullName} is active again`)));
  }

  notify(message: string): void {
    this.snackBar.open(message, 'OK', { duration: 5000 });
  }
}
