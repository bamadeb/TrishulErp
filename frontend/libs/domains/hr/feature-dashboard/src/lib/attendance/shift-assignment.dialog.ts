import { ChangeDetectionStrategy, Component, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { MatButton } from '@angular/material/button';
import { provideNativeDateAdapter } from '@angular/material/core';
import { MatDatepicker, MatDatepickerInput, MatDatepickerToggle } from '@angular/material/datepicker';
import { MAT_DIALOG_DATA, MatDialogModule, MatDialogRef } from '@angular/material/dialog';
import { MatFormField, MatLabel, MatSuffix } from '@angular/material/form-field';
import { MatInput } from '@angular/material/input';
import { MatOption, MatSelect } from '@angular/material/select';
import {
  ShiftAssignmentEmployeeOption,
  ShiftAssignmentItem,
  ShiftAssignmentWrite,
  ShiftItem,
  WeekdayCode,
} from '@trishul/hr-data-access';

export interface ShiftAssignmentDialogData {
  mode: 'add' | 'edit';
  assignment: ShiftAssignmentItem | null;
  employees: ShiftAssignmentEmployeeOption[];
  shifts: ShiftItem[];
  defaultWeeklyOff: WeekdayCode[];
}

@Component({
  selector: 'trishul-shift-assignment-dialog',
  imports: [
    FormsModule,
    MatButton,
    MatDatepicker,
    MatDatepickerInput,
    MatDatepickerToggle,
    MatDialogModule,
    MatFormField,
    MatInput,
    MatLabel,
    MatOption,
    MatSelect,
    MatSuffix,
  ],
  providers: [provideNativeDateAdapter()],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <h2 mat-dialog-title>{{ data.mode === 'add' ? 'Assign Shift' : 'Edit Assignment' }}</h2>
    <mat-dialog-content>
      @if (error()) {
        <p class="err">{{ error() }}</p>
      }
      <div class="grid">
        <mat-form-field appearance="outline">
          <mat-label>Employee</mat-label>
          <mat-select [(ngModel)]="employeeId" name="employee" [disabled]="data.mode === 'edit'">
            @for (emp of data.employees; track emp.id) {
              <mat-option [value]="emp.id">{{ emp.employeeCode }} · {{ emp.employeeName }}</mat-option>
            }
          </mat-select>
        </mat-form-field>
        <mat-form-field appearance="outline">
          <mat-label>Shift</mat-label>
          <mat-select [(ngModel)]="shiftId" name="shift">
            @for (shift of data.shifts; track shift.id) {
              <mat-option [value]="shift.id">{{ shift.code }} · {{ shift.name }}</mat-option>
            }
          </mat-select>
        </mat-form-field>
        <mat-form-field appearance="outline">
          <mat-label>Effective from</mat-label>
          <input matInput [matDatepicker]="fromPicker" [(ngModel)]="fromDate" name="from" />
          <mat-datepicker-toggle matIconSuffix [for]="fromPicker" />
          <mat-datepicker #fromPicker />
        </mat-form-field>
        <mat-form-field appearance="outline">
          <mat-label>Effective to (optional)</mat-label>
          <input matInput [matDatepicker]="toPicker" [(ngModel)]="toDate" name="to" />
          <mat-datepicker-toggle matIconSuffix [for]="toPicker" />
          <mat-datepicker #toPicker />
        </mat-form-field>
        <mat-form-field appearance="outline" class="full">
          <mat-label>Weekly off days</mat-label>
          <mat-select [(ngModel)]="weeklyOffDays" multiple name="offs">
            @for (day of weekdayOptions; track day) {
              <mat-option [value]="day">{{ day }}</mat-option>
            }
          </mat-select>
        </mat-form-field>
      </div>
    </mat-dialog-content>
    <mat-dialog-actions align="end">
      <button mat-button type="button" mat-dialog-close>Cancel</button>
      <button mat-flat-button color="primary" type="button" (click)="save()">Save</button>
    </mat-dialog-actions>
  `,
  styles: `
    mat-dialog-content {
      min-width: min(30rem, 92vw);
    }
    .grid {
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 0.5rem 0.75rem;
    }
    .full {
      grid-column: 1 / -1;
    }
    .err {
      color: #b3261e;
      margin: 0 0 0.75rem;
    }
  `,
})
export class ShiftAssignmentDialog {
  private readonly ref = inject(MatDialogRef<ShiftAssignmentDialog, ShiftAssignmentWrite | null>);
  protected readonly data = inject<ShiftAssignmentDialogData>(MAT_DIALOG_DATA);
  protected readonly error = signal('');
  protected readonly weekdayOptions: WeekdayCode[] = ['MON', 'TUE', 'WED', 'THU', 'FRI', 'SAT', 'SUN'];

  protected employeeId = this.data.assignment?.employeeId ?? this.data.employees[0]?.id ?? 0;
  protected shiftId = this.data.assignment?.shiftId ?? this.data.shifts[0]?.id ?? 0;
  protected fromDate: Date | null = parseDate(this.data.assignment?.fromDate) ?? new Date();
  protected toDate: Date | null = parseDate(this.data.assignment?.toDate);
  protected weeklyOffDays: WeekdayCode[] =
    this.data.assignment?.weeklyOffDays?.length
      ? [...this.data.assignment.weeklyOffDays]
      : [...this.data.defaultWeeklyOff];

  protected save(): void {
    if (!this.employeeId || !this.shiftId || !this.fromDate) {
      this.error.set('Employee, shift and effective-from date are required.');
      return;
    }
    if (this.toDate && this.toDate < this.fromDate) {
      this.error.set('End date cannot be before the start date.');
      return;
    }
    this.ref.close({
      employeeId: this.employeeId,
      shiftId: this.shiftId,
      fromDate: isoDate(this.fromDate),
      toDate: this.toDate ? isoDate(this.toDate) : null,
      weeklyOffDays: this.weeklyOffDays,
      isActive: true,
    });
  }
}

function parseDate(value: string | null | undefined): Date | null {
  if (!value) return null;
  const [y, m, d] = value.slice(0, 10).split('-').map(Number);
  if (!y || !m || !d) return null;
  return new Date(y, m - 1, d);
}

function isoDate(value: Date): string {
  const y = value.getFullYear();
  const m = String(value.getMonth() + 1).padStart(2, '0');
  const d = String(value.getDate()).padStart(2, '0');
  return `${y}-${m}-${d}`;
}
