import { DatePipe } from '@angular/common';
import { HttpErrorResponse } from '@angular/common/http';
import { ChangeDetectionStrategy, Component, computed, inject, signal } from '@angular/core';
import { MatButton, MatIconButton } from '@angular/material/button';
import { MatButtonToggle, MatButtonToggleChange, MatButtonToggleGroup } from '@angular/material/button-toggle';
import { MatCheckbox } from '@angular/material/checkbox';
import { MatDialog } from '@angular/material/dialog';
import { MatFormField, MatLabel, MatPrefix } from '@angular/material/form-field';
import { MatIcon } from '@angular/material/icon';
import { MatInput } from '@angular/material/input';
import { MatOption, MatSelect } from '@angular/material/select';
import { MatProgressBar } from '@angular/material/progress-bar';
import { MatSnackBar } from '@angular/material/snack-bar';
import { AuthStore } from '@trishul/core-auth';
import {
  BranchListItem,
  CompanyOption,
  DepartmentOption,
  DesignationOption,
  EmployeeListItem,
  TadaEmployeeItem,
  TadaEmployeeSummary,
  TadaRates,
  TadaSummary,
  TadaTripDetail,
  TadaTripItem,
} from '@trishul/core-api';
import { OrganizationApi, TadaApi } from '@trishul/hr-data-access';
import { PageHeader, StatusBadge, StatusSeverity } from '@trishul/shared-ui';
import { concatMap, forkJoin, map, Observable, of, range, switchMap, toArray } from 'rxjs';
import { openPayrollRecord } from '../payroll.dialog';
import { inr } from '../payroll.format';
import { PayrollPagerBar } from '../payroll-pager.bar';

const VEHICLES = ['Own bike', 'Own car', 'Company vehicle', 'Public transport'] as const;
const TRIP_STATUSES = ['In progress', 'Completed', 'Auto closed'] as const;
const APPROVALS = ['Pending', 'Approved', 'Rejected'] as const;
type Tab = 'summary' | 'trips' | 'rates' | 'queue' | 'settlement';
type Vehicle = (typeof VEHICLES)[number];
type Approval = (typeof APPROVALS)[number];

interface Filters {
  month: string;
  companyId: number | null;
  branchId: number | null;
  departmentId: number | null;
  employeeId: number | null;
  designationId: number | null;
  vehicleType: Vehicle | null;
  approval: Approval | null;
  tripStatus: (typeof TRIP_STATUSES)[number] | null;
}

/** Employee summary, trip lines, rates, approval and payroll settlement for TA/DA. */
@Component({
  selector: 'trishul-tada-report-page',
  imports: [
    DatePipe, MatButton, MatIconButton, MatButtonToggleGroup, MatButtonToggle, MatCheckbox,
    MatFormField, MatLabel, MatPrefix, MatIcon, MatInput, MatSelect, MatOption, MatProgressBar,
    PageHeader, StatusBadge, PayrollPagerBar,
  ],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './tada-report.page.html',
  styleUrls: ['../payroll.shared.scss', './tada-report.page.scss'],
})
export class TadaReportPage {
  private readonly api = inject(TadaApi);
  private readonly organization = inject(OrganizationApi);
  private readonly dialog = inject(MatDialog);
  private readonly snackBar = inject(MatSnackBar);
  private readonly auth = inject(AuthStore);
  private searchTimer: ReturnType<typeof setTimeout> | undefined;

  protected readonly canManage = this.auth.hasPermission('core.employee.manage');
  protected readonly vehicles = VEHICLES;
  protected readonly tripStatuses = TRIP_STATUSES;
  protected readonly approvals = APPROVALS;
  protected readonly approvalSeverity: Record<string, StatusSeverity> = {
    Pending: 'warn', Approved: 'success', Rejected: 'danger', Sent: 'info',
  };
  protected readonly tripSeverity: Record<string, StatusSeverity> = {
    'In progress': 'warn', Completed: 'success', 'Auto closed': 'info',
  };

