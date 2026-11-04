import { ChangeDetectionStrategy, Component, computed, inject, signal } from '@angular/core';
import { MatDialog } from '@angular/material/dialog';
import { MatButton } from '@angular/material/button';
import { PageHeader, StatusBadge } from '@trishul/shared-ui';
import { openPayrollRecord } from '../payroll.dialog';
import { PAYROLL_STATUS, inr } from '../payroll.format';
import { StatutoryScheme } from '../payroll.mock';
import { PayrollPrototype } from '../payroll.prototype';

/** PF, ESI, professional tax and TDS for the prototype period. */
@Component({
  selector: 'trishul-statutory-page',
  imports: [MatButton, PageHeader, StatusBadge],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './statutory.page.html',
  styleUrl: '../payroll.shared.scss',
})
export class StatutoryPage {
  private readonly payroll = inject(PayrollPrototype);
  private readonly dialog = inject(MatDialog);
  protected readonly status = PAYROLL_STATUS;
  protected readonly inr = inr;
  protected readonly schemes = this.payroll.statutory;
  protected readonly selected = signal<StatutoryScheme['id']>('pf');
  protected readonly current = computed(
    () => this.schemes.find((scheme) => scheme.id === this.selected()) ?? this.schemes[0],
  );
  protected readonly totals = computed(() => {
    const rows = this.current().rows;
    const employee = rows.reduce((sum, row) => sum + row.employeeShare, 0);
    const employer = rows.reduce((sum, row) => sum + row.employerShare, 0);
    return { employee, employer, total: employee + employer, people: rows.length };
  });

  protected select(id: StatutoryScheme['id']): void {
    this.selected.set(id);
  }

  protected viewReport(scheme: StatutoryScheme): void {
    const totals = scheme.rows.reduce(
      (sum, row) => sum + row.employeeShare + row.employerShare,
      0,
    );
    openPayrollRecord(this.dialog, {
      title: `${scheme.name} compliance report`,
      mode: 'view',
      fields: [
        { key: 'period', label: 'Period', value: scheme.period },
        { key: 'status', label: 'Status', value: scheme.status },
        { key: 'employees', label: 'Employees', value: String(scheme.rows.length) },
        { key: 'total', label: 'Total', value: inr(totals) },
      ],
    }).subscribe();
  }
}
