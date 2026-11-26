import { ChangeDetectionStrategy, Component, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { MatButton } from '@angular/material/button';
import { MatCheckbox } from '@angular/material/checkbox';
import { MAT_DIALOG_DATA, MatDialogModule, MatDialogRef } from '@angular/material/dialog';
import { MatFormField, MatLabel } from '@angular/material/form-field';
import { MatInput } from '@angular/material/input';
import { MatSlideToggle } from '@angular/material/slide-toggle';
import { AttendanceRules, AttendanceRulesWrite, WeekdayCode } from '@trishul/hr-data-access';

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
        <mat-form-field appearance="outline" subscriptSizing="dynamic">
          <mat-label>Standard work hours / day</mat-label>
          <input matInput type="number" min="1" max="24" step="0.25" [(ngModel)]="form.standardWorkHours" />
        </mat-form-field>
        <mat-form-field appearance="outline" subscriptSizing="dynamic">
          <mat-label>Working days / week</mat-label>
          <input matInput type="number" min="1" max="7" [(ngModel)]="form.workingDaysPerWeek" />
        </mat-form-field>
        <mat-form-field appearance="outline" subscriptSizing="dynamic">
          <mat-label>Late arrival grace (min)</mat-label>
          <input matInput type="number" min="0" max="240" [(ngModel)]="form.lateArrivalGraceMinutes" />
        </mat-form-field>
        <mat-form-field appearance="outline" subscriptSizing="dynamic">
          <mat-label>Early exit grace (min)</mat-label>
          <input matInput type="number" min="0" max="240" [(ngModel)]="form.earlyExitGraceMinutes" />
        </mat-form-field>
        <mat-form-field appearance="outline" subscriptSizing="dynamic" class="span">
          <mat-label>Grace days per employee / month</mat-label>
          <input matInput type="number" min="0" max="31" [(ngModel)]="form.graceDaysPerMonth" />
        </mat-form-field>
        <mat-form-field appearance="outline" subscriptSizing="dynamic">
          <mat-label>OT after hours</mat-label>
          <input matInput type="number" min="1" max="24" step="0.25" [(ngModel)]="form.otAfterHours" />
        </mat-form-field>
        <mat-form-field appearance="outline" subscriptSizing="dynamic">
          <mat-label>Weekly off applies to</mat-label>
          <input matInput maxlength="80" [(ngModel)]="form.weeklyOffAppliesTo" />
        </mat-form-field>
      </div>
      <p class="hint">
        Each employee gets the late-arrival grace on {{ form.graceDaysPerMonth || 0 }} days per calendar month. Those
        days have no salary deduction. From the next late-arrival day, half-day salary deduction applies. Grace usage
        is tracked employee-wise and month-wise, and late arrivals and deductions are retained for payroll. These rules
        apply to every shift.
      </p>
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
        <mat-slide-toggle [(ngModel)]="form.autoAttendanceEnabled">Auto attendance (app)</mat-slide-toggle>
        <mat-slide-toggle [(ngModel)]="form.manualAttendanceEnabled">Manual attendance (with approval)</mat-slide-toggle>
      </div>
    </mat-dialog-content>
    <mat-dialog-actions align="end">
      <button mat-button type="button" mat-dialog-close>Cancel</button>
      <button mat-flat-button color="primary" type="button" (click)="save()">Save rules</button>
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
      padding: 14px 16px 0;
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
      padding: 12px 16px 4px;
    }

    .grid {
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 0.65rem 0.75rem;
      width: 100%;
      min-width: 0;
    }

    .span {
      grid-column: 1 / -1;
    }

    mat-form-field {
      width: 100%;
      min-width: 0;
    }

    /* Keep the outline from cutting through a floated label. */
    :host ::ng-deep .mdc-floating-label--float-above {
      background: #fff;
      padding: 0 4px;
      overflow: visible;
      max-width: calc(100% - 8px);
      z-index: 1;
    }

    .hint,
    .label,
    .err {
      overflow-wrap: anywhere;
    }

    .hint {
      margin: 0.1rem 0 0.45rem;
      color: #475569;
      font-size: 0.75rem;
      line-height: 1.4;
    }

    .block {
      margin: 0 0 0.5rem;
    }

    .label {
      display: block;
      margin-bottom: 0.25rem;
      color: #5c6b82;
      font-size: 0.75rem;
      font-weight: 600;
      line-height: 1.2;
    }

    .days {
      display: flex;
      flex-wrap: wrap;
      align-items: center;
      gap: 0.15rem 0.65rem;
    }

    .days mat-checkbox {
      --mat-checkbox-state-layer-size: 32px;
      font-size: 13px;
    }

    .toggles {
      display: grid;
      gap: 0.35rem;
    }

    .toggles mat-slide-toggle {
      --mat-slide-toggle-track-height: 22px;
      --mat-slide-toggle-track-width: 42px;
      --mat-slide-toggle-track-shape: 11px;
      --mat-slide-toggle-with-icon-handle-size: 18px;
      --mat-slide-toggle-pressed-handle-size: 18px;
      --mat-slide-toggle-unselected-handle-size: 18px;
      --mat-slide-toggle-selected-handle-size: 18px;
      font-size: 13px;
    }

    :host ::ng-deep .mdc-switch__icons {
      display: none;
    }

    .err {
      margin: 0 0 0.5rem;
      color: #b3261e;
      font-size: 0.75rem;
    }

    mat-dialog-actions {
      justify-content: flex-end;
      gap: 0.35rem;
      min-height: 0;
      margin: 0;
      padding: 4px 16px 12px;
      overflow: visible;
    }

    mat-dialog-actions button {
      min-width: 0;
      height: 32px;
      padding: 0 12px;
      font-size: 13px;
      line-height: 32px;
    }

    @media (max-width: 560px) {
      .grid {
        grid-template-columns: minmax(0, 1fr);
      }

      .span {
        grid-column: auto;
      }
    }
  `,
})
export class AttendanceRulesEditDialog {
  private readonly ref = inject(MatDialogRef<AttendanceRulesEditDialog, AttendanceRulesWrite | null>);
  private readonly data = inject<AttendanceRules>(MAT_DIALOG_DATA);
  protected readonly weekdays = WEEKDAYS;
  protected readonly error = signal('');

  protected form: AttendanceRulesWrite = {
    standardWorkHours: this.data.standardWorkHours,
    workingDaysPerWeek: this.data.workingDaysPerWeek,
    lateArrivalGraceMinutes: this.data.lateArrivalGraceMinutes,
    earlyExitGraceMinutes: this.data.earlyExitGraceMinutes,
    graceDaysPerMonth: this.data.graceDaysPerMonth || 3,
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
