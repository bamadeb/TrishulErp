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
import { MatIcon } from '@angular/material/icon';
import { MatInput } from '@angular/material/input';
import { MatOption, MatSelect } from '@angular/material/select';
import { MatSlideToggle } from '@angular/material/slide-toggle';
import {
  FaceAttendanceApi,
  WorkLocation,
  faceAttendanceError,
} from '@trishul/hr-data-access';
import { mapLink } from './face-attendance.shared';

export interface FaLocationDialogData {
  row?: WorkLocation;
  branches: { id: number; name: string }[];
}

/**
 * An office geofence. The easiest way to get the point: open the office in Google Maps, long-press or
 * right-click the entrance and copy "lat, long" into the Location field.
 */
@Component({
  selector: 'trishul-fa-location-dialog',
  imports: [
    ReactiveFormsModule,
    MatButton,
    MatDialogModule,
    MatFormField,
    MatHint,
    MatIcon,
    MatInput,
    MatLabel,
    MatOption,
    MatSelect,
    MatSlideToggle,
  ],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <h2 mat-dialog-title>
      {{ data.row ? 'Edit work location' : 'Add work location' }}
    </h2>
    <mat-dialog-content [formGroup]="form">
      <mat-form-field appearance="outline">
        <mat-label>Name</mat-label>
        <input
          matInput
          formControlName="name"
          placeholder="e.g. Bhubaneswar office"
        />
      </mat-form-field>
      <mat-form-field appearance="outline">
        <mat-label>Branch (optional)</mat-label>
        <mat-select formControlName="branchId">
          <mat-option [value]="0">—</mat-option>
          @for (b of data.branches; track b.id) {
            <mat-option [value]="b.id">{{ b.name }}</mat-option>
          }
        </mat-select>
      </mat-form-field>
      <mat-form-field appearance="outline">
        <mat-label>Location (latitude, longitude)</mat-label>
        <input
          matInput
          formControlName="point"
          placeholder="20.296059, 85.824539"
          (blur)="tidyPoint()"
        />
        <mat-hint
          >In Google Maps, right-click the office entrance and copy the numbers
          shown.</mat-hint
        >
      </mat-form-field>
      @if (pointLink(); as link) {
        <a class="map" [href]="link" target="_blank" rel="noopener"
          ><mat-icon>map</mat-icon> Check on Google Maps</a
        >
      }
      <mat-form-field appearance="outline">
        <mat-label>Allowed radius (metres)</mat-label>
        <input
          matInput
          type="number"
          min="10"
          max="5000"
          formControlName="radiusM"
        />
        <mat-hint
          >Punches within this distance count as inside the office. 150 m suits
          most offices.</mat-hint
        >
      </mat-form-field>
      <mat-form-field appearance="outline">
        <mat-label>Address (optional)</mat-label>
        <input matInput formControlName="address" />
      </mat-form-field>
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
      min-width: min(28rem, 90vw);
    }
    .map {
      display: inline-flex;
      gap: 0.3rem;
      align-items: center;
      color: var(--mat-sys-primary);
      text-decoration: none;
      font: var(--mat-sys-body-small);
    }
    .error {
      margin: 0;
      color: var(--mat-sys-error);
      font-size: 0.82rem;
    }
  `,
})
export class FaLocationDialog {
  private readonly api = inject(FaceAttendanceApi);
  private readonly ref = inject(MatDialogRef<FaLocationDialog, boolean>);
  protected readonly data = inject<FaLocationDialogData>(MAT_DIALOG_DATA);
  protected readonly saving = signal(false);
  protected readonly error = signal<string | null>(null);

  protected readonly form = inject(FormBuilder).nonNullable.group({
    name: [
      this.data.row?.name ?? '',
      [Validators.required, Validators.maxLength(120)],
    ],
    branchId: [this.data.row?.branchId ?? 0],
    point: [
      this.data.row
        ? `${this.data.row.latitude}, ${this.data.row.longitude}`
        : '',
      [Validators.required, Validators.pattern(POINT)],
    ],
    radiusM: [
      this.data.row?.radiusM ?? 150,
      [Validators.required, Validators.min(10), Validators.max(5000)],
    ],
    address: [this.data.row?.address ?? '', Validators.maxLength(300)],
    isActive: [this.data.row?.isActive ?? true],
  });

  protected pointLink(): string | null {
    const p = parsePoint(this.form.controls.point.value);
    return p ? mapLink(p.latitude, p.longitude) : null;
  }

  protected tidyPoint(): void {
    const p = parsePoint(this.form.controls.point.value);
    if (p) this.form.controls.point.setValue(`${p.latitude}, ${p.longitude}`);
  }

  protected save(): void {
    const v = this.form.getRawValue();
    const p = parsePoint(v.point);
    if (!p) {
      this.error.set(
        'Enter the location as latitude, longitude (e.g. 20.296059, 85.824539).',
      );
      return;
    }
    this.saving.set(true);
    this.error.set(null);
    const body = {
      name: v.name.trim(),
      branchId: v.branchId || null,
      latitude: p.latitude,
      longitude: p.longitude,
      radiusM: Number(v.radiusM),
      address: v.address.trim() || null,
    };
    const request = this.data.row
      ? this.api.updateLocation(this.data.row, {
          ...body,
          isActive: v.isActive,
        })
      : this.api.createLocation(body);
    request.subscribe({
      next: () => this.ref.close(true),
      error: (err) => {
        this.saving.set(false);
        this.error.set(
          faceAttendanceError(err, 'The work location could not be saved.'),
        );
      },
    });
  }
}

const POINT = /^\s*-?\d{1,2}(\.\d+)?\s*,\s*-?\d{1,3}(\.\d+)?\s*$/;

function parsePoint(
  text: string,
): { latitude: number; longitude: number } | null {
  if (!POINT.test(text)) return null;
  const [lat, lng] = text
    .split(',')
    .map((s) => Number(Number(s.trim()).toFixed(6)));
  if (Math.abs(lat) > 90 || Math.abs(lng) > 180) return null;
  return { latitude: lat, longitude: lng };
}
