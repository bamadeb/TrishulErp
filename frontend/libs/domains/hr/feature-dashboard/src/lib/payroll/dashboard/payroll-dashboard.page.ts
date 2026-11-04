import { ChangeDetectionStrategy, Component, computed, inject } from '@angular/core';
import { MatIcon } from '@angular/material/icon';
import { PageHeader, StatusBadge } from '@trishul/shared-ui';
import { PAYROLL_STATUS, inr } from '../payroll.format';
import { PayrollPrototype } from '../payroll.prototype';

/** Payroll overview. Counts and charts use the local prototype data. */
@Component({
  selector: 'trishul-payroll-dashboard-page',
  imports: [MatIcon, PageHeader, StatusBadge],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './payroll-dashboard.page.html',
  styleUrl: '../payroll.shared.scss',
})
export class PayrollDashboardPage {
  private readonly payroll = inject(PayrollPrototype);
  protected readonly status = PAYROLL_STATUS;
  protected readonly inr = inr;
  protected readonly totals = this.payroll.totals;
  protected readonly activities = this.payroll.activities;
  protected readonly departments = this.payroll.departments;

  protected readonly trend = computed(() => {
    const points = this.payroll.trend;
    const max = Math.max(...points.map((point) => point.net));
    return points.map((point) => ({ ...point, height: Math.round((point.net / max) * 100) }));
  });

  protected readonly distribution = computed(() => {
    const rows = this.departments();
    const max = Math.max(...rows.map((row) => row.gross), 1);
    return rows.map((row) => ({ ...row, width: Math.round((row.gross / max) * 100) }));
  });

  protected readonly cards = computed(() => {
    const totals = this.totals();
    return [
      { label: 'Total Employees', value: String(totals.employees), icon: 'groups' },
      { label: 'Gross Payroll', value: inr(totals.gross), icon: 'payments' },
      { label: 'Total Deductions', value: inr(totals.deductions), icon: 'remove_circle' },
      { label: 'Net Payable', value: inr(totals.net), icon: 'account_balance_wallet' },
      { label: 'Pending Approvals', value: String(totals.pendingApprovals), icon: 'fact_check' },
    ];
  });
}
