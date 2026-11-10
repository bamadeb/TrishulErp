import { ChangeDetectionStrategy, Component, DestroyRef, computed, inject, signal } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { MatButton, MatIconButton } from '@angular/material/button';
import { MatCheckbox } from '@angular/material/checkbox';
import { MatDialog } from '@angular/material/dialog';
import { MatFormField, MatLabel, MatPrefix } from '@angular/material/form-field';
import { MatIcon } from '@angular/material/icon';
import { MatInput } from '@angular/material/input';
import { MatMenu, MatMenuItem, MatMenuTrigger } from '@angular/material/menu';
import { MatPaginator, PageEvent } from '@angular/material/paginator';
import { MatProgressBar } from '@angular/material/progress-bar';
import { MatOption, MatSelect } from '@angular/material/select';
import { Subject, debounceTime, distinctUntilChanged } from 'rxjs';
import { HasPermission } from '@trishul/core-auth';
import {
  STATUTORY_MANAGE,
  StatutoryApi,
  StatutoryContribution,
  StatutoryRule,
  StatutoryScheme,
  StatutorySummary,
} from '@trishul/hr-data-access';
import { PageHeader, StatusBadge } from '@trishul/shared-ui';
import { StatutoryRuleDialog } from './statutory-rule.dialog';

type Tab = 'overview' | StatutoryScheme;

interface SchemeQuery {
  search: string;
  departmentId: number | null;
  stateId: number | null;
  page: number;
  pageSize: number;
}

const COLUMNS = [
  { key: 'code', label: 'Employee code', locked: true },
  { key: 'name', label: 'Employee name', locked: false },
  { key: 'department', label: 'Department', locked: false },
  { key: 'location', label: 'State', locked: false },
  { key: 'wages', label: 'Applicable wages', locked: false },
  { key: 'employee', label: 'Employee contribution', locked: false },
  { key: 'employer', label: 'Employer contribution', locked: false },
  { key: 'total', label: 'Total contribution', locked: false },
  { key: 'status', label: 'Calculation status', locked: false },
  { key: 'reason', label: 'Reason', locked: false },
  { key: 'actions', label: 'Actions', locked: true },
] as const;

type ColumnKey = (typeof COLUMNS)[number]['key'];

const EMPTY_SUMMARY: StatutorySummary = {
  month: '',
  financialYear: '',
  eligibleEmployees: 0,
  employeeContribution: null,
  employerContribution: null,
  totalLiability: null,
  configurationStatus: 'Not configured',
  calculationStatus: 'Not calculated',
  filingStatus: 'Not filed',
  schemes: [],
  states: [],
  departments: [],
};

@Component({
  selector: 'trishul-statutory-page',
  imports: [
    HasPermission,
    MatButton,
    MatCheckbox,
    MatFormField,
    MatIcon,
    MatIconButton,
    MatInput,
    MatLabel,
    MatMenu,
    MatMenuItem,
    MatMenuTrigger,
    MatOption,
    MatPaginator,
    MatPrefix,
    MatProgressBar,
    MatSelect,
    PageHeader,
    StatusBadge,
  ],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './statutory.page.html',
  styleUrl: './statutory.page.scss',
})
export class StatutoryPage {
  private readonly api = inject(StatutoryApi);
  private readonly dialog = inject(MatDialog);
  private readonly destroyRef = inject(DestroyRef);
  private readonly searchInput = new Subject<string>();

