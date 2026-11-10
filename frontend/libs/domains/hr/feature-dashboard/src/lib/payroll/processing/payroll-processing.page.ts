import { ChangeDetectionStrategy, Component, inject, signal } from '@angular/core';
import { MatButton } from '@angular/material/button';
import { MatDialog } from '@angular/material/dialog';
import { MatFormField, MatPrefix } from '@angular/material/form-field';
import { MatIcon } from '@angular/material/icon';
import { MatInput } from '@angular/material/input';
import { MatSnackBar } from '@angular/material/snack-bar';
import { TadaDecisionHistoryItem, TadaEmployeeItem } from '@trishul/core-api';
import { PayrollRunItem, PayrollRunsApi, TadaApi } from '@trishul/hr-data-access';
import { PageHeader, StatusBadge } from '@trishul/shared-ui';
import { forkJoin, of } from 'rxjs';
import { catchError, map } from 'rxjs/operators';
import { openPayrollRecord } from '../payroll.dialog';
import { PAYROLL_STATUS, inr } from '../payroll.format';
import { payrollPager } from '../payroll.pager';
import { PayrollPagerBar } from '../payroll-pager.bar';

interface SettledTada {
  employeeName: string;
  employeeCode: string;
  designation: string | null;
  trips: number;
  amount: number;
  date: string;
  mode: string;
  batchId: number;
  reference: string;
  remarks: string;
  payroll: boolean;
}

/** Monthly payroll runs calculated from saved salary structures. */
@Component({
  selector: 'trishul-payroll-processing-page',
  imports: [MatButton, MatFormField, MatPrefix, MatIcon, MatInput, PageHeader, StatusBadge, PayrollPagerBar],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './payroll-processing.page.html',
  styleUrl: '../payroll.shared.scss',
  styles: `
    .cards, .table-card + .table-card { margin-top: 1rem; }
    .month-box input {
      height: 2.4rem;
      padding: 0 0.65rem;
      color: inherit;
      background: var(--mat-sys-surface);
      border: 1px solid var(--mat-sys-outline-variant);
      border-radius: var(--mat-sys-corner-small);
    }
  `,
})
export class PayrollProcessingPage {
  private readonly runsApi = inject(PayrollRunsApi);
  private readonly tada = inject(TadaApi);
  private readonly dialog = inject(MatDialog);
  private readonly snackBar = inject(MatSnackBar);
  protected readonly status = PAYROLL_STATUS;
  protected readonly inr = inr;
  protected readonly runs = signal<PayrollRunItem[]>([]);
  protected readonly list = payrollPager(
    this.runs,
    (row) => `${this.monthText(row.periodMonth.slice(0, 7))} ${row.status}`,
  );
  protected readonly month = signal(new Date().toISOString().slice(0, 7));
  protected readonly loading = signal(false);
  protected readonly processing = signal(false);
  protected readonly settled = signal<SettledTada[]>([]);
  protected readonly payrollRows = () => this.settled().filter((row) => row.payroll);
  protected readonly outsideRows = () => this.settled().filter((row) => !row.payroll);
  protected readonly payrollTotal = () => this.payrollRows().reduce((sum, row) => sum + row.amount, 0);
  protected readonly outsideTotal = () => this.outsideRows().reduce((sum, row) => sum + row.amount, 0);

  constructor() {
    this.loadRuns();
    this.loadSettled();
  }

  protected monthText(month = this.month()): string {
    const [year, mon] = month.split('-').map(Number);
    return new Date(year, (mon || 1) - 1, 1).toLocaleString('en-IN', { month: 'short', year: 'numeric' });
  }

  protected onMonth(value: string): void {
    if (!value) return;
    this.month.set(value);
    this.loadSettled();
  }

  protected view(row: PayrollRunItem): void {
    openPayrollRecord(this.dialog, {
      title: this.monthText(row.periodMonth.slice(0, 7)),
      mode: 'view',
      fields: [
        { key: 'month', label: 'Payroll month', value: this.monthText(row.periodMonth.slice(0, 7)) },
        { key: 'employees', label: 'Total employees', value: String(row.employees) },
        { key: 'gross', label: 'Gross salary', value: inr(Number(row.gross), 2) },
        { key: 'deductions', label: 'Total deductions', value: inr(Number(row.deductions), 2) },
        { key: 'net', label: 'Net payable', value: inr(Number(row.netPay), 2) },
        { key: 'status', label: 'Processing status', value: row.status },
      ],
    }).subscribe();
  }

  protected processMonth(): void {
    const month = `${this.month()}-01`;
    this.processing.set(true);
    this.runsApi.process(month).subscribe({
      next: (created) => {
        this.processing.set(false);
        const count = created.reduce((sum, row) => sum + row.employees, 0);
        const label = count === 1 ? 'employee' : 'employees';
        this.snackBar.open(`${this.monthText()} payroll processed for ${count} ${label}.`, 'OK', { duration: 4000 });
        this.loadRuns();
      },
      error: (error: { error?: { detail?: string } }) => {
        this.processing.set(false);
        const detail = error.error?.detail;
        this.snackBar.open(typeof detail === 'string' && detail ? detail : 'Payroll could not be processed.', 'OK', {
          duration: 5000,
        });
      },
    });
  }

  private loadRuns(): void {
    this.runsApi.list().subscribe({
      next: (rows) => this.runs.set(rows),
      error: () => this.snackBar.open('Payroll months could not be loaded.', 'OK', { duration: 4000 }),
    });
  }

  private loadSettled(): void {
    const month = this.month();
    this.loading.set(true);
    this.tada.employees({ month, page: 1, pageSize: 200 }).subscribe({
      next: (report) => {
        const paid = report.items.filter((row) => row.settlementStatus === 'Paid');
        if (!paid.length) {
          this.settled.set([]);
          this.loading.set(false);
          return;
        }
        forkJoin(paid.map((row) => this.tada.history(row.employeeId, month).pipe(
          map((items) => this.toSettled(row, items)),
          catchError(() => of(null)),
        ))).subscribe({
          next: (rows) => {
            if (this.month() !== month) return;
            this.settled.set(rows.filter((row): row is SettledTada => row != null));
            this.loading.set(false);
          },
          error: () => this.loading.set(false),
        });
      },
      error: () => {
        this.settled.set([]);
        this.loading.set(false);
        this.snackBar.open('Settled TA/DA could not be loaded.', 'OK', { duration: 4000 });
      },
    });
  }

  private toSettled(employee: TadaEmployeeItem, items: TadaDecisionHistoryItem[]): SettledTada | null {
    const payment = items.find((item) => item.tripId == null && item.toStatus === 'Paid' && item.remarks);
    if (!payment?.remarks) return null;
    const read = (label: string) => {
      const part = payment.remarks?.split(' | ').find((piece) => piece.startsWith(`${label}: `));
      return part ? part.slice(label.length + 2).trim() : '';
    };
    const amount = Number((read('Paid amount').match(/[0-9][0-9,]*(?:\.\d+)?/)?.[0] ?? '').replaceAll(',', ''));
    if (!Number.isFinite(amount)) return null;
    const mode = read('Payment mode') || 'Payroll';
    return {
      employeeName: employee.employeeName,
      employeeCode: employee.employeeCode,
      designation: employee.designation,
      trips: employee.approvedTrips ?? employee.totalTrips,
      amount,
      date: read('Payment date'),
      mode,
      batchId: payment.id,
      reference: read('Payment reference'),
      remarks: payment.remarks.split(' | ').filter((part) => !part.includes(': ')).join(' '),
      payroll: mode === 'Payroll',
    };
  }
}
