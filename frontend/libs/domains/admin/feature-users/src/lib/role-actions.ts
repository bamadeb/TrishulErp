import { Injectable, inject } from '@angular/core';
import { MatDialog } from '@angular/material/dialog';
import { MatSnackBar } from '@angular/material/snack-bar';
import { Observable, filter, switchMap, tap } from 'rxjs';
import { RoleDetail, RoleRow, RolesApi } from '@trishul/admin-data-access';
import { confirmAction } from '@trishul/shared-ui';

/** Deactivate / activate a role, with confirmation and feedback; used by list and form. */
@Injectable({ providedIn: 'root' })
export class RoleActions {
  private readonly api = inject(RolesApi);
  private readonly dialog = inject(MatDialog);
  private readonly snackBar = inject(MatSnackBar);

  deactivate(role: RoleRow): Observable<RoleDetail> {
    const users = role.userCount;
    const impact = users
      ? `${users} ${users === 1 ? 'user loses' : 'users lose'} the permissions this role gives, straight away.`
      : 'No active user holds this role.';
    return confirmAction(this.dialog, {
      title: 'Deactivate role?',
      message: `${role.name} (${role.code}) can no longer be given to users. ${impact} You can activate it again later.`,
      confirmText: 'Deactivate',
      destructive: true,
    }).pipe(
      filter(Boolean),
      switchMap(() => this.api.deactivate(role.id)),
      tap(() => this.notify(`${role.name} deactivated`)),
    );
  }

  activate(role: RoleRow): Observable<RoleDetail> {
    return this.api
      .activate(role.id)
      .pipe(tap(() => this.notify(`${role.name} is active again`)));
  }

  notify(message: string): void {
    this.snackBar.open(message, 'OK', { duration: 5000 });
  }
}
