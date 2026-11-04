import { ChangeDetectionStrategy, Component, inject } from '@angular/core';
import { MatButton } from '@angular/material/button';
import { MatFormField, MatPrefix } from '@angular/material/form-field';
import { MatIcon } from '@angular/material/icon';
import { MatInput } from '@angular/material/input';
import { MatSnackBar } from '@angular/material/snack-bar';
import { PageHeader, StatusBadge } from '@trishul/shared-ui';
import { PAYROLL_STATUS, inr } from '../payroll.format';
import { payrollPager } from '../payroll.pager';
import { PayrollPagerBar } from '../payroll-pager.bar';
import { PayrollPrototype } from '../payroll.prototype';

/** Approve or reject submitted payroll rows in the prototype. */
@Component({
  selector: 'trishul-payroll-approvals-page',
  imports: [MatButton, MatFormField, MatPrefix, MatIcon, MatInput, PageHeader, StatusBadge, PayrollPagerBar],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './payroll-approvals.page.html',
  styleUrl: '../payroll.shared.scss',
})
export class PayrollApprovalsPage {
  private readonly payroll = inject(PayrollPrototype);
  private readonly snackBar = inject(MatSnackBar);
  protected readonly status = PAYROLL_STATUS;
  protected readonly inr = inr;
  protected readonly list = payrollPager(
    this.payroll.approvals,
    (row) => `${row.employee} ${row.month} ${row.submittedBy} ${row.status}`,
  );

  protected decide(id: number, name: string, next: 'Approved' | 'Rejected'): void {
    this.payroll.setApproval(id, next);
    this.snackBar.open(`${name} ${next.toLowerCase()}`, 'OK', { duration: 4000 });
  }
}
