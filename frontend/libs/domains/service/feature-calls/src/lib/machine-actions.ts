import { Injectable, inject } from '@angular/core';
import { MatDialog } from '@angular/material/dialog';
import { MatSnackBar } from '@angular/material/snack-bar';
import { Observable, filter, switchMap, tap } from 'rxjs';
import {
  MachineApi,
  MachineDetail,
  MachineRow,
} from '@trishul/service-data-access';
import { confirmAction } from '@trishul/shared-ui';

/** Deactivate / activate a machine, with confirmation and feedback; used by list and form. */
@Injectable({ providedIn: 'root' })
export class MachineActions {
  private readonly api = inject(MachineApi);
  private readonly dialog = inject(MatDialog);
  private readonly snackBar = inject(MatSnackBar);

  deactivate(machine: MachineRow): Observable<MachineDetail> {
    return confirmAction(this.dialog, {
      title: 'Deactivate machine?',
      message: `${machine.serialNumber} (${machine.modelName}) can no longer be chosen for new service calls. Calls already logged against it keep it. You can activate it again later.`,
      confirmText: 'Deactivate',
      destructive: true,
    }).pipe(
      filter(Boolean),
      switchMap(() => this.api.deactivate(machine.id)),
      tap(() => this.notify(`${machine.serialNumber} deactivated`)),
    );
  }

  activate(machine: MachineRow): Observable<MachineDetail> {
    return this.api
      .activate(machine.id)
      .pipe(tap(() => this.notify(`${machine.serialNumber} is active again`)));
  }

  notify(message: string): void {
    this.snackBar.open(message, 'OK', { duration: 5000 });
  }
}
