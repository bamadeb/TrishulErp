import { ChangeDetectionStrategy, Component, inject, signal } from '@angular/core';
import {
  FormBuilder,
  ReactiveFormsModule,
  Validators,
} from '@angular/forms';
import { MatButton } from '@angular/material/button';
import {
  MAT_DIALOG_DATA,
  MatDialog,
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
import { MatInput } from '@angular/material/input';
import { EMPTY, Observable, catchError, finalize, tap } from 'rxjs';
import {
  CallTripHistoryItem,
  TripApi,
  TripOut,
} from '@trishul/service-data-access';

interface AdjustDialogData {
  trip: CallTripHistoryItem;
}

/**
 * Team Lead overrides a trip's distance. The GPS value is shown but never changed; the entered
 * value becomes the effective distance and the reason is kept for audit. Closes with the updated
 * TripOut on success, or undefined if cancelled.
 */
@Component({
  selector: 'trishul-adjust-distance-dialog',
  imports: [
    ReactiveFormsModule,
    MatDialogTitle,
    MatDialogContent,
    MatDialogActions,
    MatFormField,
    MatLabel,
    MatInput,
    MatHint,
    MatError,
    MatSuffix,
    MatButton,
  ],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <h2 mat-dialog-title>Adjust trip distance</h2>
    <mat-dialog-content>
      <p class="sub">
        {{ trip.tripType }} · visit {{ trip.visitNo }} · trip #{{ trip.id }}
      </p>

      <div class="gps">
        <span>GPS-calculated (kept on record)</span>
        <b>{{ fmt(trip.gpsDistanceKm) }} km</b>
      </div>

      <form [formGroup]="form" (ngSubmit)="save()">
        <mat-form-field appearance="outline" class="km">
          <mat-label>Revised distance</mat-label>
          <input
            matInput
            type="number"
            min="0"
            max="999999.99"
            step="0.01"
            inputmode="decimal"
            formControlName="newDistanceKm"
          />
          <span matSuffix>km</span>
          <mat-hint
            >Currently effective: {{ fmt(trip.effectiveDistanceKm) }} km</mat-hint
          >
          @if (form.controls.newDistanceKm.hasError('required')) {
            <mat-error>Enter the revised distance.</mat-error>
          } @else if (form.controls.newDistanceKm.hasError('min')) {
            <mat-error>Distance cannot be negative.</mat-error>
          } @else if (form.controls.newDistanceKm.hasError('max')) {
            <mat-error>That distance is too large.</mat-error>
          }
        </mat-form-field>

        <mat-form-field appearance="outline">
          <mat-label>Reason for adjustment</mat-label>
          <textarea
            matInput
            rows="3"
            formControlName="reason"
            placeholder="e.g. GPS lost signal on the ghat section; distance taken from the vehicle odometer."
          ></textarea>
          <mat-hint
            >Recorded against your user ID with the date and time, for
            audit.</mat-hint
          >
          @if (form.controls.reason.hasError('required') || form.controls.reason.hasError('minlength')) {
            <mat-error>Give a short reason — it is kept for audit.</mat-error>
          } @else if (form.controls.reason.hasError('maxlength')) {
            <mat-error>Keep the reason under 500 characters.</mat-error>
          }
        </mat-form-field>
      </form>
    </mat-dialog-content>
    <mat-dialog-actions align="end">
      <button mat-button type="button" (click)="dialogRef.close()">Cancel</button>
      <button
        mat-flat-button
        [disabled]="saving()"
        (click)="save()"
      >
        {{ saving() ? 'Saving…' : 'Save adjustment' }}
      </button>
    </mat-dialog-actions>
  `,
  styles: `
    .sub {
      margin: 0 0 1rem;
      color: var(--mat-sys-on-surface-variant);
      font: var(--mat-sys-body-small);
    }
    .gps {
      display: flex;
      justify-content: space-between;
      align-items: center;
      gap: 0.75rem;
      padding: 0.5rem 0.75rem;
      margin-bottom: 1rem;
      border-radius: var(--mat-sys-corner-small);
      background: var(--mat-sys-surface-container-high);
      font: var(--mat-sys-body-small);
      color: var(--mat-sys-on-surface-variant);
    }
    .gps b {
      font-variant-numeric: tabular-nums;
      color: var(--mat-sys-on-surface);
    }
    form {
      display: flex;
      flex-direction: column;
    }
    mat-form-field {
      width: 100%;
    }
    .km {
      max-width: 14rem;
    }
  `,
})
export class AdjustDistanceDialog {
  protected readonly dialogRef =
    inject<MatDialogRef<AdjustDistanceDialog, TripOut>>(MatDialogRef);
  private readonly data = inject<AdjustDialogData>(MAT_DIALOG_DATA);
  private readonly api = inject(TripApi);
  private readonly fb = inject(FormBuilder);

  protected readonly trip = this.data.trip;
  protected readonly saving = signal(false);

  protected readonly form = this.fb.nonNullable.group({
    newDistanceKm: [
      this.trip.effectiveDistanceKm ?? this.trip.gpsDistanceKm ?? 0,
      [Validators.required, Validators.min(0), Validators.max(999999.99)],
    ],
    reason: [
      '',
      [
        Validators.required,
        Validators.minLength(3),
        Validators.maxLength(500),
      ],
    ],
  });

  protected fmt(value: number | null | undefined): string {
    return value === null || value === undefined ? '—' : value.toFixed(2);
  }

  protected save(): void {
    if (this.form.invalid || this.saving()) {
      this.form.markAllAsTouched();
      return;
    }
    const { newDistanceKm, reason } = this.form.getRawValue();
    this.saving.set(true);
    this.api
      .adjustDistance(this.trip.id, { newDistanceKm, reason: reason.trim() }, this.trip.rowVersion)
      .pipe(
        tap((updated) => this.dialogRef.close(updated)),
        catchError(() => EMPTY), // the global interceptor shows the error toast
        finalize(() => this.saving.set(false)),
      )
      .subscribe();
  }
}

/** Opens the adjust dialog; emits the updated trip on success, undefined if cancelled. */
export function openAdjustDistanceDialog(
  dialog: MatDialog,
  trip: CallTripHistoryItem,
): Observable<TripOut | undefined> {
  return dialog
    .open<AdjustDistanceDialog, AdjustDialogData, TripOut>(
      AdjustDistanceDialog,
      { data: { trip }, width: '30rem', autoFocus: 'dialog' },
    )
    .afterClosed();
}