  protected readonly tab = signal<Tab>('summary');
  protected readonly loading = signal(true);
  protected readonly exporting = signal(false);
  protected readonly error = signal('');
  protected readonly employees = signal<TadaEmployeeItem[]>([]);
  protected readonly trips = signal<TadaTripItem[]>([]);
  protected readonly expandedTrips = signal<TadaTripItem[]>([]);
  protected readonly expandedId = signal<number | null>(null);
  protected readonly total = signal(0);
  protected readonly employeeSummary = signal<TadaEmployeeSummary | null>(null);
  protected readonly tripSummary = signal<TadaSummary | null>(null);
  protected readonly rates = signal<TadaRates | null>(null);
  protected readonly selected = signal<number[]>([]);
  protected readonly companies = signal<CompanyOption[]>([]);
  protected readonly branches = signal<BranchListItem[]>([]);
  protected readonly departments = signal<DepartmentOption[]>([]);
  protected readonly designations = signal<DesignationOption[]>([]);
  protected readonly people = signal<EmployeeListItem[]>([]);
  protected readonly draft = signal<Filters>(emptyFilters());
  protected readonly applied = signal<Filters>(emptyFilters());
  protected readonly search = signal('');
  protected readonly sort = signal('employeeCode');
  protected readonly pageIndex = signal(0);
  protected readonly pageSize = signal(20);

  protected readonly branchChoices = computed(() => {
    const companyId = this.draft().companyId;
    return this.branches().filter((branch) => companyId == null || branch.companyId === companyId);
  });
  protected readonly employeeChoices = computed(() => {
    const { companyId, branchId } = this.draft();
    return this.people().filter((employee) => {
      if (branchId != null && employee.branchId !== branchId) return false;
      if (companyId == null) return true;
      const branch = this.branches().find((item) => item.id === employee.branchId);
      return branch == null || branch.companyId === companyId;
    });
  });
  protected readonly pageCount = computed(() => Math.max(1, Math.ceil(this.total() / this.pageSize())));
  protected readonly pages = computed(() => {
    const count = this.pageCount();
    const start = Math.max(0, Math.min(this.pageIndex() - 2, count - 5));
    return Array.from({ length: Math.min(5, count) }, (_, index) => start + index);
  });
  protected readonly rangeLabel = computed(() => {
    const total = this.total();
    if (!total) return '0 of 0';
    const start = this.pageIndex() * this.pageSize() + 1;
    const shown = this.tab() === 'trips' ? this.trips().length : this.employees().length;
    return `${start}–${Math.min(total, start + shown - 1)} of ${total}`;
  });
  protected readonly allSelected = computed(() => {
    const ids = this.employees().map((row) => row.employeeId);
    return ids.length > 0 && ids.every((id) => this.selected().includes(id));
  });
  protected readonly someSelected = computed(() => this.selected().length > 0 && !this.allSelected());
  protected readonly cards = computed(() => {
    const summary = this.employeeSummary();
    const blank = '—';
    return [
      this.card('Employees with Trips', 'groups', summary?.serviceEngineers, summary?.previousServiceEngineers, false),
      this.card('Total Trips', 'route', summary?.trips, summary?.previousTrips, false),
      this.card('Total Travel KM', 'straighten', summary ? Number(summary.travelKm) : null, summary ? Number(summary.previousTravelKm) : null, false, summary ? this.km(summary.travelKm) : blank),
      this.card('Bike Allowance', 'two_wheeler', summary ? Number(summary.bikeAllowance) : null, summary ? Number(summary.previousBikeAllowance) : null, true),
      this.card('Car Allowance', 'directions_car', summary ? Number(summary.carAllowance) : null, summary ? Number(summary.previousCarAllowance) : null, true),
      this.card('Total TA/DA Payable', 'payments', summary ? Number(summary.totalTaPayable) : null, summary ? Number(summary.previousTotalPayable) : null, true),
    ];
  });

  constructor() {
    this.loadOptions();
    this.load();
  }

  protected km(value: string | number | null): string {
    if (value == null || value === '') return '—';
    return Number(value).toLocaleString('en-IN', { maximumFractionDigits: 3 });
  }

  protected money(value: string | null): string {
    if (value == null || value === '') return '—';
    return inr(Number(value), 2);
  }

  protected clock(value: string | null): string {
    if (!value) return '—';
    return new Date(value).toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit' });
  }

