import { ChangeDetectionStrategy, Component, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { MatButton } from '@angular/material/button';
import { provideNativeDateAdapter } from '@angular/material/core';
import { MatDatepicker, MatDatepickerInput, MatDatepickerToggle } from '@angular/material/datepicker';
import { MAT_DIALOG_DATA, MatDialogModule, MatDialogRef } from '@angular/material/dialog';
import { MatFormField, MatLabel, MatSuffix } from '@angular/material/form-field';
import { MatInput } from '@angular/material/input';
import { MatOption, MatSelect } from '@angular/material/select';
import { MatSlideToggle } from '@angular/material/slide-toggle';
import {
  ShiftAssignmentBulkWrite,
  ShiftAssignmentEmployeeOption,
  ShiftAssignmentItem,
  ShiftAssignmentWrite,
  ShiftItem,
  WeekdayCode,
} from '@trishul/hr-data-access';

export type ShiftAssignmentDialogResult =
  | { kind: 'one'; body: ShiftAssignmentWrite }
  | { kind: 'many'; body: ShiftAssignmentBulkWrite };

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
    MatSlideToggle,
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
        @if (data.mode === 'add') {
          <mat-slide-toggle class="full" [(ngModel)]="allEmployees" name="all">
            All active employees
          </mat-slide-toggle>
        }
        <mat-form-field appearance="outline" subscriptSizing="dynamic" class="full">
          <mat-label>Employee</mat-label>
          @if (data.mode === 'edit') {
            <mat-select [(ngModel)]="employeeId" name="employee" disabled>
              @for (emp of data.employees; track emp.id) {
                <mat-option [value]="emp.id">{{ emp.employeeCode }} · {{ emp.employeeName }}</mat-option>
              }
            </mat-select>
          } @else {
            <mat-select [(ngModel)]="employeeIds" name="employees" multiple [disabled]="allEmployees">
              @for (emp of data.employees; track emp.id) {
                <mat-option [value]="emp.id">{{ emp.employeeCode }} · {{ emp.employeeName }}</mat-option>
              }
            </mat-select>
          }
        </mat-form-field>
        <mat-form-field appearance="outline" subscriptSizing="dynamic">
          <mat-label>Shift</mat-label>
          <mat-select [(ngModel)]="shiftId" name="shift">
            @for (shift of data.shifts; track shift.id) {
              <mat-option [value]="shift.id">{{ shift.code }} · {{ shift.name }}</mat-option>
            }
          </mat-select>
        </mat-form-field>
        <mat-form-field appearance="outline" subscriptSizing="dynamic">
          <mat-label>Effective from</mat-label>
          <input matInput [matDatepicker]="fromPicker" [(ngModel)]="fromDate" name="from" />
          <mat-datepicker-toggle matIconSuffix [for]="fromPicker" />
          <mat-datepicker #fromPicker />
        </mat-form-field>
        <mat-form-field appearance="outline" subscriptSizing="dynamic">
          <mat-label>Effective to (optional)</mat-label>
          <input matInput [matDatepicker]="toPicker" [(ngModel)]="toDate" name="to" />
          <mat-datepicker-toggle matIconSuffix [for]="toPicker" />
          <mat-datepicker #toPicker />
        </mat-form-field>
        <mat-form-field appearance="outline" subscriptSizing="dynamic" class="full">
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
    :host {
      display: block;
      width: 100%;
      max-width: 100%;
    }

    h2[mat-dialog-title] {
      margin: 0;
      padding: 12px 16px 0;
      font-size: 1.05rem;
      line-height: 1.3;
    }

    :host mat-dialog-content.mat-mdc-dialog-content {
      display: block;
      width: 100%;
      max-width: 100%;
      max-height: none;
      box-sizing: border-box;
      overflow: visible;
      padding: 10px 16px 2px;
    }

    .grid {
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 0.55rem 0.65rem;
      width: 100%;
      min-width: 0;
    }

    .full {
      grid-column: 1 / -1;
    }

    mat-form-field {
      width: 100%;
      min-width: 0;
    }

    :host ::ng-deep .mdc-floating-label--float-above {
      background: #fff;
      padding: 0 4px;
      overflow: visible;
      z-index: 1;
    }

    mat-slide-toggle {
      --mat-slide-toggle-track-height: 20px;
      --mat-slide-toggle-track-width: 36px;
      --mat-slide-toggle-track-shape: 10px;
      --mat-slide-toggle-with-icon-handle-size: 16px;
      --mat-slide-toggle-pressed-handle-size: 16px;
      --mat-slide-toggle-unselected-handle-size: 16px;
      --mat-slide-toggle-selected-handle-size: 16px;
      font-size: 13px;
    }

    :host ::ng-deep .mdc-switch__icons {
      display: none;
    }

    .err {
      margin: 0 0 0.45rem;
      color: #b3261e;
      font-size: 0.75rem;
    }

    mat-dialog-actions {
      justify-content: flex-end;
      gap: 0.35rem;
      min-height: 0;
      margin: 0;
      padding: 4px 16px 12px;
    }

    mat-dialog-actions button {
      min-width: 0;
      height: 32px;
      padding: 0 12px;
      font-size: 13px;
      line-height: 32px;
    }
  `,
})
export class ShiftAssignmentDialog {
  private readonly ref = inject(MatDialogRef<ShiftAssignmentDialog, ShiftAssignmentDialogResult | null>);
  protected readonly data = inject<ShiftAssignmentDialogData>(MAT_DIALOG_DATA);
  protected readonly error = signal('');
  protected readonly weekdayOptions: WeekdayCode[] = ['MON', 'TUE', 'WED', 'THU', 'FRI', 'SAT', 'SUN'];

  protected allEmployees = false;
  protected employeeId = this.data.assignment?.employeeId ?? this.data.employees[0]?.id ?? 0;
  protected employeeIds: number[] = this.data.assignment ? [this.data.assignment.employeeId] : [];
  protected shiftId = this.data.assignment?.shiftId ?? this.data.shifts[0]?.id ?? 0;
  protected fromDate: Date | null = parseDate(this.data.assignment?.fromDate) ?? new Date();
  protected toDate: Date | null = parseDate(this.data.assignment?.toDate);
  protected weeklyOffDays: WeekdayCode[] =
    this.data.assignment?.weeklyOffDays?.length
      ? [...this.data.assignment.weeklyOffDays]
      : [...this.data.defaultWeeklyOff];

  protected save(): void {
    if (!this.shiftId || !this.fromDate) {
      this.error.set('Shift and effective-from date are required.');
      return;
    }
    if (!this.allEmployees && (this.data.mode === 'edit' ? !this.employeeId : this.employeeIds.length === 0)) {
      this.error.set('Select at least one employee, or assign the shift to all active employees.');
      return;
    }
    if (this.toDate && this.toDate < this.fromDate) {
      this.error.set('End date cannot be before the start date.');
      return;
    }
    const fromDate = isoDate(this.fromDate);
    const toDate = this.toDate ? isoDate(this.toDate) : null;
    if (this.data.mode === 'add' && (this.allEmployees || this.employeeIds.length > 1)) {
      this.ref.close({
        kind: 'many',
        body: {
          shiftId: this.shiftId,
          fromDate,
          toDate,
          weeklyOffDays: this.weeklyOffDays,
          allEmployees: this.allEmployees,
          employeeIds: this.allEmployees ? [] : this.employeeIds,
        },
      });
      return;
    }
    this.ref.close({
      kind: 'one',
      body: {
        employeeId: this.data.mode === 'edit' ? this.employeeId : this.employeeIds[0],
        shiftId: this.shiftId,
        fromDate,
        toDate,
        weeklyOffDays: this.weeklyOffDays,
        isActive: true,
      },
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
