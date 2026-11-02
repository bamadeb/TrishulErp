import {
  ChangeDetectionStrategy,
  Component,
  Signal,
  computed,
  inject,
} from '@angular/core';
import { MatButton } from '@angular/material/button';
import {
  MAT_DIALOG_DATA,
  MatDialogActions,
  MatDialogContent,
  MatDialogRef,
  MatDialogTitle,
} from '@angular/material/dialog';

export interface IdleWarningData {
  secondsLeft: Signal<number>;
}

/** Shown a minute before the idle sign-out. Closes with true to stay signed in, false to sign out now. */
@Component({
  selector: 'trishul-idle-warning-dialog',
  imports: [MatDialogTitle, MatDialogContent, MatDialogActions, MatButton],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <h2 mat-dialog-title>Are you still there?</h2>
    <mat-dialog-content>
      <p role="timer" aria-live="polite">
        You have been inactive for a while. For security you will be signed
        out in <b>{{ countdown() }}</b>.
      </p>
    </mat-dialog-content>
    <mat-dialog-actions align="end">
      <button mat-button type="button" (click)="dialogRef.close(false)">
        Sign out
      </button>
      <button mat-flat-button type="button" (click)="dialogRef.close(true)">
        Stay signed in
      </button>
    </mat-dialog-actions>
  `,
  styles: `
    p {
      margin: 0;
    }
    b {
      font-variant-numeric: tabular-nums;
    }
  `,
})
export class IdleWarningDialog {
  protected readonly dialogRef =
    inject<MatDialogRef<IdleWarningDialog, boolean>>(MatDialogRef);
  private readonly data = inject<IdleWarningData>(MAT_DIALOG_DATA);

  protected readonly countdown = computed(() => {
    const seconds = Math.max(0, this.data.secondsLeft());
    return `${Math.floor(seconds / 60)}:${String(seconds % 60).padStart(2, '0')}`;
  });
}