  protected rowNumber(index: number): number {
    return this.pageIndex() * this.pageSize() + index + 1;
  }

  protected onTab(event: MatButtonToggleChange): void {
    this.tab.set(event.value as Tab);
    this.pageIndex.set(0);
    this.selected.set([]);
    this.expandedId.set(null);
    this.sort.set(event.value === 'trips' ? '-startAt' : 'employeeCode');
    if (event.value !== 'rates') this.load();
  }

  protected patch(partial: Partial<Filters>): void {
    this.draft.update((current) => ({ ...current, ...partial }));
  }

  protected applyFilters(): void {
    this.applied.set({ ...this.draft() });
    this.pageIndex.set(0);
    this.selected.set([]);
    this.load();
  }

  protected resetFilters(): void {
    const fresh = emptyFilters();
    this.draft.set(fresh);
    this.applied.set(fresh);
    this.search.set('');
    this.pageIndex.set(0);
    this.selected.set([]);
    this.load();
  }

  protected onSearch(value: string): void {
    clearTimeout(this.searchTimer);
    this.searchTimer = setTimeout(() => {
      this.search.set(value.trim());
      this.pageIndex.set(0);
      this.load();
    }, 350);
  }

  protected sortBy(key: string): void {
    this.sort.update((current) => (current === key ? `-${key}` : key));
    this.load();
  }

  protected goTo(index: number): void {
    this.pageIndex.set(index);
    this.selected.set([]);
    this.load();
  }

  protected onPageSize(value: string): void {
    this.pageSize.set(Number(value));
    this.pageIndex.set(0);
    this.load();
  }

  protected togglePage(checked: boolean): void {
    this.selected.set(checked ? this.employees().map((row) => row.employeeId) : []);
  }

  protected toggleRow(id: number, checked: boolean): void {
    this.selected.update((current) => checked ? [...current, id] : current.filter((item) => item !== id));
  }

  protected isSelected(id: number): boolean {
    return this.selected().includes(id);
  }

  protected expand(row: TadaEmployeeItem): void {
    if (this.expandedId() === row.employeeId) {
      this.expandedId.set(null);
      this.expandedTrips.set([]);
      return;
    }
    this.expandedId.set(row.employeeId);
    this.expandedTrips.set([]);
    this.api.employeeTrips(row.employeeId, this.applied().month).subscribe({
      next: (items) => this.expandedTrips.set(items),
      error: () => this.snackBar.open('The trips for this employee could not be loaded.', 'OK', { duration: 4000 }),
    });
  }

  protected approve(): void {
    this.runBulk('Approved');
  }

  protected reject(): void {
    this.runBulk('Rejected');
  }

  protected sendToPayroll(): void {
    const rows = this.selectedRows().filter((row) => row.approvalStatus === 'Approved' && row.settlementStatus === 'Open');
    if (!this.selected().length) {
      this.snackBar.open('Select at least one employee.', 'OK', { duration: 4000 });
      return;
    }
    if (!rows.length) {
      this.snackBar.open('Only approved employees who have not been sent can go to payroll.', 'OK', { duration: 5000 });
      return;
    }
    this.api.settle({ payrollMonth: this.applied().month, employeeIds: rows.map((row) => row.employeeId) }).subscribe({
      next: (result) => this.afterBulk(result.updated, result.skipped.map((skip) => `${skip.employeeCode}: ${skip.reason}`), 'sent to payroll'),
      error: () => this.snackBar.open('Payroll settlement could not be saved.', 'OK', { duration: 4000 }),
    });
  }

  protected saveRates(bike: string, car: string): void {
    const bikePerKm = Number(bike);
    const carPerKm = Number(car);
    if (!Number.isFinite(bikePerKm) || bikePerKm < 0) {
      this.snackBar.open('Enter a bike rate of 0 or more.', 'OK', { duration: 4000 });
      return;
    }
    if (!Number.isFinite(carPerKm) || carPerKm < 5 || carPerKm > 6) {
      this.snackBar.open('The car rate must be between ₹5.00 and ₹6.00 per KM.', 'OK', { duration: 4000 });
      return;
    }
    this.api.saveRates({ bikePerKm: bikePerKm.toFixed(2), carPerKm: carPerKm.toFixed(2) }).subscribe({
      next: () => {
        this.snackBar.open('TA rates saved', 'OK', { duration: 3000 });
        this.load();
      },
      error: () => this.snackBar.open('The TA rates could not be saved.', 'OK', { duration: 4000 }),
    });
  }

