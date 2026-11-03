import { Injectable, inject } from '@angular/core';
import { MatDialog } from '@angular/material/dialog';
import { MatSnackBar } from '@angular/material/snack-bar';
import { Observable, filter, switchMap, tap } from 'rxjs';
import { TeamDetail, TeamRow, TeamsApi } from '@trishul/admin-data-access';
import { confirmAction } from '@trishul/shared-ui';

/** Deactivate / activate a team, with confirmation and feedback; used by list and form. */
@Injectable({ providedIn: 'root' })
export class TeamActions {
  private readonly api = inject(TeamsApi);
  private readonly dialog = inject(MatDialog);
  private readonly snackBar = inject(MatSnackBar);

  deactivate(team: TeamRow): Observable<TeamDetail> {
    return confirmAction(this.dialog, {
      title: 'Deactivate team?',
      message:
        `${team.teamLeadName} will no longer see the service calls of ${team.name}'s engineers, ` +
        'and its members can join another team. You can activate it again later.',
      confirmText: 'Deactivate',
      destructive: true,
    }).pipe(
      filter(Boolean),
      switchMap(() => this.api.deactivate(team.id)),
      tap(() => this.notify(`${team.name} deactivated`)),
    );
  }

  activate(team: TeamRow): Observable<TeamDetail> {
    return this.api
      .activate(team.id)
      .pipe(tap(() => this.notify(`${team.name} is active again`)));
  }

  notify(message: string): void {
    this.snackBar.open(message, 'OK', { duration: 5000 });
  }
}
