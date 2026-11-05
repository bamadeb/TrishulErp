import { DatePipe, DecimalPipe } from '@angular/common';
import {
  ChangeDetectionStrategy,
  Component,
  OnInit,
  inject,
  signal,
} from '@angular/core';
import { FormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { MatButtonModule } from '@angular/material/button';
import {
  MAT_DIALOG_DATA,
  MatDialogModule,
  MatDialogRef,
} from '@angular/material/dialog';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatIconModule } from '@angular/material/icon';
import { MatInputModule } from '@angular/material/input';
import { MatProgressBarModule } from '@angular/material/progress-bar';
import { MatSelectModule } from '@angular/material/select';
import { DocumentPanel } from '@trishul/core-documents';
import {
  ManualTravelOut,
  TripApi,
  VehicleTypeItem,
} from '@trishul/service-data-access';

export interface ManualTravelData {
  callId: number;
  callNo: string;
  /** Present when viewing or correcting an existing entry. */
  entry?: ManualTravelOut;
}

/** The documents module's key for a manual travel entry (backend: trk.manual_travel). */
export const MANUAL_TRAVEL_ENTITY = 'trk.manual_travel';

const MAX_AGE_DAYS = 90;

/** crypto.randomUUID() only exists on secure origins (https, localhost); the dev server is plain http. */
function newUuid(): string {
  const bytes = crypto.getRandomValues(new Uint8Array(16));
  bytes[6] = (bytes[6] & 0x0f) | 0x40;
  bytes[8] = (bytes[8] & 0x3f) | 0x80;
  const hex = Array.from(bytes, (b) => b.toString(16).padStart(2, '0')).join('');
  return `${hex.slice(0, 8)}-${hex.slice(8, 12)}-${hex.slice(12, 16)}-${hex.slice(16, 20)}-${hex.slice(20)}`;
}

function isoDay(offsetDays: number): string {
  const date = new Date();
  date.setDate(date.getDate() + offsetDays);
  return new Date(date.getTime() - date.getTimezoneOffset() * 60_000)
    .toISOString()
    .slice(0, 10);
}

/**
 * Manual travel for vehicles that have no GPS trip (Bus, Train, Other): the engineer types the
 * kilometres and attaches tickets. There is no Start / Stop trip here by design.
 * Tickets use the common document panel; they can be added as soon as the entry is saved.
 */