  protected viewTrip(row: TadaTripItem): void {
    this.api.trip(row.id).subscribe({
      next: (detail) => this.openDetail(detail),
      error: () => this.snackBar.open('The trip could not be opened.', 'OK', { duration: 4000 }),
    });
  }

  protected downloadTemplate(): void {
    download('tada-employee-summary-template.csv', `\uFEFF${SUMMARY_COLUMNS.join(',')}\r\n`);
  }

  protected exportReport(): void {
    this.exporting.set(true);
    const done = () => this.exporting.set(false);
    if (this.tab() === 'trips') {
      this.allTrips().subscribe({
        next: (rows) => { done(); download(`${this.applied().month}-tada-trips.csv`, tripCsv(rows)); },
        error: () => { done(); this.snackBar.open('The export could not be prepared.', 'OK', { duration: 4000 }); },
      });
      return;
    }
    this.allEmployees().subscribe({
      next: (rows) => { done(); download(`${this.applied().month}-tada-employees.csv`, employeeCsv(rows)); },
      error: () => { done(); this.snackBar.open('The export could not be prepared.', 'OK', { duration: 4000 }); },
    });
  }

  private runBulk(decision: 'Approved' | 'Rejected'): void {
    const rows = this.selectedRows().filter((row) => row.approvalStatus === 'Pending' && row.settlementStatus === 'Open');
    if (!this.selected().length) {
      this.snackBar.open('Select at least one employee.', 'OK', { duration: 4000 });
      return;
    }
    if (!rows.length) {
      this.snackBar.open('Only pending employees can be approved or rejected.', 'OK', { duration: 5000 });
      return;
    }
    this.api.decide({
      payrollMonth: this.applied().month,
      employeeIds: rows.map((row) => row.employeeId),
      decision,
    }).subscribe({
      next: (result) => this.afterBulk(result.updated, result.skipped.map((skip) => `${skip.employeeCode}: ${skip.reason}`), decision.toLowerCase()),
      error: () => this.snackBar.open('The approval could not be saved.', 'OK', { duration: 4000 }),
    });
  }

  private afterBulk(updated: number, skipped: string[], verb: string): void {
    const detail = skipped.length ? ` Skipped ${skipped.length}: ${skipped.slice(0, 3).join('; ')}` : '';
    this.snackBar.open(`${updated} ${verb}.${detail}`, 'OK', { duration: 5000 });
    this.selected.set([]);
    this.load();
  }

  private selectedRows(): TadaEmployeeItem[] {
    const ids = new Set(this.selected());
    return this.employees().filter((row) => ids.has(row.employeeId));
  }

  private load(): void {
    if (this.tab() === 'rates') {
      this.loading.set(false);
      return;
    }
    this.loading.set(true);
    this.error.set('');
    if (this.tab() === 'trips') {
      this.api.report(this.tripParams(this.pageIndex() + 1, this.pageSize())).subscribe({
        next: (report) => {
          this.trips.set(report.items);
          this.total.set(report.total);
          this.tripSummary.set(report.summary);
          this.rates.set(report.rates);
          this.loading.set(false);
        },
        error: (error: HttpErrorResponse) => this.fail(error),
      });
      return;
    }
    this.api.employees(this.employeeParams(this.pageIndex() + 1, this.pageSize())).subscribe({
      next: (report) => {
        this.employees.set(report.items);
        this.total.set(report.total);
        this.employeeSummary.set(report.summary);
        this.rates.set(report.rates);
        this.loading.set(false);
      },
      error: (error: HttpErrorResponse) => this.fail(error),
    });
  }

  private fail(error: HttpErrorResponse): void {
    this.employees.set([]);
    this.trips.set([]);
    this.total.set(0);
    this.loading.set(false);
    const detail = error.error?.detail;
    this.error.set(typeof detail === 'string' && detail ? detail : 'The TA/DA report could not be loaded.');
  }

