import { ChangeDetectionStrategy, Component, inject, signal } from '@angular/core';
import { FormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { MatButton } from '@angular/material/button';
import { MAT_DIALOG_DATA, MatDialogModule, MatDialogRef } from '@angular/material/dialog';
import { MatFormField, MatLabel } from '@angular/material/form-field';
import { MatInput } from '@angular/material/input';
import { MatSlideToggle } from '@angular/material/slide-toggle';
import { BiometricApi, BiometricDevice } from '@trishul/hr-data-access';

export interface BiometricDeviceDialogData {
  row?: BiometricDevice;
}

@Component({
  selector: 'trishul-biometric-device-dialog',
  imports: [
    ReactiveFormsModule,
    MatButton,
    MatDialogModule,
    MatFormField,
    MatInput,
    MatLabel,
    MatSlideToggle,
  ],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <h2 mat-dialog-title>{{ data.row ? 'Edit device' : 'Add device' }}</h2>
    <mat-dialog-content [formGroup]="form">
      <mat-form-field appearance="outline">
        <mat-label>Device name</mat-label>
        <input matInput formControlName="name" />
      </mat-form-field>
      <mat-form-field appearance="outline">
        <mat-label>Code</mat-label>
        <input matInput formControlName="code" [readonly]="!!data.row" />
      </mat-form-field>
      <mat-form-field appearance="outline">
        <mat-label>Serial number</mat-label>
        <input matInput formControlName="serialNumber" />
      </mat-form-field>
      <mat-form-field appearance="outline">
        <mat-label>Location</mat-label>
        <input matInput formControlName="locationName" />
      </mat-form-field>
      <mat-form-field appearance="outline">
        <mat-label>Vendor</mat-label>
        <input matInput formControlName="vendor" />
      </mat-form-field>
      <mat-form-field appearance="outline">
        <mat-label>Base URL (optional)</mat-label>
        <input matInput formControlName="baseUrl" />
      </mat-form-field>
      <mat-slide-toggle formControlName="isSyncEnabled">Sync enabled</mat-slide-toggle>
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
        color="primary"
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
      gap: 0.45rem;
      min-width: min(28rem, 90vw);
    }
    .error {
      margin: 0.25rem 0 0;
      color: #b3261e;
      font-size: 0.8rem;
    }
  `,
})
export class BiometricDeviceDialog {
  private readonly api = inject(BiometricApi);
  private readonly dialogRef = inject(MatDialogRef<BiometricDeviceDialog, boolean>);
  private readonly fb = inject(FormBuilder);
  protected readonly data = inject<BiometricDeviceDialogData>(MAT_DIALOG_DATA);
  protected readonly saving = signal(false);
  protected readonly error = signal<string | null>(null);

  protected readonly form = this.fb.nonNullable.group({
    name: [this.data.row?.name ?? '', [Validators.required, Validators.maxLength(120)]],
    code: [this.data.row?.code ?? '', [Validators.required, Validators.maxLength(40)]],
    serialNumber: [this.data.row?.serialNumber ?? ''],
    locationName: [this.data.row?.locationName ?? ''],
    vendor: [this.data.row?.vendor ?? 'ESSL', [Validators.required, Validators.maxLength(40)]],
    baseUrl: [this.data.row?.baseUrl ?? ''],
    isSyncEnabled: [this.data.row?.isSyncEnabled ?? false],
    isActive: [this.data.row?.isActive ?? true],
  });

  protected save(): void {
    if (this.form.invalid || this.saving()) return;
    this.saving.set(true);
    this.error.set(null);
    const value = this.form.getRawValue();
    const request = this.data.row
      ? this.api.updateDevice(this.data.row.id, {
          name: value.name,
          serialNumber: value.serialNumber || null,
          locationName: value.locationName || null,
          vendor: value.vendor,
          baseUrl: value.baseUrl || null,
          isSyncEnabled: value.isSyncEnabled,
          isActive: value.isActive,
        })
      : this.api.createDevice({
          code: value.code,
          name: value.name,
          serialNumber: value.serialNumber || null,
          locationName: value.locationName || null,
          vendor: value.vendor,
          baseUrl: value.baseUrl || null,
          isSyncEnabled: value.isSyncEnabled,
        });

    request.subscribe({
      next: () => this.dialogRef.close(true),
      error: (err) => {
        this.saving.set(false);
        this.error.set(err?.error?.detail || 'Device could not be saved.');
      },
    });
  }
}
