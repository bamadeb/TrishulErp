import { ChangeDetectionStrategy, Component, inject, OnInit, signal } from '@angular/core';
import { FormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { MatButton } from '@angular/material/button';
import { MAT_DIALOG_DATA, MatDialogModule, MatDialogRef } from '@angular/material/dialog';
import { MatFormField, MatLabel } from '@angular/material/form-field';
import { MatInput } from '@angular/material/input';
import { MatOption, MatSelect } from '@angular/material/select';
import {
  BiometricApi,
  BiometricDevice,
  BiometricMapping,
  EmployeesApi,
} from '@trishul/hr-data-access';

export interface BiometricMappingDialogData {
  row?: BiometricMapping;
  devices: BiometricDevice[];
}

interface EmployeeOption {
  id: number;
  label: string;
}

@Component({
  selector: 'trishul-biometric-mapping-dialog',
  imports: [
    ReactiveFormsModule,
    MatButton,
    MatDialogModule,
    MatFormField,
    MatInput,
    MatLabel,
    MatOption,
    MatSelect,
  ],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <h2 mat-dialog-title>{{ data.row ? 'Edit mapping' : 'Add mapping' }}</h2>
    <mat-dialog-content [formGroup]="form">
      <mat-form-field appearance="outline">
        <mat-label>Employee</mat-label>
        <mat-select formControlName="employeeId">
          @for (emp of employees(); track emp.id) {
            <mat-option [value]="emp.id">{{ emp.label }}</mat-option>
          }
        </mat-select>
      </mat-form-field>
      <mat-form-field appearance="outline">
        <mat-label>Biometric user ID</mat-label>
        <input matInput formControlName="biometricUserId" />
      </mat-form-field>
      <mat-form-field appearance="outline">
        <mat-label>Device</mat-label>
        <mat-select formControlName="deviceId">
          <mat-option [value]="null">All devices</mat-option>
          @for (device of data.devices; track device.id) {
            <mat-option [value]="device.id">{{ device.name }} ({{ device.code }})</mat-option>
          }
        </mat-select>
      </mat-form-field>
      <mat-form-field appearance="outline">
        <mat-label>Effective from</mat-label>
        <input matInput type="date" formControlName="effectiveFrom" />
      </mat-form-field>
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
export class BiometricMappingDialog implements OnInit {
  private readonly api = inject(BiometricApi);
  private readonly employeesApi = inject(EmployeesApi);
  private readonly dialogRef = inject(MatDialogRef<BiometricMappingDialog, boolean>);
  private readonly fb = inject(FormBuilder);
  protected readonly data = inject<BiometricMappingDialogData>(MAT_DIALOG_DATA);
  protected readonly employees = signal<EmployeeOption[]>([]);
  protected readonly saving = signal(false);
  protected readonly error = signal<string | null>(null);

  protected readonly form = this.fb.nonNullable.group({
    employeeId: [this.data.row?.employeeId ?? 0, [Validators.required, Validators.min(1)]],
    biometricUserId: [
      this.data.row?.biometricUserId ?? '',
      [Validators.required, Validators.maxLength(80)],
    ],
    deviceId: this.fb.control<number | null>(this.data.row?.deviceId ?? null),
    effectiveFrom: [
      this.data.row?.effectiveFrom ?? new Date().toISOString().slice(0, 10),
      Validators.required,
    ],
  });

  ngOnInit(): void {
    this.employeesApi.list({ page: 1, pageSize: 200, status: 'active' }).subscribe({
      next: (page) => {
        this.employees.set(
          page.items.map((item) => ({
            id: item.id,
            label: `${item.employeeCode} — ${item.fullName}`,
          })),
        );
      },
      error: () => this.error.set('Employees could not be loaded.'),
    });
  }

  protected save(): void {
    if (this.form.invalid || this.saving()) return;
    this.saving.set(true);
    this.error.set(null);
    const value = this.form.getRawValue();
    const request = this.data.row
      ? this.api.updateMapping(this.data.row.id, {
          biometricUserId: value.biometricUserId,
          deviceId: value.deviceId,
          effectiveFrom: value.effectiveFrom,
        })
      : this.api.createMapping({
          employeeId: value.employeeId,
          biometricUserId: value.biometricUserId,
          deviceId: value.deviceId,
          effectiveFrom: value.effectiveFrom,
        });

    request.subscribe({
      next: () => this.dialogRef.close(true),
      error: (err) => {
        this.saving.set(false);
        this.error.set(err?.error?.detail || 'Mapping could not be saved.');
      },
    });
  }
}
