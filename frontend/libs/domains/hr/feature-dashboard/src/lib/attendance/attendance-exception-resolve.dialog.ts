import { ChangeDetectionStrategy, Component, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { MatButton, MatIconButton } from '@angular/material/button';
import {
  MAT_DIALOG_DATA,
  MatDialogClose,
  MatDialogRef,
} from '@angular/material/dialog';
import { MatFormField, MatLabel } from '@angular/material/form-field';
import { MatIcon } from '@angular/material/icon';
import { MatInput } from '@angular/material/input';
import { MatOption, MatSelect } from '@angular/material/select';

export type ExceptionResolvedStatus = 'Present' | 'Absent' | 'Half day' | 'On duty';

export interface ExceptionResolveData {
  employeeName: string;
  exceptionType: string;
  date: string;
  requireStatus: boolean;
}

export interface ExceptionResolveResult {
  resolvedStatus?: ExceptionResolvedStatus;
  remark: string;
}

const STATUS_OPTIONS: ExceptionResolvedStatus[] = ['Present', 'Half day', 'Absent', 'On duty'];

/** Resolve attendance exception — requires explicit status for Missing Punch / Absent. */
@Component({
  selector: 'trishul-attendance-exception-resolve-dialog',
  imports: [
    FormsModule,
    MatButton,
    MatDialogClose,
    MatFormField,
    MatIcon,
    MatIconButton,
    MatInput,
    MatLabel,
    MatOption,
    MatSelect,
  ],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <header class="head">
      <div>
        <h2>Resolve exception</h2>
        <p>{{ data.employeeName }} · {{ data.exceptionType }} · {{ data.date }}</p>
      </div>
      <button mat-icon-button type="button" mat-dialog-close aria-label="Close">
        <mat-icon>close</mat-icon>
      </button>
    </header>

    <div class="body">
      @if (data.requireStatus) {
        <p class="hint">
          {{ data.exceptionType }} has no automatic LOP policy. Choose the attendance status to
          apply.
        </p>
        <mat-form-field appearance="outline" subscriptSizing="dynamic">
          <mat-label>Resolved status</mat-label>
          <mat-select [ngModel]="status()" (ngModelChange)="status.set($event)">
            @for (opt of statusOptions; track opt) {
              <mat-option [value]="opt">{{ opt }}</mat-option>
            }
          </mat-select>
        </mat-form-field>
      } @else if (data.exceptionType === 'Late Arrival') {
        <p class="hint">
          Per HR policy, late beyond grace defaults to Half day salary impact unless you choose
          another status.
        </p>
        <mat-form-field appearance="outline" subscriptSizing="dynamic">
          <mat-label>Resolved status</mat-label>
          <mat-select [ngModel]="status()" (ngModelChange)="status.set($event)">
            @for (opt of statusOptions; track opt) {
              <mat-option [value]="opt">{{ opt }}</mat-option>
            }
          </mat-select>
        </mat-form-field>
      } @else {
        <p class="hint">This will mark the day as Present and clear the exception.</p>
      }
      <mat-form-field appearance="outline" subscriptSizing="dynamic">
        <mat-label>Remark (optional)</mat-label>
        <input matInput [ngModel]="remark()" (ngModelChange)="remark.set($event)" maxlength="300" />
      </mat-form-field>
    </div>

    <footer class="actions">
      <button mat-stroked-button type="button" mat-dialog-close>Cancel</button>
      <button mat-flat-button color="primary" type="button" (click)="submit()">Resolve</button>
    </footer>
  `,
  styles: [
    `
      :host {
        display: block;
        width: min(28rem, 92vw);
        color: #1b2a4a;
      }
      .head {
        display: flex;
        justify-content: space-between;
        gap: 0.75rem;
        padding: 1rem 1rem 0.5rem;
        h2 {
          margin: 0;
          font-size: 1.05rem;
        }
        p {
          margin: 0.2rem 0 0;
          color: #64748b;
          font-size: 0.8rem;
        }
      }
      .body {
        display: grid;
        gap: 0.75rem;
        padding: 0.5rem 1rem 0.25rem;
      }
      .hint {
        margin: 0;
        color: #475569;
        font-size: 0.82rem;
        line-height: 1.4;
      }
      .actions {
        display: flex;
        justify-content: flex-end;
        gap: 0.5rem;
        padding: 0.75rem 1rem 1rem;
      }
    `,
  ],
})
export class AttendanceExceptionResolveDialog {
  private readonly dialogRef = inject(
    MatDialogRef<AttendanceExceptionResolveDialog, ExceptionResolveResult | null>,
  );
  protected readonly data = inject<ExceptionResolveData>(MAT_DIALOG_DATA);
  protected readonly statusOptions = STATUS_OPTIONS;
  protected readonly status = signal<ExceptionResolvedStatus>(
    this.data.exceptionType === 'Late Arrival' ? 'Half day' : 'Present',
  );
  protected readonly remark = signal('Resolved from Attendance Exceptions');

  protected submit(): void {
    const needsStatus =
      this.data.requireStatus || this.data.exceptionType === 'Late Arrival';
    this.dialogRef.close({
      resolvedStatus: needsStatus ? this.status() : undefined,
      remark: this.remark().trim() || 'Resolved from Attendance Exceptions',
    });
  }
}
