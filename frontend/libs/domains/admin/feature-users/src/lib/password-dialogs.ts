import { Clipboard } from '@angular/cdk/clipboard';
import {
  ChangeDetectionStrategy,
  Component,
  inject,
  signal,
} from '@angular/core';
import { FormsModule } from '@angular/forms';
import { MatButton } from '@angular/material/button';
import {
  MAT_DIALOG_DATA,
  MatDialog,
  MatDialogActions,
  MatDialogClose,
  MatDialogContent,
  MatDialogTitle,
} from '@angular/material/dialog';
import { MatIcon } from '@angular/material/icon';
import { MatRadioButton, MatRadioGroup } from '@angular/material/radio';
import { Observable } from 'rxjs';
import { PasswordDelivery } from '@trishul/admin-data-access';

/** Asks how the user gets their new password. Closes with the choice, or undefined. */
@Component({
  selector: 'trishul-password-reset-dialog',
  imports: [
    FormsModule,
    MatDialogTitle,
    MatDialogContent,
    MatDialogActions,
    MatDialogClose,
    MatButton,
    MatRadioGroup,
    MatRadioButton,
  ],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <h2 mat-dialog-title>Reset password</h2>
    <mat-dialog-content>
      <p>
        How should <strong>{{ data.email }}</strong> get a new password? Their
        current sessions end either way.
      </p>
      <mat-radio-group
        class="choices"
        aria-label="Delivery"
        [(ngModel)]="delivery"
      >
        <mat-radio-button value="email">
          Email them a reset code
        </mat-radio-button>
        <mat-radio-button value="show">
          Show me a temporary password to hand over
        </mat-radio-button>
      </mat-radio-group>
    </mat-dialog-content>
    <mat-dialog-actions align="end">
      <button mat-button mat-dialog-close>Cancel</button>
      <button mat-flat-button [mat-dialog-close]="delivery">
        Reset password
      </button>
    </mat-dialog-actions>
  `,
  styles: `
    .choices {
      display: flex;
      flex-direction: column;
      gap: 0.25rem;
    }
  `,
})
export class PasswordResetDialog {
  protected readonly data = inject<{ email: string }>(MAT_DIALOG_DATA);
  protected delivery: PasswordDelivery = 'email';
}

/** Shows a temporary password once, with a copy button. */
@Component({
  selector: 'trishul-temporary-password-dialog',
  imports: [
    MatDialogTitle,
    MatDialogContent,
    MatDialogActions,
    MatDialogClose,
    MatButton,
    MatIcon,
  ],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <h2 mat-dialog-title>Temporary password</h2>
    <mat-dialog-content>
      <p>
        Give this to <strong>{{ data.email }}</strong> privately. It is shown
        only now, and they must choose their own password when they first sign
        in.
      </p>
      <div class="password">
        <code data-testid="temporary-password">{{ data.password }}</code>
        <button mat-button (click)="copy()">
          <mat-icon>{{ copied() ? 'check' : 'content_copy' }}</mat-icon>
          {{ copied() ? 'Copied' : 'Copy' }}
        </button>
      </div>
    </mat-dialog-content>
    <mat-dialog-actions align="end">
      <button mat-flat-button mat-dialog-close>Done</button>
    </mat-dialog-actions>
  `,
  styles: `
    .password {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 0.5rem;
      padding: 0.5rem 0.75rem;
      border-radius: var(--mat-sys-corner-small);
      background: var(--mat-sys-surface-container-high);
    }
    code {
      font-size: 1.1rem;
      letter-spacing: 0.05em;
      user-select: all;
    }
  `,
})
export class TemporaryPasswordDialog {
  protected readonly data = inject<{ email: string; password: string }>(
    MAT_DIALOG_DATA,
  );
  private readonly clipboard = inject(Clipboard);
  protected readonly copied = signal(false);

  protected copy(): void {
    this.copied.set(this.clipboard.copy(this.data.password));
  }
}

export function choosePasswordDelivery(
  dialog: MatDialog,
  email: string,
): Observable<PasswordDelivery | undefined> {
  return dialog
    .open<PasswordResetDialog, { email: string }, PasswordDelivery>(
      PasswordResetDialog,
      { data: { email }, width: '30rem' },
    )
    .afterClosed();
}

export function showTemporaryPassword(
  dialog: MatDialog,
  email: string,
  password: string,
): Observable<void> {
  return dialog
    .open(TemporaryPasswordDialog, {
      data: { email, password },
      width: '30rem',
      disableClose: true, // the password is gone once closed
    })
    .afterClosed();
}
