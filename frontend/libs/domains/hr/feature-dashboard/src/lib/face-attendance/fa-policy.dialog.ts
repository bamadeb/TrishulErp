import {
  ChangeDetectionStrategy,
  Component,
  inject,
  signal,
} from '@angular/core';
import { FormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { MatButton } from '@angular/material/button';
import {
  MAT_DIALOG_DATA,
  MatDialogModule,
  MatDialogRef,
} from '@angular/material/dialog';
import { MatFormField, MatHint, MatLabel } from '@angular/material/form-field';
import { MatInput } from '@angular/material/input';
import { MatOption, MatSelect } from '@angular/material/select';
import { MatSlideToggle } from '@angular/material/slide-toggle';
import {
  AttendancePolicy,
  AttendancePolicyCreate,
  FaceAttendanceApi,
  faceAttendanceError,
  num,
} from '@trishul/hr-data-access';

export interface FaPolicyDialogData {
  row?: AttendancePolicy;
}

/** How strict face attendance is for a group of employees. Thresholds blank = the face model's defaults. */
@Component({
  selector: 'trishul-fa-policy-dialog',
  imports: [
    ReactiveFormsModule,
    MatButton,
    MatDialogModule,
    MatFormField,
    MatHint,
    MatInput,
    MatLabel,
    MatOption,
    MatSelect,
    MatSlideToggle,
  ],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <h2 mat-dialog-title>
      {{ data.row ? 'Edit policy ' + data.row.code : 'Add policy' }}
    </h2>
    <mat-dialog-content [formGroup]="form">
      @if (!data.row) {
        <mat-form-field appearance="outline">
          <mat-label>Code</mat-label>
          <input matInput formControlName="code" placeholder="e.g. SITE" />
          <mat-hint>Capital letters, digits and _ only.</mat-hint>
        </mat-form-field>
      }
      <mat-form-field appearance="outline">
        <mat-label>Name</mat-label>
        <input matInput formControlName="name" />
      </mat-form-field>
      <mat-form-field appearance="outline">
        <mat-label>Where employees punch</mat-label>
        <mat-select formControlName="mode">
          <mat-option value="Office"
            >Office — must be inside a work location</mat-option
          >
          <mat-option value="Field"
            >Field — anywhere, location recorded</mat-option
          >
          <mat-option value="Hybrid"
            >Hybrid — anywhere, nearest office recorded</mat-option
          >
        </mat-select>
      </mat-form-field>
      <mat-form-field appearance="outline">
        <mat-label>Liveness check</mat-label>
        <mat-select formControlName="challenge">
          <mat-option value="Blink">Blink</mat-option>
          <mat-option value="Blink and turn"
            >Blink, then turn the head (left or right, random)</mat-option
          >
          <mat-option value="None">None (not recommended)</mat-option>
        </mat-select>
      </mat-form-field>
      <mat-slide-toggle formControlName="challengeOnCheckOut"
        >Same liveness check on check-out</mat-slide-toggle
      >
      <div class="row">
        <mat-form-field appearance="outline">
          <mat-label>Match line</mat-label>
          <input
            matInput
            type="number"
            step="0.01"
            min="0"
            max="1"
            formControlName="matchThreshold"
          />
          <mat-hint>Blank = model default (0.36)</mat-hint>
        </mat-form-field>
        <mat-form-field appearance="outline">
          <mat-label>Review line</mat-label>
          <input
            matInput
            type="number"
            step="0.01"
            min="0"
            max="1"
            formControlName="reviewThreshold"
          />
          <mat-hint>Below: rejected; between: to HR (0.30)</mat-hint>
        </mat-form-field>
      </div>
      <mat-form-field appearance="outline">
        <mat-label>Weakest GPS accepted (metres)</mat-label>
        <input
          matInput
          type="number"
          min="5"
          max="2000"
          formControlName="maxGpsAccuracyM"
        />
        <mat-hint>Weaker GPS sends the punch to HR for review.</mat-hint>
      </mat-form-field>
      <mat-slide-toggle formControlName="allowOffline"
        >Allow punches without network (sent later)</mat-slide-toggle
      >
      @if (form.controls.allowOffline.value) {
        <mat-slide-toggle formControlName="offlineAutoAccept"
          >Accept offline punches that pass every check</mat-slide-toggle
        >
        <mat-form-field appearance="outline">
          <mat-label>Offline punch must arrive within (hours)</mat-label>
          <input
            matInput
            type="number"
            min="1"
            max="720"
            formControlName="maxOfflineHours"
          />
        </mat-form-field>
      }
      @if (data.row) {
        <mat-slide-toggle formControlName="isActive">Active</mat-slide-toggle>
      }
      @if (error()) {
        <p class="error">{{ error() }}</p>
      }
    </mat-dialog-content>
    <mat-dialog-actions align="end">
      <button mat-button type="button" mat-dialog-close>Cancel</button>
      <button
        mat-flat-button
        type="button"
        [disabled]="form.invalid || saving()"
        (click)="save()"
      >
        Save
      </button>
    </mat-dialog-actions>
  `,
  styles: `
    mat-dialog-content {
      display: grid;
      gap: 0.6rem;
      min-width: min(30rem, 90vw);
    }
    .row {
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 0.6rem;
    }
    .error {
      margin: 0;
      color: var(--mat-sys-error);
      font-size: 0.82rem;
    }
  `,
})
export class FaPolicyDialog {
  private readonly api = inject(FaceAttendanceApi);
  private readonly ref = inject(MatDialogRef<FaPolicyDialog, boolean>);
  protected readonly data = inject<FaPolicyDialogData>(MAT_DIALOG_DATA);
  protected readonly saving = signal(false);
  protected readonly error = signal<string | null>(null);

  private readonly r = this.data.row;
  protected readonly form = inject(FormBuilder).nonNullable.group({
    code: [
      this.r?.code ?? '',
      [
        Validators.required,
        Validators.maxLength(20),
        Validators.pattern(/^[A-Z0-9_]+$/),
      ],
    ],
    name: [this.r?.name ?? '', [Validators.required, Validators.maxLength(80)]],
    mode: [this.r?.mode ?? 'Office'],
    challenge: [this.r?.challenge ?? 'Blink'],
    challengeOnCheckOut: [this.r?.challengeOnCheckOut ?? false],
    matchThreshold: [
      num(this.r?.matchThreshold),
      [Validators.min(0), Validators.max(1)],
    ],
    reviewThreshold: [
      num(this.r?.reviewThreshold),
      [Validators.min(0), Validators.max(1)],
    ],
    maxGpsAccuracyM: [
      this.r?.maxGpsAccuracyM ?? 100,
      [Validators.required, Validators.min(5), Validators.max(2000)],
    ],
    allowOffline: [this.r?.allowOffline ?? true],
    offlineAutoAccept: [this.r?.offlineAutoAccept ?? true],
    maxOfflineHours: [
      this.r?.maxOfflineHours ?? 72,
      [Validators.required, Validators.min(1), Validators.max(720)],
    ],
    isActive: [this.r?.isActive ?? true],
  });

  protected save(): void {
    const v = this.form.getRawValue();
    const blank = (n: number | null): number | null =>
      n === null || (n as unknown) === '' ? null : Number(n);
    // The fields both a new and an edited policy send (the code is fixed once created).
    const fields = {
      name: v.name.trim(),
      mode: v.mode,
      challenge: v.challenge,
      challengeOnCheckOut: v.challengeOnCheckOut,
      antispoofRequired: this.r?.antispoofRequired ?? true,
      matchThreshold: blank(v.matchThreshold),
      reviewThreshold: blank(v.reviewThreshold),
      maxScoreGap: this.r?.maxScoreGap ?? 0.1,
      maxGpsAccuracyM: Number(v.maxGpsAccuracyM),
      allowOffline: v.allowOffline,
      offlineAutoAccept: v.offlineAutoAccept,
      maxOfflineHours: Number(v.maxOfflineHours),
    };
    this.saving.set(true);
    this.error.set(null);
    const create: AttendancePolicyCreate = {
      ...fields,
      code: v.code,
      name: v.name.trim(),
      mode: v.mode,
    };
    const request = this.r
      ? this.api.updatePolicy(this.r, { ...fields, isActive: v.isActive })
      : this.api.createPolicy(create);
    request.subscribe({
      next: () => this.ref.close(true),
      error: (err) => {
        this.saving.set(false);
        this.error.set(
          faceAttendanceError(err, 'The policy could not be saved.'),
        );
      },
    });
  }
}
