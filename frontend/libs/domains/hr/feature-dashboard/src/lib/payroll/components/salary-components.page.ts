import { ChangeDetectionStrategy, Component, inject } from '@angular/core';
import { MatButton, MatIconButton } from '@angular/material/button';
import { MatDialog } from '@angular/material/dialog';
import { MatFormField, MatPrefix } from '@angular/material/form-field';
import { MatIcon } from '@angular/material/icon';
import { MatInput } from '@angular/material/input';
import { MatMenu, MatMenuItem, MatMenuTrigger } from '@angular/material/menu';
import { MatSnackBar } from '@angular/material/snack-bar';
import { PageHeader, StatusBadge } from '@trishul/shared-ui';
import { openPayrollRecord } from '../payroll.dialog';
import { PAYROLL_STATUS, inr } from '../payroll.format';
import { SalaryComponentRow } from '../payroll.mock';
import { payrollPager } from '../payroll.pager';
import { PayrollPagerBar } from '../payroll-pager.bar';
import { PayrollPrototype } from '../payroll.prototype';

/** Earning and deduction components. */
@Component({
  selector: 'trishul-salary-components-page',
  imports: [
    MatButton, MatIconButton, MatFormField, MatPrefix, MatIcon, MatInput,
    MatMenu, MatMenuItem, MatMenuTrigger, PageHeader, StatusBadge, PayrollPagerBar,
  ],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './salary-components.page.html',
  styleUrl: '../payroll.shared.scss',
})
export class SalaryComponentsPage {
  private readonly payroll = inject(PayrollPrototype);
  private readonly dialog = inject(MatDialog);
  private readonly snackBar = inject(MatSnackBar);
  protected readonly status = PAYROLL_STATUS;
  protected readonly inr = inr;
  protected readonly list = payrollPager(
    this.payroll.components,
    (row) => `${row.name} ${row.type} ${row.calculation} ${row.applicability}`,
  );

  protected add(): void {
    this.edit({
      id: this.payroll.nextComponentId(),
      name: '',
      type: 'Earning',
      calculation: 'Fixed',
      value: 0,
      applicability: '',
      active: true,
    }, 'create');
  }

  protected view(row: SalaryComponentRow): void {
    openPayrollRecord(this.dialog, { title: row.name, mode: 'view', fields: this.fields(row) }).subscribe();
  }

  protected edit(row: SalaryComponentRow, mode: 'edit' | 'create' = 'edit'): void {
    openPayrollRecord(this.dialog, {
      title: mode === 'create' ? 'Add component' : `Edit ${row.name}`,
      mode,
      fields: this.fields(row),
    }).subscribe((values) => {
      if (!values) return;
      this.payroll.saveComponent({
        id: row.id,
        name: values['name']?.trim() ?? '',
        type: values['type'] === 'Deduction' ? 'Deduction' : 'Earning',
        calculation: values['calculation'] === 'Percentage' ? 'Percentage' : 'Fixed',
        value: Number(values['value'] ?? 0),
        applicability: values['applicability']?.trim() ?? '',
        active: values['active'] !== 'Inactive',
      });
      this.snackBar.open('Salary component saved', 'OK', { duration: 4000 });
    });
  }

  protected toggle(row: SalaryComponentRow): void {
    this.payroll.saveComponent({ ...row, active: !row.active });
    this.snackBar.open(`${row.name} ${row.active ? 'deactivated' : 'activated'}`, 'OK', { duration: 4000 });
  }

  private fields(row: SalaryComponentRow) {
    return [
      { key: 'name', label: 'Component name', value: row.name, required: true },
      { key: 'type', label: 'Component type', value: row.type, kind: 'select' as const, options: ['Earning', 'Deduction'] },
      { key: 'calculation', label: 'Calculation type', value: row.calculation, kind: 'select' as const, options: ['Fixed', 'Percentage'] },
      { key: 'value', label: 'Amount / percentage', value: String(row.value), kind: 'number' as const },
      { key: 'applicability', label: 'Applicability', value: row.applicability, required: true },
      { key: 'active', label: 'Status', value: row.active ? 'Active' : 'Inactive', kind: 'select' as const, options: ['Active', 'Inactive'] },
    ];
  }
}
