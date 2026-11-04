import { ChangeDetectionStrategy, Component, inject } from '@angular/core';
import { MatButton } from '@angular/material/button';
import { MatDialog } from '@angular/material/dialog';
import { MatFormField, MatPrefix } from '@angular/material/form-field';
import { MatIcon } from '@angular/material/icon';
import { MatInput } from '@angular/material/input';
import { MatSnackBar } from '@angular/material/snack-bar';
import { PageHeader, StatusBadge } from '@trishul/shared-ui';
import { openPayrollRecord } from '../payroll.dialog';
import { PAYROLL_STATUS, inr } from '../payroll.format';
import { PayrollRun } from '../payroll.mock';
import { payrollPager } from '../payroll.pager';
import { PayrollPagerBar } from '../payroll-pager.bar';
import { PayrollPrototype } from '../payroll.prototype';

/** Monthly payroll runs. Process updates the local status only. */
@Component({
  selector: 'trishul-payroll-processing-page',
  imports: [MatButton, MatFormField, MatPrefix, MatIcon, MatInput, PageHeader, StatusBadge, PayrollPagerBar],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './payroll-processing.page.html',
  styleUrl: '../payroll.shared.scss',
})
export class PayrollProcessingPage {
  private readonly payroll = inject(PayrollPrototype);
  private readonly dialog = inject(MatDialog);
  private readonly snackBar = inject(MatSnackBar);
  protected readonly status = PAYROLL_STATUS;
  protected readonly inr = inr;
  protected readonly list = payrollPager(this.payroll.runs, (row) => `${row.month} ${row.status}`);

  protected view(row: PayrollRun): void {
    openPayrollRecord(this.dialog, {
      title: row.month,
      mode: 'view',
      fields: [
        { key: 'month', label: 'Payroll month', value: row.month },
        { key: 'employees', label: 'Total employees', value: String(row.employees) },
        { key: 'gross', label: 'Gross salary', value: inr(row.gross) },
        { key: 'deductions', label: 'Total deductions', value: inr(row.deductions) },
        { key: 'net', label: 'Net payable', value: inr(row.net) },
        { key: 'status', label: 'Processing status', value: row.status },
      ],
    }).subscribe();
  }

  protected process(row: PayrollRun): void {
    if (row.status !== 'Draft') {
      this.snackBar.open(`${row.month} is already ${row.status.toLowerCase()}`, 'OK', { duration: 4000 });
      return;
    }
    this.payroll.setRunStatus(row.id, 'Processed');
    this.snackBar.open(`${row.month} payroll processed`, 'OK', { duration: 4000 });
  }
}