  private loadOptions(): void {
    forkJoin({
      companies: this.organization.companyOptions(),
      branches: this.organization.listBranches({ page: 1, pageSize: 200, search: '', status: 'active' }),
      departments: this.organization.departmentOptions(),
      designations: this.organization.designationOptions(),
      employees: this.organization.employeeOptions(),
    }).subscribe({
      next: (options) => {
        this.companies.set(options.companies);
        this.branches.set(options.branches.items);
        this.departments.set(options.departments);
        this.designations.set(options.designations);
        this.people.set(options.employees);
      },
      error: () => this.snackBar.open('Filter lists could not be loaded.', 'OK', { duration: 4000 }),
    });
  }

  private employeeParams(page: number, pageSize: number) {
    const filters = this.applied();
    const approval = this.tab() === 'queue' ? 'Pending' : this.tab() === 'settlement' ? 'Approved' : filters.approval;
    return {
      page,
      pageSize,
      sort: this.sort(),
      month: filters.month,
      ...(this.search() ? { search: this.search() } : {}),
      ...(filters.companyId != null ? { companyId: filters.companyId } : {}),
      ...(filters.branchId != null ? { branchId: filters.branchId } : {}),
      ...(filters.departmentId != null ? { departmentId: filters.departmentId } : {}),
      ...(filters.employeeId != null ? { employeeId: filters.employeeId } : {}),
      ...(filters.designationId != null ? { designationId: filters.designationId } : {}),
      ...(filters.vehicleType ? { vehicleType: filters.vehicleType } : {}),
      ...(approval ? { approvalStatus: approval } : {}),
    };
  }

  private tripParams(page: number, pageSize: number) {
    const filters = this.applied();
    return {
      page,
      pageSize,
      sort: this.sort(),
      month: filters.month,
      ...(this.search() ? { search: this.search() } : {}),
      ...(filters.companyId != null ? { companyId: filters.companyId } : {}),
      ...(filters.branchId != null ? { branchId: filters.branchId } : {}),
      ...(filters.departmentId != null ? { departmentId: filters.departmentId } : {}),
      ...(filters.employeeId != null ? { employeeId: filters.employeeId } : {}),
      ...(filters.designationId != null ? { designationId: filters.designationId } : {}),
      ...(filters.vehicleType ? { vehicleType: filters.vehicleType } : {}),
      ...(filters.tripStatus ? { status: filters.tripStatus } : {}),
    };
  }

  private allEmployees() {
    return pageAll((page) => this.api.employees(this.employeeParams(page, 200)).pipe(
      map((report) => ({ items: report.items, total: report.total })),
    ));
  }

  private allTrips() {
    return pageAll((page) => this.api.report(this.tripParams(page, 200)).pipe(
      map((report) => ({ items: report.items, total: report.total })),
    ));
  }

  private card(label: string, icon: string, current: number | null | undefined, previous: number | null | undefined, asMoney: boolean, text?: string) {
    const value = text ?? (current == null ? '—' : asMoney ? inr(current, 2) : String(current));
    return { label, icon, value, delta: percentChange(current ?? null, previous ?? null) };
  }

