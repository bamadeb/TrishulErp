import { ChangeDetectionStrategy, Component, computed, inject, signal } from '@angular/core';
import { PageHeader } from '@trishul/shared-ui';
import { inr, netOf } from '../payroll.format';
import { REPORTS, ReportId } from '../payroll.mock';
import { PayrollPrototype } from '../payroll.prototype';

/** Payroll reports assembled from the same prototype rows. */
@Component({
  selector: 'trishul-payroll-reports-page',
  imports: [PageHeader],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './payroll-reports.page.html',
  styleUrl: '../payroll.shared.scss',
})
export class PayrollReportsPage {
  private readonly payroll = inject(PayrollPrototype);
  protected readonly reports = REPORTS;
  protected readonly inr = inr;
  protected readonly netOf = netOf;
  protected readonly selected = signal<ReportId>('register');
  protected readonly salaries = this.payroll.salaries;
  protected readonly departments = computed(() => {
    const buckets = new Map<string, { employees: number; gross: number; deductions: number }>();
    for (const row of this.salaries()) {
      const current = buckets.get(row.department) ?? { employees: 0, gross: 0, deductions: 0 };
      buckets.set(row.department, {
        employees: current.employees + 1,
        gross: current.gross + row.gross,
        deductions: current.deductions + row.deductions,
      });
    }
    return [...buckets.entries()].map(([name, value]) => ({ name, ...value }));
  });
  protected readonly tada = computed(() =>
    this.payroll.tada().map((row) => ({ ...row, payable: this.payroll.tadaPayable(row) })),
  );

  protected select(id: ReportId): void {
    this.selected.set(id);
  }
}
