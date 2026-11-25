import { ChangeDetectionStrategy, Component, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { MatButton } from '@angular/material/button';
import { MatCheckbox } from '@angular/material/checkbox';
import { MAT_DIALOG_DATA, MatDialogModule, MatDialogRef } from '@angular/material/dialog';
import { MatFormField, MatLabel } from '@angular/material/form-field';
import { MatInput } from '@angular/material/input';
import { MatSlideToggle } from '@angular/material/slide-toggle';
import { AttendanceRules, AttendanceRulesWrite, WeekdayCode } from '@trishul/hr-data-access';

function ordinal(day: number): string {
  const mod100 = day % 100;
  if (mod100 >= 11 && mod100 <= 13) return `${day}th`;
  if (day % 10 === 1) return `${day}st`;
  if (day % 10 === 2) return `${day}nd`;
  if (day % 10 === 3) return `${day}rd`;
  return `${day}th`;
}

const WEEKDAYS: { id: WeekdayCode; label: string }[] = [
  { id: 'MON', label: 'Mon' },
  { id: 'TUE', label: 'Tue' },
  { id: 'WED', label: 'Wed' },
  { id: 'THU', label: 'Thu' },
  { id: 'FRI', label: 'Fri' },
  { id: 'SAT', label: 'Sat' },
  { id: 'SUN', label: 'Sun' },
];

@Component({
  selector: 'trishul-attendance-rules-edit-dialog',
  imports: [
    FormsModule,
    MatButton,
    MatCheckbox,
    MatDialogModule,
    MatFormField,
    MatInput,
    MatLabel,
    MatSlideToggle,
  ],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <h2 mat-dialog-title>Edit Attendance Rules</h2>
    <mat-dialog-content>
      @if (error()) {
        <p class="err">{{ error() }}</p>
      }
      <div class="grid">
        <mat-form-field appearance="outline">
          <mat-label>Standard work hours / day</mat-label>
          <input matInput type="number" min="1" max="24" step="0.25" [(ngModel)]="form.standardWorkHours" />
        </mat-form-field>
        <mat-form-field appearance="outline">
          <mat-label>Working days / week</mat-label>
          <input matInput type="number" min="1" max="7" [(ngModel)]="form.workingDaysPerWeek" />
        </mat-form-field>
        <mat-form-field appearance="outline">
          <mat-label>Late arrival grace (min)</mat-label>
          <input matInput type="number" min="0" max="240" [(ngModel)]="form.lateArrivalGraceMinutes" />
        </mat-form-field>
        <mat-form-field appearance="outline">
          <mat-label>Early exit grace (min)</mat-label>
          <input matInput type="number" min="0" max="240" [(ngModel)]="form.earlyExitGraceMinutes" />
        </mat-form-field>
        <p class="hint">
          Each employee gets this late-arrival grace on {{ graceDays }} days per calendar month. Those days have no
          salary deduction. From the {{ nextLateDay }} late-arrival day onwards, half-day salary deduction applies.
          Grace usage is tracked employee-wise and month-wise, and late arrivals and deductions are retained for payroll.
        </p>
        <mat-form-field appearance="outline">
          <mat-label>OT after hours</mat-label>
          <input matInput type="number" min="1" max="24" step="0.25" [(ngModel)]="form.otAfterHours" />
        </mat-form-field>
        <mat-form-field appearance="outline">
          <mat-label>Weekly off applies to</mat-label>
          <input matInput maxlength="80" [(ngModel)]="form.weeklyOffAppliesTo" />
        </mat-form-field>
      </div>
      <div class="block">
        <span class="label">Weekly off days</span>
        <div class="days">
          @for (day of weekdays; track day.id) {
            <mat-checkbox [checked]="hasDay(day.id)" (change)="toggleDay(day.id, $event.checked)">
              {{ day.label }}
            </mat-checkbox>
          }
        </div>
      </div>
      <div class="toggles">
        <mat-slide-toggle [(ngModel)]="form.otApprovalRequired">OT approval required</mat-slide-toggle>
        <mat-slide-toggle [(ngModel)]="form.autoAttendanceEnabled">Auto attendance (biometric)</mat-slide-toggle>
        <mat-slide-toggle [(ngModel)]="form.manualAttendanceEnabled">Manual attendance (with approval)</mat-slide-toggle>
      </div>
    </mat-dialog-content>
    <mat-dialog-actions align="end">
      <button mat-button type="button" mat-dialog-close>Cancel</button>
      <button mat-flat-button color="primary" type="button" (click)="save()">Save rules</button>
    </mat-dialog-actions>
  `,
  styles: `
    mat-dialog-content {
      min-width: min(32rem, 92vw);
    }
    .grid {
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 0.5rem 0.75rem;
    }
    .block {
      margin: 0.5rem 0 0.85rem;
    }
    .label {
      display: block;
      font-size: 0.78rem;
      color: #5c6b82;
      margin-bottom: 0.35rem;
    }
    .days {
      display: flex;
      flex-wrap: wrap;
      gap: 0.35rem 0.75rem;
    }
    .toggles {
      display: grid;
      gap: 0.65rem;
    }
    .err {
      color: #b3261e;
      margin: 0 0 0.75rem;
    }
    .hint {
      grid-column: 1 / -1;
      margin: 0;
      color: #475569;
      font-size: 0.75rem;
      line-height: 1.45;
    }
  `,
})
export class AttendanceRulesEditDialog {
  private readonly ref = inject(MatDialogRef<AttendanceRulesEditDialog, AttendanceRulesWrite | null>);
  private readonly data = inject<AttendanceRules>(MAT_DIALOG_DATA);
  protected readonly weekdays = WEEKDAYS;
  protected readonly graceDays = this.data.graceDaysPerMonth || 3;
  protected readonly nextLateDay = ordinal(this.graceDays + 1);
  protected readonly error = signal('');

  protected form: AttendanceRulesWrite = {
    standardWorkHours: this.data.standardWorkHours,
    workingDaysPerWeek: this.data.workingDaysPerWeek,
    lateArrivalGraceMinutes: this.data.lateArrivalGraceMinutes,
    earlyExitGraceMinutes: this.data.earlyExitGraceMinutes,
    otAfterHours: this.data.otAfterHours,
    otApprovalRequired: this.data.otApprovalRequired,
    weeklyOffDays: [...this.data.weeklyOffDays],
    weeklyOffAppliesTo: this.data.weeklyOffAppliesTo,
    autoAttendanceEnabled: this.data.autoAttendanceEnabled,
    manualAttendanceEnabled: this.data.manualAttendanceEnabled,
  };

  protected hasDay(day: WeekdayCode): boolean {
    return this.form.weeklyOffDays.includes(day);
  }

  protected toggleDay(day: WeekdayCode, checked: boolean): void {
    const set = new Set(this.form.weeklyOffDays);
    if (checked) set.add(day);
    else set.delete(day);
    this.form.weeklyOffDays = WEEKDAYS.map((item) => item.id).filter((id) => set.has(id));
  }

  protected save(): void {
    if (this.form.workingDaysPerWeek < 7 && this.form.weeklyOffDays.length === 0) {
      this.error.set('Select at least one weekly off day when working fewer than seven days.');
      return;
    }
    if (this.form.workingDaysPerWeek + this.form.weeklyOffDays.length > 7) {
      this.error.set('Working days plus weekly off days cannot exceed seven.');
      return;
    }
    this.ref.close({ ...this.form });
  }
}