  protected readonly manage = STATUTORY_MANAGE;
  protected readonly columns = COLUMNS;
  protected readonly schemeTabs = [
    { scheme: 'PF' as const, name: 'PF' },
    { scheme: 'ESI' as const, name: 'ESI' },
    { scheme: 'PT' as const, name: 'Professional Tax' },
    { scheme: 'TDS' as const, name: 'TDS' },
  ];
  protected readonly tones = {
    Configured: 'success',
    Partial: 'warn',
    'Not configured': 'neutral',
    Calculated: 'success',
    'Not calculated': 'neutral',
    'Not applicable': 'neutral',
    'Not filed': 'neutral',
    'Not started': 'neutral',
  } as const;
  protected readonly summary = signal<StatutorySummary>(EMPTY_SUMMARY);
  protected readonly rows = signal<StatutoryContribution[]>([]);
  protected readonly rules = signal<StatutoryRule[]>([]);
  protected readonly total = signal(0);
  protected readonly loading = signal(true);
  protected readonly error = signal('');
  protected readonly tab = signal<Tab>('overview');
  protected readonly year = signal(financialYear(new Date()));
  protected readonly month = signal(monthStart(new Date()));
  protected readonly years = financialYearChoices(new Date());
  protected readonly months = computed(() => monthsIn(this.year()));
  protected readonly visible = signal<Record<ColumnKey, boolean>>(
    Object.fromEntries(COLUMNS.map((column) => [column.key, true])) as Record<ColumnKey, boolean>,
  );
  protected readonly queries = signal<Record<StatutoryScheme, SchemeQuery>>({
    PF: emptyQuery(),
    ESI: emptyQuery(),
    PT: emptyQuery(),
    TDS: emptyQuery(),
  });
  protected readonly schemeCards = computed(() => {
    const saved = new Map(this.summary().schemes.map((item) => [item.scheme, item]));
    return this.schemeTabs.map(
      (item) =>
        saved.get(item.scheme) ?? {
          scheme: item.scheme,
          name: item.name,
          configurationStatus: 'Not configured' as const,
          calculationStatus: 'Not calculated' as const,
          filingStatus: 'Not filed' as const,
        },
    );
  });
  protected readonly workflow = computed(() => {
    const summary = this.summary();
    return [
      { name: 'Configuration', status: summary.configurationStatus },
      { name: 'Payroll calculation', status: summary.calculationStatus },
      { name: 'Statutory verification', status: 'Not started' },
      { name: 'Challan generation', status: 'Not started' },
      { name: 'Payment tracking', status: 'Not started' },
      { name: 'Filing', status: summary.filingStatus },
      { name: 'Reports', status: 'Not started' },
    ];
  });

  constructor() {
    this.searchInput
      .pipe(debounceTime(300), distinctUntilChanged(), takeUntilDestroyed(this.destroyRef))
      .subscribe((search) => this.updateScheme({ search, page: 1 }));
    this.loadSummary();
  }

  protected scheme(): StatutoryScheme {
    const tab = this.tab();
    return tab === 'overview' ? 'PF' : tab;
  }

  protected query(): SchemeQuery {
    const tab = this.tab();
    return tab === 'overview' ? emptyQuery() : this.queries()[tab];
  }

  protected shown(key: ColumnKey): boolean {
    return this.visible()[key];
  }

  protected columnCount(): number {
    return COLUMNS.filter((column) => this.visible()[column.key]).length;
  }

  protected toggleColumn(key: ColumnKey, checked: boolean): void {
    if (COLUMNS.find((column) => column.key === key)?.locked) return;
    this.visible.update((current) => ({ ...current, [key]: checked }));
  }

  protected onYear(year: string): void {
    this.year.set(year);
    const months = monthsIn(year);
    if (!months.some((item) => item.value === this.month())) this.month.set(months[0].value);
    this.loadSummary();
    if (this.tab() !== 'overview') this.loadScheme();
  }

  protected onMonth(month: string): void {
    this.month.set(month);
    this.loadSummary();
    if (this.tab() !== 'overview') this.loadScheme();
  }

  protected selectTab(tab: Tab): void {
    this.tab.set(tab);
    this.loadSummary();
    if (tab !== 'overview') this.loadScheme();
  }

  protected onSearch(value: string): void {
    const tab = this.tab();
    if (tab === 'overview') return;
    this.queries.update((current) => ({ ...current, [tab]: { ...current[tab], search: value } }));
    this.searchInput.next(value);
  }

  protected onDepartment(departmentId: number | null): void {
    this.updateScheme({ departmentId, page: 1 });
  }

  protected onState(stateId: number | null): void {
    this.updateScheme({ stateId, page: 1 });
  }

  protected clearFilters(): void {
    this.updateScheme({ search: '', departmentId: null, stateId: null, page: 1 });
  }

  protected onPage(event: PageEvent): void {
    this.updateScheme({ page: event.pageIndex + 1, pageSize: event.pageSize });
  }

  protected money(value: string | null): string {
    if (value == null || value === '') return 'Not calculated';
    const amount = Number(value);
    if (!Number.isFinite(amount)) return value;
    return amount.toLocaleString('en-IN', { style: 'currency', currency: 'INR', maximumFractionDigits: 2 });
  }

  protected configure(scheme: StatutoryScheme): void {
    this.api.rules(scheme).subscribe({
      next: (rules) => this.openRules(scheme, rules),
      error: () => this.openRules(scheme, []),
    });
  }

  private openRules(scheme: StatutoryScheme, rules: StatutoryRule[]): void {
    const status = this.schemeCards().find((item) => item.scheme === scheme);
    this.dialog
      .open(StatutoryRuleDialog, {
        data: {
          scheme,
          schemeName: status?.name ?? scheme,
          month: this.month(),
          states: this.summary().states,
          rules,
          rule: null,
        },
        width: '42rem',
        maxWidth: '100vw',
        height: '100vh',
        maxHeight: '100vh',
        position: { right: '0', top: '0' },
        panelClass: 'salary-component-drawer',
        autoFocus: 'dialog',
      })
      .afterClosed()
      .subscribe((saved) => {
        if (!saved) return;
        this.loadSummary();
        if (this.tab() === scheme) this.loadScheme();
      });
  }

