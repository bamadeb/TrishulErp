import { DatePipe } from '@angular/common';
import { ChangeDetectionStrategy, Component, computed, inject, signal } from '@angular/core';
import { MatButton } from '@angular/material/button';
import { provideNativeDateAdapter } from '@angular/material/core';
import {
  MatDatepicker,
  MatDatepickerInput,
  MatDatepickerToggle,
} from '@angular/material/datepicker';
import {
  MAT_DIALOG_DATA,
  MatDialogActions,
  MatDialogClose,
  MatDialogContent,
  MatDialogRef,
  MatDialogTitle,
} from '@angular/material/dialog';
import { MatFormField, MatHint, MatLabel, MatSuffix } from '@angular/material/form-field';
import { MatInput } from '@angular/material/input';
import { MatSnackBar } from '@angular/material/snack-bar';
import { EmployeesApi, EmploymentEvent } from '@trishul/hr-data-access';

export interface EmploymentHistoryDialogData {
  employeeId: number;
  fullName: string;
  employeeCode: string;
  canManage: boolean;
}

function isoDay(value: Date): string {
  const month = String(value.getMonth() + 1).padStart(2, '0');
  const day = String(value.getDate()).padStart(2, '0');
  return `${value.getFullYear()}-${month}-${day}`;
}

function problemDetail(error: unknown): string {
  const detail = (error as { error?: { detail?: unknown } })?.error?.detail;
  return typeof detail === 'string' && detail ? detail : 'Could not record the confirmation.';
}

/** Employment events for one employee, and a way to record confirmation. */
@Component({
  selector: 'trishul-employee-history-dialog',
  imports: [
    DatePipe,
    MatButton,
    MatDialogTitle,
    MatDialogContent,
    MatDialogActions,
    MatDialogClose,
    MatFormField,
    MatLabel,
    MatHint,
    MatSuffix,
    MatInput,
    MatDatepicker,
    MatDatepickerInput,
    MatDatepickerToggle,
  ],
  providers: [provideNativeDateAdapter()],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <h2 mat-dialog-title>Employment history</h2>
    <mat-dialog-content>
      <p class="who">{{ data.fullName }} · {{ data.employeeCode }}</p>
      @if (events() === null) {
        <p>Loading…</p>
      } @else if (events()!.length === 0) {
        <p>No employment events are recorded for this employee.</p>
      } @else {
        <ul>
          @for (event of events()!; track event.id) {
            <li>
              <strong>{{ event.eventType }}</strong>
              <span>{{ event.effectiveDate | date: 'dd MMM y' }}</span>
              @if (event.remarks) {
                <span class="remarks">{{ event.remarks }}</span>
              }
            </li>
          }
        </ul>
      }
      @if (canRecord()) {
        <form class="confirm" (submit)="$event.preventDefault(); save()">
          <mat-form-field appearance="outline" subscriptSizing="dynamic">
            <mat-label>Confirmation date</mat-label>
            <input
              matInput
              [matDatepicker]="picker"
              [value]="confirmDate()"
              (dateChange)="onDate($event)"
            />
            <mat-datepicker-toggle matIconSuffix [for]="picker" />
            <mat-datepicker #picker />
            <mat-hint>Leave can be applied on or after this date.</mat-hint>
          </mat-form-field>
          <mat-form-field appearance="outline" subscriptSizing="dynamic">
            <mat-label>Remarks</mat-label>
            <input matInput [value]="remarks()" (input)="onRemarks($event)" maxlength="500" />
          </mat-form-field>
          @if (error()) {
            <p class="error">{{ error() }}</p>
          }
        </form>
      } @else if (confirmedOn()) {
        <p class="done">Confirmed on {{ confirmedOn() | date: 'dd MMM y' }}.</p>
      }
    </mat-dialog-content>
    <mat-dialog-actions align="end">
      @if (canRecord()) {
        <button mat-flat-button type="button" (click)="save()" [disabled]="saving() || !confirmDate()">
          Confirm
        </button>
      }
      <button mat-button type="button" [mat-dialog-close]="saved()">Close</button>
    </mat-dialog-actions>
  `,
  styles: `
    .who,
    .done {
      margin: 0 0 0.75rem;
      color: var(--mat-sys-on-surface-variant);
    }
    ul {
      margin: 0 0 0.75rem;
      padding: 0;
      list-style: none;
    }
    li {
      display: flex;
      flex-wrap: wrap;
      gap: 0.5rem 1rem;
      padding: 0.5rem 0;
      border-top: 1px solid var(--mat-sys-outline-variant);
    }
    .remarks {
      flex-basis: 100%;
      color: var(--mat-sys-on-surface-variant);
    }
    .confirm {
      display: grid;
      gap: 0.65rem;
      margin-top: 0.75rem;
    }
    .error {
      margin: 0;
      color: var(--mat-sys-error);
    }
  `,
})
export class EmployeeHistoryDialog {
  protected readonly data = inject<EmploymentHistoryDialogData>(MAT_DIALOG_DATA);
  private readonly api = inject(EmployeesApi);
  private readonly snackBar = inject(MatSnackBar);
  private readonly dialogRef = inject(MatDialogRef<EmployeeHistoryDialog, boolean>);
  protected readonly events = signal<EmploymentEvent[] | null>(null);
  protected readonly confirmDate = signal<Date | null>(new Date());
  protected readonly remarks = signal('');
  protected readonly saving = signal(false);
  protected readonly error = signal('');
  protected readonly saved = signal(false);
  protected readonly confirmedOn = computed(() => {
    const rows = this.events();
    if (!rows) return null;
    const dates = rows
      .filter((row) => row.eventType === 'Confirmed')
      .map((row) => row.effectiveDate)
      .sort();
    return dates.at(-1) ?? null;
  });
  protected readonly canRecord = computed(
    () => this.data.canManage && this.events() !== null && this.confirmedOn() === null,
  );

  constructor() {
    this.load();
  }

  protected onDate(event: { value: Date | null }): void {
    this.confirmDate.set(event.value);
  }

  protected onRemarks(event: Event): void {
    this.remarks.set((event.target as HTMLInputElement).value);
  }

  protected save(): void {
    const value = this.confirmDate();
    if (!value || this.saving()) return;
    this.saving.set(true);
    this.error.set('');
    this.api.confirmEmployee(this.data.employeeId, isoDay(value), this.remarks().trim() || null).subscribe({
      next: () => {
        this.saving.set(false);
        this.saved.set(true);
        this.snackBar.open('Employee confirmed.', 'Close', { duration: 2500 });
        this.dialogRef.close(true);
      },
      error: (error: unknown) => {
        this.saving.set(false);
        this.error.set(problemDetail(error));
      },
    });
  }

  private load(): void {
    this.api.employmentHistory(this.data.employeeId).subscribe({
      next: (rows) => this.events.set(rows),
      error: () => this.events.set([]),
    });
  }
}
