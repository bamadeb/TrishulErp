import { ChangeDetectionStrategy, Component, inject, signal } from '@angular/core';
import { MatButton } from '@angular/material/button';
import { MatIcon } from '@angular/material/icon';
import { MatSnackBar } from '@angular/material/snack-bar';
import { PageHeader, StatusBadge } from '@trishul/shared-ui';
import { PAYROLL_STATUS } from '../payroll.format';
import { TADA_COLUMNS, TadaRow, VehicleType } from '../payroll.mock';
import { PayrollPrototype } from '../payroll.prototype';

function cells(line: string): string[] {
  return line.split(',').map((cell) => cell.trim().replace(/^"|"$/g, ''));
}

function amount(value: string): number {
  const parsed = Number(value || 0);
  return Number.isFinite(parsed) ? parsed : Number.NaN;
}

/** CSV template that opens in Excel, with validation, preview and import history. */
@Component({
  selector: 'trishul-tada-import-page',
  imports: [MatButton, MatIcon, PageHeader, StatusBadge],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './tada-import.page.html',
  styleUrl: '../payroll.shared.scss',
})
export class TadaImportPage {
  private readonly payroll = inject(PayrollPrototype);
  private readonly snackBar = inject(MatSnackBar);
  protected readonly status = PAYROLL_STATUS;
  protected readonly history = this.payroll.imports;
  protected readonly fileName = signal('');
  protected readonly errors = signal<string[]>([]);
  protected readonly preview = signal<TadaRow[]>([]);

  protected downloadTemplate(): void {
    const sample = [
      TADA_COLUMNS.join(','),
      'SE-1401,Sample Engineer,Service Engineer,10 Jan 2027,SC-25001,Bengaluru,Kolar,Bike,80,400,100,0,50,0',
      'SE-1402,Sample Lead,Senior Service Engineer,10 Jan 2027,SC-25002,Mysuru,Hassan,Car,160,500,200,0,0,250',
    ].join('\n');
    const url = URL.createObjectURL(new Blob([`\uFEFF${sample}`], { type: 'text/csv' }));
    const link = document.createElement('a');
    link.href = url;
    link.download = 'tada-import-template.csv';
    link.click();
    URL.revokeObjectURL(url);
  }

  protected onFile(event: Event): void {
    const file = (event.target as HTMLInputElement).files?.[0];
    (event.target as HTMLInputElement).value = '';
    this.preview.set([]);
    this.errors.set([]);
    if (!file) return;
    this.fileName.set(file.name);
    const name = file.name.toLowerCase();
    if (!name.endsWith('.csv') && !name.endsWith('.xlsx') && !name.endsWith('.xls')) {
      this.errors.set(['Upload a .csv, .xlsx or .xls file.']);
      return;
    }
    if (!name.endsWith('.csv')) {
      this.errors.set([
        'Excel files are accepted, and this prototype previews the CSV template. Open the template in Excel and save it as CSV.',
      ]);
      return;
    }
    void file.text().then((text) => this.parse(text));
  }

  protected importRows(): void {
    const rows = this.preview();
    if (!rows.length || this.errors().length) return;
    this.payroll.addTada(rows, this.fileName());
    this.preview.set([]);
    this.snackBar.open(`${rows.length} TA/DA rows imported`, 'OK', { duration: 4000 });
  }

  private parse(text: string): void {
    const lines = text.replace(/^\uFEFF/, '').split(/\r?\n/).map((line) => line.trim()).filter(Boolean);
    if (lines.length < 2) {
      this.errors.set(['The file needs a header row and at least one trip.']);
      return;
    }
    const header = cells(lines[0]);
    const missing = TADA_COLUMNS.filter((column) => !header.includes(column));
    if (missing.length) {
      this.errors.set([`Missing columns: ${missing.join(', ')}`]);
      return;
    }
    const errors: string[] = [];
    const rows: TadaRow[] = [];
    let next = this.payroll.nextTadaId();
    lines.slice(1).forEach((line, index) => {
      const value = Object.fromEntries(header.map((column, columnIndex) => [column, cells(line)[columnIndex] ?? '']));
      const rowNumber = index + 2;
      const vehicle = value['Vehicle Type'];
      const km = amount(value['Total KM']);
      const rowErrors: string[] = [];
      if (!value['Employee Code'] || !value['Employee Name']) rowErrors.push('employee code and name are required');
      if (vehicle !== 'Bike' && vehicle !== 'Car') rowErrors.push('vehicle must be Bike or Car');
      if (!Number.isFinite(km) || km < 0) rowErrors.push('Total KM must be a number');
      (['HRA', 'Special Allowance', 'Other Allowance', 'Conveyance', 'Promotion'] as const).forEach((column) => {
        if (!Number.isFinite(amount(value[column]))) rowErrors.push(`${column} must be a number`);
      });
      if (rowErrors.length) {
        errors.push(`Row ${rowNumber}: ${rowErrors.join('; ')}.`);
        return;
      }
      rows.push({
        id: next,
        code: value['Employee Code'],
        name: value['Employee Name'],
        designation: value['Designation'] || 'Service Engineer',
        serviceDate: value['Service Date'],
        ticket: value['Service Call'],
        from: value['Travel From'],
        to: value['Travel To'],
        vehicle: vehicle as VehicleType,
        km,
        hra: amount(value['HRA']),
        specialAllowance: amount(value['Special Allowance']),
        otherAllowance: amount(value['Other Allowance']),
        conveyance: amount(value['Conveyance']),
        promotion: amount(value['Promotion']),
        status: 'Pending',
      });
      next += 1;
    });
    this.errors.set(errors);
    this.preview.set(rows);
  }
}
