import { DatePipe } from '@angular/common';
import { ChangeDetectionStrategy, Component, inject, signal } from '@angular/core';
import { MatButton } from '@angular/material/button';
import {
  MAT_DIALOG_DATA,
  MatDialogActions,
  MatDialogClose,
  MatDialogContent,
  MatDialogTitle,
} from '@angular/material/dialog';
import { EmployeesApi, EmploymentEvent } from '@trishul/hr-data-access';

export interface EmploymentHistoryDialogData {
  employeeId: number;
  fullName: string;
  employeeCode: string;
}

/** Employment events already stored for one employee. */
@Component({
  selector: 'trishul-employee-history-dialog',
  imports: [
    DatePipe,
    MatButton,
    MatDialogTitle,
    MatDialogContent,
    MatDialogActions,
    MatDialogClose,
  ],
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
    </mat-dialog-content>
    <mat-dialog-actions align="end">
      <button mat-button type="button" mat-dialog-close>Close</button>
    </mat-dialog-actions>
  `,
  styles: `
    .who {
      margin: 0 0 0.75rem;
      color: var(--mat-sys-on-surface-variant);
    }
    ul {
      margin: 0;
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
  `,
})
export class EmployeeHistoryDialog {
  protected readonly data = inject<EmploymentHistoryDialogData>(MAT_DIALOG_DATA);
  private readonly api = inject(EmployeesApi);
  protected readonly events = signal<EmploymentEvent[] | null>(null);

  constructor() {
    this.api.employmentHistory(this.data.employeeId).subscribe({
      next: (rows) => this.events.set(rows),
      error: () => this.events.set([]),
    });
  }
}
