import { HttpErrorResponse } from '@angular/common/http';
import { ChangeDetectionStrategy, Component, inject, signal } from '@angular/core';
import {
  AbstractControl,
  NonNullableFormBuilder,
  ReactiveFormsModule,
  ValidationErrors,
  Validators,
} from '@angular/forms';
import { MatButton, MatIconButton } from '@angular/material/button';
import {
  MatDialogActions,
  MatDialogContent,
  MatDialogRef,
  MatDialogTitle,
} from '@angular/material/dialog';
import {
  MatError,
  MatFormField,
  MatHint,
  MatLabel,
  MatSuffix,
} from '@angular/material/form-field';
import { MatIcon } from '@angular/material/icon';
import { MatInput } from '@angular/material/input';
import { MatProgressBar } from '@angular/material/progress-bar';
import {
  ApiClient,
  ProblemDetails,
  changeMyPassword,
  withoutErrorToast,
} from '@trishul/core-api';
import { finalize } from 'rxjs';

/** The two new-password boxes must match. */
function sameNewPassword(group: AbstractControl): ValidationErrors | null {
  const { newPassword, confirmPassword } = group.value as {
    newPassword: string;
    confirmPassword: string;
  };
  return confirmPassword && newPassword !== confirmPassword
    ? { mismatch: true }
    : null;
}

/** The signed-in user changes their own password; the current password is required. */
@Component({
  selector: 'trishul-change-password-dialog',
  imports: [
    ReactiveFormsModule,
    MatDialogTitle,
    MatDialogContent,
    MatDialogActions,
    MatFormField,
    MatLabel,
    MatHint,
    MatError,
    MatSuffix,
    MatInput,
    MatButton,
    MatIconButton,
    MatIcon,
    MatProgressBar,
  ],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <h2 mat-dialog-title>Change password</h2>
    <form [formGroup]="form" (ngSubmit)="save()" novalidate>
      <mat-dialog-content>
        <div class="progress">
          @if (saving()) {
            <mat-progress-bar mode="indeterminate" />
          }
        </div>
        <mat-form-field appearance="outline">
          <mat-label>Current password</mat-label>
          <input
            matInput
            [type]="show() ? 'text' : 'password'"
            formControlName="currentPassword"
            autocomplete="current-password"
            cdkFocusInitial
          />
          <mat-error>{{
            fieldError('currentPassword') ?? 'Enter your current password.'
          }}</mat-error>
        </mat-form-field>
        <mat-form-field appearance="outline">
          <mat-label>New password</mat-label>
          <input
            matInput
            [type]="show() ? 'text' : 'password'"
            formControlName="newPassword"
            autocomplete="new-password"
          />
          <button
            mat-icon-button
            matSuffix
            type="button"
            [attr.aria-label]="show() ? 'Hide passwords' : 'Show passwords'"
            (click)="show.set(!show())"
          >
            <mat-icon>{{ show() ? 'visibility_off' : 'visibility' }}</mat-icon>
          </button>
          <mat-hint>At least 12 characters.</mat-hint>
          <mat-error>{{
            fieldError('newPassword') ?? 'Use at least 12 characters.'
          }}</mat-error>
        </mat-form-field>
        <mat-form-field appearance="outline">
          <mat-label>Confirm new password</mat-label>
          <input
            matInput
            [type]="show() ? 'text' : 'password'"
            formControlName="confirmPassword"
            autocomplete="new-password"
          />
          <mat-error>Type the same new password again.</mat-error>
        </mat-form-field>
        @if (form.hasError('mismatch') && form.controls.confirmPassword.touched) {
          <p class="error">The new passwords don't match.</p>
        }
        @if (message(); as m) {
          <p class="error" role="alert">{{ m }}</p>
        }
      </mat-dialog-content>
      <mat-dialog-actions align="end">
        <button mat-button type="button" (click)="ref.close(false)">Cancel</button>
        <button mat-flat-button type="submit" [disabled]="saving()">
          Change password
        </button>
      </mat-dialog-actions>
    </form>
  `,
  styles: `
    mat-dialog-content {
      display: flex;
      flex-direction: column;
      gap: 0.5rem;
      min-width: min(26rem, 80vw);
    }
    .progress {
      height: 4px;
    }
    .error {
      margin: 0;
      color: var(--mat-sys-error);
      font: var(--mat-sys-body-small);
    }
  `,
})
export class ChangePasswordDialog {
  protected readonly ref = inject(MatDialogRef<ChangePasswordDialog, boolean>);
  private readonly api = inject(ApiClient);

  protected readonly saving = signal(false);
  protected readonly show = signal(false);
  /** A message from the server that isn't about one field. */
  protected readonly message = signal<string | null>(null);
  private readonly serverErrors = signal<Record<string, string>>({});

  protected readonly form = inject(NonNullableFormBuilder).group(
    {
      currentPassword: ['', Validators.required],
      newPassword: ['', [Validators.required, Validators.minLength(12)]],
      confirmPassword: ['', Validators.required],
    },
    { validators: sameNewPassword },
  );

  protected fieldError(field: string): string | null {
    return this.serverErrors()[field] ?? null;
  }

  protected save(): void {
    this.form.markAllAsTouched();
    if (this.form.invalid || this.saving()) return;
    const { currentPassword, newPassword } = this.form.getRawValue();
    this.saving.set(true);
    this.message.set(null);
    this.serverErrors.set({});
    this.api
      .call(
        changeMyPassword,
        { body: { currentPassword, newPassword } },
        withoutErrorToast(),
      )
      .pipe(finalize(() => this.saving.set(false)))
      .subscribe({
        next: () => this.ref.close(true),
        error: (error: unknown) => this.showError(error),
      });
  }

  private showError(error: unknown): void {
    const problem = (
      error instanceof HttpErrorResponse ? error.error : null
    ) as ProblemDetails | null;
    const fields: Record<string, string> = {};
    for (const [field, messages] of Object.entries(problem?.errors ?? {})) {
      if (field in this.form.controls && messages?.length) {
        fields[field] = messages.join(' ');
        this.form.get(field)?.setErrors({ server: true });
      }
    }
    this.serverErrors.set(fields);
    if (!Object.keys(fields).length) {
      this.message.set(
        problem?.detail ?? 'The password could not be changed. Try again.',
      );
    }
  }
}