  protected exportCsv(): void {
    const tab = this.tab();
    if (tab === 'overview') return;
    this.collectExport(tab, 1, []);
  }

  private collectExport(scheme: StatutoryScheme, page: number, collected: StatutoryContribution[]): void {
    const query = this.queries()[scheme];
    this.api.contributions({ ...query, month: this.month(), scheme, page, pageSize: 200 }).subscribe({
      next: (result) => {
        const rows = collected.concat(result.items);
        if (rows.length < result.total) this.collectExport(scheme, page + 1, rows);
        else this.download(scheme, rows);
      },
    });
  }

  private download(scheme: StatutoryScheme, rows: StatutoryContribution[]): void {
    const headers = COLUMNS.filter((column) => column.key !== 'actions' && this.visible()[column.key]).map(
      (column) => column.label,
    );
    const lines = rows.map((row) =>
      [
        this.shown('code') ? row.employeeCode : null,
        this.shown('name') ? row.fullName : null,
        this.shown('department') ? row.department || '' : null,
        this.shown('location') ? row.location || '' : null,
        this.shown('wages') ? this.money(row.applicableWages) : null,
        this.shown('employee') ? this.money(row.employeeContribution) : null,
        this.shown('employer') ? this.money(row.employerContribution) : null,
        this.shown('total') ? this.money(row.totalContribution) : null,
        this.shown('status') ? row.calculationStatus : null,
        this.shown('reason') ? row.reason || '' : null,
      ].filter((value): value is string => value != null),
    );
    const csv = [headers, ...lines].map((line) => line.map(csvCell).join(',')).join('\r\n');
    const blob = new Blob([csv], { type: 'text/csv;charset=utf-8' });
    const link = document.createElement('a');
    link.href = URL.createObjectURL(blob);
    link.download = `statutory-${scheme}-${this.month()}.csv`;
    link.click();
    URL.revokeObjectURL(link.href);
  }

  private updateScheme(change: Partial<SchemeQuery>): void {
    const tab = this.tab();
    if (tab === 'overview') return;
    this.queries.update((current) => ({ ...current, [tab]: { ...current[tab], ...change } }));
    this.loadScheme();
  }

  private loadSummary(): void {
    const scheme = this.tab() === 'PT' ? 'PT' : undefined;
    this.api.summary(this.month(), scheme).subscribe({
      next: (summary) => this.summary.set(summary),
      error: () => this.summary.set({ ...EMPTY_SUMMARY, month: this.month() }),
    });
  }

  private loadScheme(): void {
    const tab = this.tab();
    if (tab === 'overview') return;
    this.loading.set(true);
    this.error.set('');
    const query = this.queries()[tab];
    this.api.contributions({ ...query, month: this.month(), scheme: tab }).subscribe({
      next: (page) => {
        this.rows.set(page.items);
        this.total.set(page.total);
        this.loading.set(false);
      },
      error: () => {
        this.error.set('Statutory contributions could not be loaded.');
        this.loading.set(false);
      },
    });
    this.api.rules(tab).subscribe({
      next: (rules) => this.rules.set(rules),
      error: () => this.rules.set([]),
    });
  }
}

function emptyQuery(): SchemeQuery {
  return { search: '', departmentId: null, stateId: null, page: 1, pageSize: 20 };
}

function monthStart(value: Date): string {
  const month = String(value.getMonth() + 1).padStart(2, '0');
  return `${value.getFullYear()}-${month}-01`;
}

function financialYear(value: Date): string {
  const start = value.getMonth() >= 3 ? value.getFullYear() : value.getFullYear() - 1;
  return `${start}-${String((start + 1) % 100).padStart(2, '0')}`;
}

function financialYearChoices(value: Date): string[] {
  const start = value.getMonth() >= 3 ? value.getFullYear() : value.getFullYear() - 1;
  return [start - 1, start, start + 1].map(
    (year) => `${year}-${String((year + 1) % 100).padStart(2, '0')}`,
  );
}

function monthsIn(yearLabel: string): { value: string; label: string }[] {
  const start = Number(yearLabel.slice(0, 4));
  return Array.from({ length: 12 }, (_, index) => {
    const month = ((index + 3) % 12) + 1;
    const year = index < 9 ? start : start + 1;
    const value = `${year}-${String(month).padStart(2, '0')}-01`;
    const label = new Date(year, month - 1, 1).toLocaleDateString('en-GB', { month: 'short', year: 'numeric' });
    return { value, label };
  });
}

function csvCell(value: string): string {
  return `"${value.replaceAll('"', '""')}"`;
}
