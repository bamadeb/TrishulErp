import { ChangeDetectionStrategy, Component, inject } from '@angular/core';
import { MatButton } from '@angular/material/button';
import {
  MAT_DIALOG_DATA,
  MatDialogActions,
  MatDialogClose,
  MatDialogContent,
  MatDialogTitle,
} from '@angular/material/dialog';
import { StatusBadge } from '@trishul/shared-ui';
import {
  ApprovalRequest,
  approvalStatusSeverity,
} from './hr-dashboard.mock-data';

/** Read-only sample request. Closing it does not change the row. */
@Component({
  selector: 'trishul-hr-approval-detail-dialog',
  imports: [
    MatDialogTitle,
    MatDialogContent,
    MatDialogActions,
    MatDialogClose,
    MatButton,
    StatusBadge,
  ],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <h2 mat-dialog-title>{{ data.employeeName }}</h2>
    <mat-dialog-content>
      <p class="line"><span>Request</span>{{ data.requestType }}</p>
      <p class="line"><span>Submitted</span>{{ data.submittedLabel }}</p>
      <p class="line"><span>Branch</span>{{ data.branch }}</p>
      <p class="line"><span>Department</span>{{ data.department }}</p>
      <p class="line">
        <span>Status</span>
        <trishul-status-badge [status]="data.status" [severities]="severity" />
      </p>
      <p class="line">
        <span>Priority</span>
        <trishul-status-badge [status]="data.priority" [severities]="severity" />
      </p>
      <p>{{ data.detail }}</p>
      <p class="note">Sample request on this page. Nothing is sent to the server.</p>
    </mat-dialog-content>
    <mat-dialog-actions align="end">
      <button mat-button type="button" mat-dialog-close>Close</button>
    </mat-dialog-actions>
  `,
  styles: `
    .line {
      display: flex;
      gap: 0.75rem;
      align-items: center;
      margin: 0 0 0.5rem;
    }
    .line span {
      min-width: 6.5rem;
      color: var(--mat-sys-on-surface-variant);
    }
    .note {
      margin: 0.75rem 0 0;
      font: var(--mat-sys-body-small);
      color: var(--mat-sys-on-surface-variant);
    }
  `,
})
export class HrApprovalDetailDialog {
  protected readonly data = inject<ApprovalRequest>(MAT_DIALOG_DATA);
  protected readonly severity = approvalStatusSeverity;
}
