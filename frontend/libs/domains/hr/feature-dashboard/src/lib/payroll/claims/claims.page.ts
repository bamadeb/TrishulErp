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
import { ClaimRow } from '../payroll.mock';
import { payrollPager } from '../payroll.pager';
import { PayrollPagerBar } from '../payroll-pager.bar';
import { PayrollPrototype } from '../payroll.prototype';

/** Reimbursements and claims. Decisions stay in the prototype. */
@Component({
  selector: 'trishul-claims-page',
  imports: [MatButton, MatFormField, MatPrefix, MatIcon, MatInput, PageHeader, StatusBadge, PayrollPagerBar],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './claims.page.html',
  styleUrl: '../payroll.shared.scss',
})
export class ClaimsPage {
  private readonly payroll = inject(PayrollPrototype);
  private readonly dialog = inject(MatDialog);
  private readonly snackBar = inject(MatSnackBar);
  protected readonly status = PAYROLL_STATUS;
  protected readonly inr = inr;
  protected readonly list = payrollPager(
    this.payroll.claims,
    (row) => `${row.employee} ${row.type} ${row.date} ${row.status}`,
  );

  protected view(row: ClaimRow): void {
    openPayrollRecord(this.dialog, {
      title: `${row.employee} — ${row.type}`,
      mode: 'view',
      fields: [
        { key: 'employee', label: 'Employee', value: row.employee },
        { key: 'type', label: 'Claim type', value: row.type },
        { key: 'date', label: 'Claim date', value: row.date },
        { key: 'amount', label: 'Claim amount', value: inr(row.amount) },
        { key: 'status', label: 'Approval status', value: row.status },
      ],
    }).subscribe();
  }

  protected decide(row: ClaimRow, next: 'Approved' | 'Rejected'): void {
    this.payroll.setClaim(row.id, next);
    this.snackBar.open(`${row.employee} claim ${next.toLowerCase()}`, 'OK', { duration: 4000 });
  }
}
