import { ChangeDetectionStrategy, Component, inject } from '@angular/core';
import { MatButton } from '@angular/material/button';
import { MatDialog } from '@angular/material/dialog';
import { MatFormField, MatPrefix } from '@angular/material/form-field';
import { MatIcon } from '@angular/material/icon';
import { MatInput } from '@angular/material/input';
import { MatSnackBar } from '@angular/material/snack-bar';
import { PageHeader } from '@trishul/shared-ui';
import { openPayrollRecord } from '../payroll.dialog';
import { inr } from '../payroll.format';
import { PayslipRow } from '../payroll.mock';
import { payrollPager } from '../payroll.pager';
import { PayrollPagerBar } from '../payroll-pager.bar';
import { PayrollPrototype } from '../payroll.prototype';

/** Payslip list. Download writes a text file in the browser. */
@Component({
  selector: 'trishul-payslips-page',
  imports: [MatButton, MatFormField, MatPrefix, MatIcon, MatInput, PageHeader, PayrollPagerBar],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './payslips.page.html',
  styleUrl: '../payroll.shared.scss',
})
export class PayslipsPage {
  private readonly payroll = inject(PayrollPrototype);
  private readonly dialog = inject(MatDialog);
  private readonly snackBar = inject(MatSnackBar);
  protected readonly inr = inr;
  protected readonly list = payrollPager(this.payroll.payslips, (row) => `${row.name} ${row.code} ${row.month}`);

  protected view(row: PayslipRow): void {
    openPayrollRecord(this.dialog, {
      title: `${row.name} — ${row.month}`,
      mode: 'view',
      fields: [
        { key: 'name', label: 'Employee name', value: row.name },
        { key: 'code', label: 'Employee code', value: row.code },
        { key: 'month', label: 'Payroll month', value: row.month },
        { key: 'gross', label: 'Gross salary', value: inr(row.gross) },
        { key: 'deductions', label: 'Deductions', value: inr(row.deductions) },
        { key: 'net', label: 'Net salary', value: inr(row.net) },
      ],
    }).subscribe();
  }

  protected download(row: PayslipRow): void {
    const body = [
      'Trishul ERP payslip',
      `Employee: ${row.name}`,
      `Code: ${row.code}`,
      `Month: ${row.month}`,
      `Gross: ${inr(row.gross)}`,
      `Deductions: ${inr(row.deductions)}`,
      `Net: ${inr(row.net)}`,
    ].join('\n');
    const url = URL.createObjectURL(new Blob([body], { type: 'text/plain' }));
    const link = document.createElement('a');
    link.href = url;
    link.download = `payslip-${row.code}.txt`;
    link.click();
    URL.revokeObjectURL(url);
    this.snackBar.open(`Payslip downloaded for ${row.name}`, 'OK', { duration: 4000 });
  }
}
