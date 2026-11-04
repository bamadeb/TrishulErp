import { MatDialog } from '@angular/material/dialog';
import { Observable } from 'rxjs';
import { PayrollDialogData, PayrollRecordDialog } from './payroll-record.dialog';

export function openPayrollRecord(
  dialog: MatDialog,
  data: PayrollDialogData,
): Observable<Record<string, string> | undefined> {
  return dialog
    .open<PayrollRecordDialog, PayrollDialogData, Record<string, string>>(PayrollRecordDialog, {
      data,
      width: '36rem',
      autoFocus: 'dialog',
    })
    .afterClosed();
}
