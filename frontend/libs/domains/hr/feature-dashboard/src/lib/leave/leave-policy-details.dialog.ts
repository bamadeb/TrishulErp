import { ChangeDetectionStrategy, Component, inject } from '@angular/core';
import { MatButton } from '@angular/material/button';
import { MAT_DIALOG_DATA, MatDialogActions, MatDialogClose, MatDialogContent, MatDialogTitle } from '@angular/material/dialog';
import { LeavePolicyItem } from '@trishul/hr-data-access';

@Component({
  selector: 'trishul-leave-policy-details-dialog',
  imports: [MatButton, MatDialogActions, MatDialogClose, MatDialogContent, MatDialogTitle],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <h2 mat-dialog-title>{{ policy.name }}</h2>
    <mat-dialog-content>
      <p>{{ year() }} · {{ mode() }} · {{ policy.employeeType || 'All employees' }} · {{ policy.departmentName || 'All departments' }} · {{ policy.stateName || policy.branchName || 'Any location' }}</p>
      <p>{{ format(policy.effectiveFrom) }} to {{ policy.effectiveTo ? format(policy.effectiveTo) : 'open' }} · {{ policy.isActive ? 'Active' : 'Inactive' }}</p>
      @for (line of policy.lines; track line.leaveTypeId) {
        <p><strong>{{ line.leaveTypeCode }} {{ line.leaveTypeName }}</strong></p>
        @for (sentence of line.ruleSummary; track sentence) { <p>{{ sentence }}</p> }
      }
    </mat-dialog-content>
    <mat-dialog-actions align="end">
      <button mat-button type="button" mat-dialog-close>Close</button>
    </mat-dialog-actions>
  `,
  styles: `
    p { margin: 0.35rem 0; }
  `,
})
export class LeavePolicyDetailsDialog {
  protected readonly policy = inject<LeavePolicyItem>(MAT_DIALOG_DATA);

  protected year(): string {
    return this.policy.yearBasis === 'CALENDAR' ? 'Calendar' : 'Financial';
  }

  protected mode(): string {
    return this.policy.assignmentMode === 'EXPLICIT' ? 'Explicit' : 'Automatic';
  }

  protected format(value: string): string {
    const [year, month, day] = value.slice(0, 10).split('-');
    const names = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
    return `${day}-${names[Number(month) - 1]}-${year}`;
  }
}
