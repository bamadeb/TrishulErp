import { Injectable, inject } from '@angular/core';
import { MatDialog } from '@angular/material/dialog';
import { MatSnackBar } from '@angular/material/snack-bar';
import { EMPTY, Observable, filter, switchMap, tap } from 'rxjs';
import { UserDetail, UserRow, UsersApi } from '@trishul/admin-data-access';
import { confirmAction } from '@trishul/shared-ui';
import {
  choosePasswordDelivery,
  showTemporaryPassword,
} from './password-dialogs';

/** Deactivate / activate / reset password, with confirmation and feedback; used by list and form. */
@Injectable({ providedIn: 'root' })
export class UserActions {
  private readonly api = inject(UsersApi);
  private readonly dialog = inject(MatDialog);
  private readonly snackBar = inject(MatSnackBar);

  deactivate(user: UserRow): Observable<UserDetail> {
    return confirmAction(this.dialog, {
      title: 'Deactivate user?',
      message: `${user.username} won't be able to sign in, and any open sessions end now. You can activate them again later.`,
      confirmText: 'Deactivate',
      destructive: true,
    }).pipe(
      filter(Boolean),
      switchMap(() => this.api.deactivate(user.id)),
      tap(() => this.notify(`${user.username} deactivated`)),
    );
  }

  activate(user: UserRow): Observable<UserDetail> {
    return this.api
      .activate(user.id)
      .pipe(tap(() => this.notify(`${user.username} can sign in again`)));
  }

  resetPassword(user: UserRow): Observable<unknown> {
    return choosePasswordDelivery(this.dialog, user.username).pipe(
      switchMap((delivery) =>
        delivery ? this.api.resetPassword(user.id, delivery) : EMPTY,
      ),
      switchMap((result) => {
        if (result.temporaryPassword) {
          return showTemporaryPassword(
            this.dialog,
            user.username,
            result.temporaryPassword,
          );
        }
        this.notify(`Password reset email sent to ${user.username}`);
        return EMPTY;
      }),
    );
  }

  notify(message: string): void {
    this.snackBar.open(message, 'OK', { duration: 5000 });
  }
}