  private openDetail(detail: TadaTripDetail): void {
    const allowances = detail.allowances.length
      ? detail.allowances.map((line) => ({ key: line.code, label: `${line.name} (monthly)`, value: this.money(line.monthlyAmount) }))
      : [{ key: 'allowances', label: 'Monthly allowances', value: 'None on the current salary structure' }];
    openPayrollRecord(this.dialog, {
      title: `${detail.employeeName} — ${detail.tripDate}`,
      mode: 'view',
      fields: [
        { key: 'code', label: 'Employee code', value: detail.employeeCode },
        { key: 'name', label: 'Employee name', value: detail.employeeName },
        { key: 'designation', label: 'Designation', value: detail.designation ?? '—' },
        { key: 'from', label: 'Travel from', value: detail.travelFrom },
        { key: 'to', label: 'Travel to', value: detail.travelTo },
        { key: 'vehicle', label: 'Vehicle type', value: detail.vehicleType ?? '—' },
        { key: 'gps', label: 'GPS distance (KM)', value: this.km(detail.gpsDistanceKm) },
        { key: 'map', label: 'Map distance (KM)', value: this.km(detail.mapDistanceKm) },
        { key: 'adjusted', label: 'Adjusted distance (KM)', value: this.km(detail.adjustedDistanceKm) },
        { key: 'applicable', label: 'Applicable distance (KM)', value: this.km(detail.applicableDistanceKm) },
        { key: 'rate', label: 'Rate per KM', value: this.money(detail.ratePerKm) },
        { key: 'ta', label: 'TA amount', value: this.money(detail.taAmount) },
        { key: 'status', label: 'Trip status', value: detail.status },
        { key: 'route', label: 'Route', value: detail.routePolyline ? detail.routePolyline.slice(0, 180) : 'No route recorded' },
        ...allowances,
        { key: 'note', label: 'Allowances', value: detail.allowanceNote },
      ],
    });
  }
}

function emptyFilters(): Filters {
  const today = new Date();
  return {
    month: `${today.getFullYear()}-${String(today.getMonth() + 1).padStart(2, '0')}`,
    companyId: null,
    branchId: null,
    departmentId: null,
    employeeId: null,
    designationId: null,
    vehicleType: null,
    approval: null,
    tripStatus: null,
  };
}

function percentChange(current: number | null, previous: number | null): string | null {
  if (current == null || previous == null || previous === 0) return null;
  const pct = Math.round(((current - previous) / previous) * 100);
  return `${pct > 0 ? '+' : ''}${pct}% vs last month`;
}

function pageAll<T>(load: (page: number) => Observable<{ items: T[]; total: number }>) {
  return load(1).pipe(
    switchMap((first) => {
      const pages = Math.min(10, Math.ceil(first.total / 200));
      if (pages <= 1) return of(first.items);
      return range(2, pages - 1).pipe(
        concatMap((page) => load(page)),
        map((report) => report.items),
        toArray(),
        map((rest) => first.items.concat(...rest)),
      );
    }),
  );
}

const SUMMARY_COLUMNS = [
  'Employee Code', 'Employee Name', 'Designation', 'Total Trips', 'Bike KM', 'Car KM', 'Total KM',
  'TA Amount', 'Additional Allowance', 'Total Payable', 'Approval Status', 'Settlement',
];

function employeeCsv(rows: readonly TadaEmployeeItem[]): string {
  const body = rows.map((row) => [
    row.employeeCode, row.employeeName, row.designation ?? '', String(row.totalTrips), row.bikeKm, row.carKm,
    row.totalKm, row.taAmount, row.additionalAllowance, row.totalPayable, row.approvalStatus, row.settlementStatus,
  ]);
  return `\uFEFF${[SUMMARY_COLUMNS, ...body].map((line) => line.map(csvCell).join(',')).join('\r\n')}`;
}

function tripCsv(rows: readonly TadaTripItem[]): string {
  const header = ['Employee Code', 'Employee Name', 'Trip Date', 'Trip Type', 'Start', 'End', 'From', 'To', 'Vehicle', 'GPS KM', 'Map KM', 'Adjusted KM', 'Applicable KM', 'Rate', 'TA', 'Trip Status'];
  const body = rows.map((row) => [
    row.employeeCode, row.employeeName, row.tripDate, row.tripType, row.startAt, row.endAt ?? '', row.travelFrom,
    row.travelTo, row.vehicleType ?? '', row.gpsDistanceKm ?? '', row.mapDistanceKm ?? '', row.adjustedDistanceKm ?? '',
    row.applicableDistanceKm ?? '', row.ratePerKm ?? '', row.taAmount ?? '', row.status,
  ]);
  return `\uFEFF${[header, ...body].map((line) => line.map(csvCell).join(',')).join('\r\n')}`;
}

function csvCell(value: string): string {
  return `"${value.replaceAll('"', '""')}"`;
}

function download(filename: string, contents: string): void {
  const blob = new Blob([contents], { type: 'text/csv;charset=utf-8' });
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = filename;
  link.click();
  URL.revokeObjectURL(url);
}
