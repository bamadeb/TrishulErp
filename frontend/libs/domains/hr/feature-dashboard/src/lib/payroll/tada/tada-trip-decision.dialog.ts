import { ChangeDetectionStrategy, Component, inject, signal } from '@angular/core';
import { MatButton } from '@angular/material/button';
import {
  MAT_DIALOG_DATA,
  MatDialog,
  MatDialogActions,
  MatDialogContent,
  MatDialogRef,
  MatDialogTitle,
} from '@angular/material/dialog';
import { MatFormField, MatLabel } from '@angular/material/form-field';
import { MatInput } from '@angular/material/input';
import { Observable } from 'rxjs';

export interface TripDecisionLine {
  label: string;
  value: string;
}

export interface TripDecisionData {
  decision: 'Approved' | 'Rejected';
  lines: readonly TripDecisionLine[];
  submit: (remarks: string) => Observable<unknown>;
}

/** Mandatory remarks before a single trip is approved or rejected. */
@Component({
  selector: 'trishul-tada-trip-decision-dialog',
  imports: [MatButton, MatDialogTitle, MatDialogContent, MatDialogActions, MatFormField, MatLabel, MatInput],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <h2 mat-dialog-title>{{ data.decision === 'Approved' ? 'Approve Trip' : 'Reject Trip' }}</h2>
    <mat-dialog-content>
      <dl>
        @for (line of data.lines; track line.label) {
          <div><dt>{{ line.label }}</dt><dd>{{ line.value }}</dd></div>
        }
      </dl>
      <mat-form-field appearance="outline" subscriptSizing="dynamic">
        <mat-label>{{ data.decision === 'Approved' ? 'Approval Remarks *' : 'Rejection Reason *' }}</mat-label>
        <textarea
          matInput
          class="remarks"
          rows="3"
          maxlength="500"
          [placeholder]="data.decision === 'Approved' ? 'Enter approval remarks...' : 'Enter the reason for rejecting this trip...'"
          [value]="remarks()"
          (input)="remarks.set($any($event.target).value); error.set('')"
        ></textarea>
        <span class="count">{{ remarks().length }} / 500</span>
      </mat-form-field>
      @if (error()) { <p class="hint">{{ error() }}</p> }
    </mat-dialog-content>
    <mat-dialog-actions align="end">
      <button mat-stroked-button type="button" [disabled]="saving()" (click)="cancel()">Cancel</button>
      @if (data.decision === 'Approved') {
        <button mat-flat-button type="button" class="approve" [disabled]="saving()" (click)="confirm()">Confirm Approval</button>
      } @else {
        <button mat-flat-button type="button" class="reject" [disabled]="saving()" (click)="confirm()">Confirm Rejection</button>
      }
    </mat-dialog-actions>
  `,
  styles: `
    h2 {
      margin: 0;
      padding: 14px 18px 4px;
      font-size: 20px;
      font-weight: 600;
      line-height: 1.3;
    }
    mat-dialog-content {
      display: grid;
      gap: 0.55rem;
      max-height: none;
      padding: 6px 18px 4px;
    }
    dl {
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 0.35rem 0.85rem;
      margin: 0;
    }
    dt { color: #64748b; font-size: 12px; font-weight: 500; }
    dd { margin: 0; color: #0f172a; font-size: 14px; font-weight: 600; line-height: 1.3; }
    .mat-mdc-form-field { font-size: 13px; }
    .mat-mdc-form-field-infix { min-height: 0; padding-top: 8px; padding-bottom: 4px; }
    .remarks {
      height: 90px;
      min-height: 90px;
      padding: 8px 10px;
      font-size: 13px;
      line-height: 1.35;
      resize: vertical;
    }
    .count { display: block; margin-top: 2px; color: #64748b; font-size: 11px; text-align: right; }
    .hint { margin: 0; color: #b91c1c; font-size: 12px; }
    mat-dialog-actions {
      min-height: 0;
      margin: 0;
      padding: 6px 18px 14px;
      gap: 8px;
    }
    mat-dialog-actions button {
      height: 36px;
      padding: 0 14px;
      font-size: 14px;
      font-weight: 500;
      border-radius: 8px;
    }
    .approve { --mat-button-filled-container-color: #15803d; --mat-button-filled-label-text-color: #fff; }
    .reject { --mat-button-filled-container-color: #dc2626; --mat-button-filled-label-text-color: #fff; }
  `,
})
export class TadaTripDecisionDialog {
  protected readonly data = inject<TripDecisionData>(MAT_DIALOG_DATA);
  private readonly dialogRef = inject(MatDialogRef<TadaTripDecisionDialog, boolean>);
  protected readonly remarks = signal('');
  protected readonly error = signal('');
  protected readonly saving = signal(false);

  protected cancel(): void {
    if (this.saving()) return;
    this.dialogRef.close(false);
  }

  protected confirm(): void {
    const remarks = this.remarks().trim();
    if (this.saving()) return;
    if (!remarks) {
      this.error.set(this.data.decision === 'Approved' ? 'Enter approval remarks.' : 'Enter the reason for rejecting this trip.');
      return;
    }
    this.saving.set(true);
    this.error.set('');
    this.dialogRef.disableClose = true;
    this.data.submit(remarks).subscribe({
      next: () => {
        this.saving.set(false);
        this.dialogRef.disableClose = false;
        this.dialogRef.close(true);
      },
      error: (error: { error?: { detail?: unknown } }) => {
        this.saving.set(false);
        this.dialogRef.disableClose = false;
        const detail = error?.error?.detail;
        this.error.set(typeof detail === 'string' && detail ? detail : 'The trip decision could not be saved.');
      },
    });
  }
}

export function openTripDecision(dialog: MatDialog, data: TripDecisionData): Observable<boolean | undefined> {
  return dialog
    .open<TadaTripDecisionDialog, TripDecisionData, boolean>(TadaTripDecisionDialog, {
      data,
      width: '540px',
      maxWidth: '92vw',
      autoFocus: 'textarea',
    })
    .afterClosed();
}
