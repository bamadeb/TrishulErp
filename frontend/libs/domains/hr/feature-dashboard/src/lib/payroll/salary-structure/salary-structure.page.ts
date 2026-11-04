import { ChangeDetectionStrategy, Component, inject } from '@angular/core';
import { MatButton, MatIconButton } from '@angular/material/button';
import { MatDialog } from '@angular/material/dialog';
import { MatFormField, MatPrefix } from '@angular/material/form-field';
import { MatIcon } from '@angular/material/icon';
import { MatInput } from '@angular/material/input';
import { MatMenu, MatMenuItem, MatMenuTrigger } from '@angular/material/menu';
import { MatSnackBar } from '@angular/material/snack-bar';
import { PageHeader } from '@trishul/shared-ui';
import { openPayrollRecord } from '../payroll.dialog';
import { inr, netOf } from '../payroll.format';
import { payrollPager } from '../payroll.pager';
import { PayrollPagerBar } from '../payroll-pager.bar';
import { SalaryRow } from '../payroll.mock';
import { PayrollPrototype } from '../payroll.prototype';

/** Employee salary structures. Values stay in the local prototype. */
@Component({
  selector: 'trishul-salary-structure-page',
  imports: [
    MatButton,
    MatIconButton,
    MatFormField,
    MatPrefix,
    MatIcon,
    MatInput,
    MatMenu,
    MatMenuItem,
    MatMenuTrigger,
    PageHeader,
    PayrollPagerBar,
  ],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './salary-structure.page.html',
  styleUrl: '../payroll.shared.scss',
})
export class SalaryStructurePage {
  private readonly payroll = inject(PayrollPrototype);
  private readonly dialog = inject(MatDialog);
  private readonly snackBar = inject(MatSnackBar);
  protected readonly inr = inr;
  protected readonly netOf = netOf;
  protected readonly list = payrollPager(
    this.payroll.salaries,
    (row) => `${row.employeeCode} ${row.name} ${row.department} ${row.designation}`,
  );

  protected add(): void {
    this.edit({
      id: this.payroll.nextSalaryId(),
      employeeCode: '',
      name: '',
      department: '',
      designation: '',
      ctc: 0,
      gross: 0,
      basic: 0,
      hra: 0,
      allowances: 0,
      deductions: 0,
    }, 'create');
  }

  protected view(row: SalaryRow): void {
    openPayrollRecord(this.dialog, {
      title: row.name,
      mode: 'view',
      fields: this.fields(row),
    }).subscribe();
  }

  protected edit(row: SalaryRow, mode: 'edit' | 'create' = 'edit'): void {
    openPayrollRecord(this.dialog, {
      title: mode === 'create' ? 'Add salary structure' : `Edit ${row.name}`,
      mode,
      fields: this.fields(row),
    }).subscribe((values) => {
      if (!values) return;
      const gross = Number(values['gross'] ?? 0);
      const deductions = Number(values['deductions'] ?? 0);
      this.payroll.saveSalary({
        id: row.id,
        employeeCode: values['employeeCode']?.trim() ?? '',
        name: values['name']?.trim() ?? '',
        department: values['department']?.trim() ?? '',
        designation: values['designation']?.trim() ?? '',
        ctc: Number(values['ctc'] ?? 0),
        gross,
        basic: Number(values['basic'] ?? 0),
        hra: Number(values['hra'] ?? 0),
        allowances: Number(values['allowances'] ?? 0),
        deductions,
      });
      this.snackBar.open('Salary structure saved', 'OK', { duration: 4000 });
    });
  }

  private fields(row: SalaryRow) {
    return [
      { key: 'employeeCode', label: 'Employee ID', value: row.employeeCode, required: true },
      { key: 'name', label: 'Name', value: row.name, required: true },
      { key: 'department', label: 'Department', value: row.department, required: true },
      { key: 'designation', label: 'Designation', value: row.designation, required: true },
      { key: 'ctc', label: 'CTC', value: String(row.ctc), kind: 'number' as const },
      { key: 'gross', label: 'Gross salary', value: String(row.gross), kind: 'number' as const },
      { key: 'basic', label: 'Basic', value: String(row.basic), kind: 'number' as const },
      { key: 'hra', label: 'HRA', value: String(row.hra), kind: 'number' as const },
      { key: 'allowances', label: 'Allowances', value: String(row.allowances), kind: 'number' as const },
      { key: 'deductions', label: 'Deductions', value: String(row.deductions), kind: 'number' as const },
      { key: 'net', label: 'Net salary', value: inr(netOf(row.gross, row.deductions)) },
    ];
  }
}
