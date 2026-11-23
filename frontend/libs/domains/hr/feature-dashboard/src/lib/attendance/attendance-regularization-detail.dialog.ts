import { ChangeDetectionStrategy, Component, inject } from '@angular/core';
import { MatButton, MatIconButton } from '@angular/material/button';
import { MAT_DIALOG_DATA, MatDialogClose, MatDialogRef } from '@angular/material/dialog';
import { MatIcon } from '@angular/material/icon';
import { RegularizationListRow } from './attendance.models';

export interface RegularizationDetailData {
  row: RegularizationListRow;
}

/** Centered read-only details for one regularization request. */
@Component({
  selector: 'trishul-attendance-regularization-detail-dialog',
  imports: [MatButton, MatDialogClose, MatIcon, MatIconButton],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './attendance-regularization-detail.dialog.html',
  styleUrl: './attendance-regularization-detail.dialog.scss',
})
export class AttendanceRegularizationDetailDialog {
  private readonly dialogRef = inject(
    MatDialogRef<AttendanceRegularizationDetailDialog, 'approve' | 'reject' | null>,
  );
  protected readonly data = inject<RegularizationDetailData>(MAT_DIALOG_DATA);
  protected readonly row = this.data.row;

  protected initials(name: string): string {
    return name
      .split(/\s+/)
      .slice(0, 2)
      .map((part) => part[0]?.toUpperCase() ?? '')
      .join('');
  }

  protected typeClass(type: string): string {
    switch (type) {
      case 'Missed Punch':
        return 'type missed';
      case 'Wrong Attendance':
        return 'type wrong';
      case 'Early Exit':
        return 'type early';
      case 'WFH Correction':
        return 'type wfh';
      case 'Late Arrival':
        return 'type late';
      default:
        return 'type';
    }
  }

  protected statusClass(status: string): string {
    switch (status) {
      case 'Pending':
        return 'status pending';
      case 'Approved':
        return 'status approved';
      case 'Rejected':
        return 'status rejected';
      default:
        return 'status';
    }
  }

  protected approve(): void {
    this.dialogRef.close('approve');
  }

  protected reject(): void {
    this.dialogRef.close('reject');
  }
}