@Component({
  selector: 'trishul-manual-travel-dialog',
  imports: [
    DatePipe,
    DecimalPipe,
    ReactiveFormsModule,
    MatDialogModule,
    MatButtonModule,
    MatFormFieldModule,
    MatIconModule,
    MatInputModule,
    MatProgressBarModule,
    MatSelectModule,
    DocumentPanel,
  ],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <h2 mat-dialog-title>
      {{ saved() ? 'Manual travel' : 'Add manual travel' }}
    </h2>
    <mat-dialog-content>
      <p class="sub">
        Call {{ data.callNo }} — for Bus, Train or Other travel, which is not
        tracked by GPS.
      </p>

      @if (loading()) {
        <mat-progress-bar mode="indeterminate" />
      }

      @if (!canEdit()) {
        @if (saved(); as e) {
          <dl>
            <dt>Engineer</dt>
            <dd>{{ e.employeeName ?? '—' }}</dd>
            <dt>Travel type</dt>
            <dd>{{ e.vehicleType }}</dd>
            <dt>Date</dt>
            <dd>{{ e.travelDate | date: 'dd MMM yyyy' }}</dd>
            <dt>Distance</dt>
            <dd>{{ e.distanceKm | number: '1.1-2' }} km</dd>
            <dt>Notes</dt>
            <dd>{{ e.notes || '—' }}</dd>
          </dl>
        }
      } @else {
        <form [formGroup]="form" (ngSubmit)="save()" id="manual-travel-form">
          <mat-form-field appearance="outline">
            <mat-label>Vehicle / travel type</mat-label>
            <mat-select formControlName="vehicleType">
              @for (v of vehicleTypes(); track v.code) {
                <mat-option [value]="v.code">{{ v.name }}</mat-option>
              }
            </mat-select>
            @if (form.controls.vehicleType.hasError('required')) {
              <mat-error>Choose the travel type</mat-error>
            }
          </mat-form-field>

          <div class="row">
            <mat-form-field appearance="outline">
              <mat-label>Travel date</mat-label>
              <input
                matInput
                type="date"
                formControlName="travelDate"
                [min]="minDate"
                [max]="maxDate"
              />
              @if (form.controls.travelDate.invalid) {
                <mat-error>Enter a date within the last 90 days</mat-error>
              }
            </mat-form-field>

            <mat-form-field appearance="outline">
              <mat-label>Total distance travelled</mat-label>
              <input
                matInput
                type="number"
                inputmode="decimal"
                step="0.1"
                formControlName="distanceKm"
              />
              <span matTextSuffix>km</span>
              @if (form.controls.distanceKm.invalid) {
                <mat-error>Enter 0.01 to 5000 km</mat-error>
              }
            </mat-form-field>
          </div>

          <mat-form-field appearance="outline">
            <mat-label>Travel notes / description</mat-label>
            <textarea
              matInput
              rows="3"
              maxlength="500"
              formControlName="notes"
              placeholder="e.g. Bhubaneswar to Bhadrak by state bus"
            ></textarea>
          </mat-form-field>
        </form>
      }

      @if (saved(); as e) {
        <trishul-document-panel
          title="Tickets / supporting documents"
          [entityType]="entityType"
          [entityId]="e.id"
          [readonly]="!e.canEdit"
        />
      } @else if (canEdit()) {
        <p class="hint">
          <mat-icon inline>attach_file</mat-icon> Save the entry first, then
          attach the ticket or travel documents.
        </p>
      }
    </mat-dialog-content>
    <mat-dialog-actions align="end">
      @if (saved() && !canEdit()) {
        <button mat-flat-button type="button" (click)="done()">Close</button>
      } @else {
        @if (saved()) {
          <button mat-button type="button" (click)="done()">Done</button>
        } @else {
          <button mat-button type="button" mat-dialog-close>Cancel</button>
        }
        <button
          mat-flat-button
          type="submit"
          form="manual-travel-form"
          [disabled]="saving() || loading()"
        >
          {{ saved() ? 'Save changes' : 'Save entry' }}
        </button>
      }
    </mat-dialog-actions>
  `,
  styles: `
    .sub,
    .hint {
      margin: 0 0 1rem;
      color: var(--mat-sys-on-surface-variant);
    }
    .hint {
      display: flex;
      align-items: center;
      gap: 0.25rem;
      margin: 0;
    }
    form {
      display: flex;
      flex-direction: column;
      gap: 0.25rem;
    }
    .row {
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 0.75rem;
    }
    mat-form-field {
      width: 100%;
    }
    dl {
      display: grid;
      grid-template-columns: max-content 1fr;
      gap: 0.4rem 1.25rem;
      margin: 0 0 1rem;
    }
    dt {
      color: var(--mat-sys-on-surface-variant);
    }
    dd {
      margin: 0;
      font-weight: 500;
      overflow-wrap: anywhere;
    }
    trishul-document-panel {
      display: block;
      margin-top: 1rem;
    }
    @media (max-width: 520px) {
      .row {
        grid-template-columns: 1fr;
      }
    }
  `,
})
export class ManualTravelDialog implements OnInit {
  protected readonly data = inject<ManualTravelData>(MAT_DIALOG_DATA);
  private readonly dialogRef =
    inject<MatDialogRef<ManualTravelDialog, boolean>>(MatDialogRef);
  private readonly api = inject(TripApi);
  private readonly fb = inject(FormBuilder);

  protected readonly entityType = MANUAL_TRAVEL_ENTITY;
  protected readonly minDate = isoDay(-MAX_AGE_DAYS);
  protected readonly maxDate = isoDay(0);
  protected readonly vehicleTypes = signal<VehicleTypeItem[]>([]);
  protected readonly loading = signal(true);
  protected readonly saving = signal(false);
  /** The saved entry; set after the first save (or when opening an existing one). */
  protected readonly saved = signal<ManualTravelOut | null>(
    this.data.entry ?? null,
  );
  protected readonly canEdit = signal(this.data.entry?.canEdit ?? true);

  /** Makes a retried save return the same entry instead of a duplicate. */
  private readonly clientUuid = newUuid();

  protected readonly form = this.fb.nonNullable.group({
    vehicleType: [this.data.entry?.vehicleType ?? '', Validators.required],
    travelDate: [
      this.data.entry?.travelDate ?? isoDay(0),
      [Validators.required],
    ],
    distanceKm: [
      this.data.entry ? Number(this.data.entry.distanceKm) : (null as number | null),
      [Validators.required, Validators.min(0.01), Validators.max(5000)],
    ],
    notes: [this.data.entry?.notes ?? '', Validators.maxLength(500)],
  });

  ngOnInit(): void {
    this.api.manualVehicleTypes().subscribe({
      next: (types) => {
        this.vehicleTypes.set(types);
        this.loading.set(false);
      },
      error: () => this.loading.set(false),
    });
  }

  protected save(): void {
    const value = this.form.getRawValue();
    if (this.form.invalid || this.saving() || value.distanceKm === null) {
      this.form.markAllAsTouched();
      return;
    }
    if (value.travelDate < this.minDate || value.travelDate > this.maxDate) {
      this.form.controls.travelDate.setErrors({ range: true });
      return;
    }
    const body = {
      vehicleType: value.vehicleType,
      travelDate: value.travelDate,
      distanceKm: value.distanceKm,
      notes: value.notes.trim() || null,
    };
    const current = this.saved();
    this.saving.set(true);
    const request = current
      ? this.api.updateManualTravel(current, body)
      : this.api.createManualTravel({
          ...body,
          serviceCallId: this.data.callId,
          clientUuid: this.clientUuid,
        });
    request.subscribe({
      next: (entry) => {
        this.saved.set(entry);
        this.saving.set(false);
      },
      // The global interceptor shows the server's message.
      error: () => this.saving.set(false),
    });
  }

  protected done(): void {
    this.dialogRef.close(true);
  }
}

export type { ManualTravelOut };
