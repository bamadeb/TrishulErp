import {
  ChangeDetectionStrategy,
  Component,
  computed,
  inject,
  signal,
} from '@angular/core';
import { toSignal } from '@angular/core/rxjs-interop';
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
import {
  AttendanceEmployee,
  AttendancePolicy,
  FaceAttendanceApi,
  WorkLocation,
  faceAttendanceError,
} from '@trishul/hr-data-access';
import { indiaToday } from './face-attendance.shared';

export interface FaAssignPolicyDialogData {
  employees: AttendanceEmployee[];
  policies: AttendancePolicy[];
  locations: WorkLocation[];
}

/** Sets the attendance policy (and, for office staff, the work locations) for one or more employees. */
@Component({
  selector: 'trishul-fa-assign-policy-dialog',
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
  ],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <h2 mat-dialog-title>Set attendance policy</h2>
    <mat-dialog-content [formGroup]="form">
      <p class="who">
        @if (data.employees.length === 1) {
          {{ data.employees[0].employeeName }} ({{
            data.employees[0].employeeCode
          }})
        } @else {
          {{ data.employees.length }} employees
        }
      </p>
      <mat-form-field appearance="outline">
        <mat-label>Policy</mat-label>
        <mat-select formControlName="policyId">
          @for (policy of activePolicies; track policy.id) {
            <mat-option [value]="policy.id"
              >{{ policy.code }} — {{ policy.name }}</mat-option
            >
          }
        </mat-select>
      </mat-form-field>
      <mat-form-field appearance="outline">
        <mat-label>From date</mat-label>
        <input matInput type="date" formControlName="fromDate" />
        <mat-hint>The previous policy ends the day before.</mat-hint>
      </mat-form-field>
      <mat-form-field appearance="outline">
        <mat-label
          >Work locations {{ needsLocation() ? '' : '(optional)' }}</mat-label
        >
        <mat-select formControlName="workLocationIds" multiple>
          @for (location of activeLocations; track location.id) {
            <mat-option [value]="location.id">
              {{ location.name
              }}{{ location.branchName ? ' · ' + location.branchName : '' }} ({{
                location.radiusM
              }}
              m)
            </mat-option>
          }
        </mat-select>
        <mat-hint>
          {{
            needsLocation()
              ? 'Office staff must punch inside one of these.'
              : 'Field staff may punch anywhere; the nearest location is recorded.'
          }}
        </mat-hint>
      </mat-form-field>
      @if (needsLocation() && !activeLocations.length) {
        <p class="error">Add a work location first (Work locations tab).</p>
      }
      @if (progress()) {
        <p class="muted">{{ progress() }}</p>
      }
      @if (error()) {
        <p class="error">{{ error() }}</p>
      }
    </mat-dialog-content>
    <mat-dialog-actions align="end">
      <button mat-button type="button" mat-dialog-close [disabled]="saving()">
        Cancel
      </button>
      <button
        mat-flat-button
        type="button"
        [disabled]="!canSave() || saving()"
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
    .who {
      margin: 0;
      font: var(--mat-sys-title-small);
    }
    .error {
      margin: 0;
      color: var(--mat-sys-error);
      font-size: 0.82rem;
    }
    .muted {
      margin: 0;
      color: var(--mat-sys-on-surface-variant);
      font-size: 0.82rem;
    }
  `,
})
export class FaAssignPolicyDialog {
  private readonly api = inject(FaceAttendanceApi);
  private readonly ref = inject(MatDialogRef<FaAssignPolicyDialog, boolean>);
  protected readonly data = inject<FaAssignPolicyDialogData>(MAT_DIALOG_DATA);
  protected readonly activePolicies = this.data.policies.filter(
    (p) => p.isActive,
  );
  protected readonly activeLocations = this.data.locations.filter(
    (l) => l.isActive,
  );
  protected readonly saving = signal(false);
  protected readonly error = signal<string | null>(null);
  protected readonly progress = signal<string | null>(null);

  private readonly first = this.data.employees[0];
  protected readonly form = inject(FormBuilder).nonNullable.group({
    policyId: [
      this.data.employees.length === 1 ? (this.first.policyId ?? 0) : 0,
      Validators.min(1),
    ],
    fromDate: [indiaToday(), Validators.required],
    workLocationIds: [
      this.data.employees.length === 1
        ? [...this.first.workLocationIds]
        : ([] as number[]),
    ],
  });

  private readonly value = toSignal(this.form.valueChanges, {
    initialValue: this.form.getRawValue(),
  });
  protected readonly needsLocation = computed(
    () =>
      this.data.policies.find((p) => p.id === this.value().policyId)?.mode ===
      'Office',
  );
  protected readonly canSave = computed(() => {
    const v = this.value();
    return (
      !!v.policyId &&
      !!v.fromDate &&
      (!this.needsLocation() || (v.workLocationIds?.length ?? 0) > 0)
    );
  });

  protected save(): void {
    const v = this.form.getRawValue();
    this.saving.set(true);
    this.error.set(null);
    const queue = [...this.data.employees];
    const failures: string[] = [];
    const next = (): void => {
      const employee = queue.shift();
      if (!employee) {
        this.saving.set(false);
        if (failures.length) {
          this.error.set(failures.join(' '));
          this.progress.set(null);
        } else {
          this.ref.close(true);
        }
        return;
      }
      this.progress.set(
        `Saving ${this.data.employees.length - queue.length} of ${this.data.employees.length}…`,
      );
      this.api
        .assignPolicy(employee.employeeId, {
          policyId: v.policyId,
          fromDate: v.fromDate,
          workLocationIds: v.workLocationIds,
        })
        .subscribe({
          next,
          error: (err) => {
            failures.push(
              `${employee.employeeCode}: ${faceAttendanceError(err, 'could not be saved.')}`,
            );
            next();
          },
        });
    };
    next();
  }
}
