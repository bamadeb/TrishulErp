import { DOCUMENT, DatePipe } from '@angular/common';
import { HttpErrorResponse } from '@angular/common/http';
import {
  ChangeDetectionStrategy,
  Component,
  DestroyRef,
  Injectable,
  ElementRef,
  HostListener,
  computed,
  inject,
  input,
  output,
  signal,
  viewChild,
} from '@angular/core';
import { MatButton, MatIconButton } from '@angular/material/button';
import { MatCheckbox } from '@angular/material/checkbox';
import { DateAdapter, MAT_DATE_FORMATS, MAT_NATIVE_DATE_FORMATS, NativeDateAdapter, provideNativeDateAdapter } from '@angular/material/core';
import { MatDatepicker, MatDatepickerInput, MatDatepickerToggle } from '@angular/material/datepicker';
import { MatDialog } from '@angular/material/dialog';
import { MatFormField, MatLabel, MatPrefix, MatSuffix } from '@angular/material/form-field';
import { MatIcon } from '@angular/material/icon';
import { MatInput } from '@angular/material/input';
import { MatMenu, MatMenuItem, MatMenuTrigger } from '@angular/material/menu';
import { MatOption, MatSelect } from '@angular/material/select';
import { MatProgressBar } from '@angular/material/progress-bar';
import { MatSnackBar } from '@angular/material/snack-bar';
import { AuthStore } from '@trishul/core-auth';
import {
  BranchListItem,
  CompanyOption,
  DepartmentOption,
  TadaDecisionHistoryItem,
  TadaEmployeeItem,
  TadaEmployeeSummary,
  TadaRates,
  TadaSummary,
  TadaTripDetail,
  TadaTripDocument,
  TadaTripItem,
} from '@trishul/core-api';
import { DocumentApi, documentIcon } from '@trishul/core-documents';
import { EmployeesApi, OrganizationApi, TadaApi } from '@trishul/hr-data-access';
import { PageHeader, StatusBadge, StatusSeverity } from '@trishul/shared-ui';
import { concatMap, forkJoin, map, Observable, of, range, switchMap, throwError, toArray } from 'rxjs';
import { openPayrollRecord } from '../payroll.dialog';
import { openTadaConfirm } from './tada-confirm.dialog';
import { openTripDecision } from './tada-trip-decision.dialog';
import { openTadaPayment, TadaPaymentResult } from './tada-payment.dialog';
import { inr } from '../payroll.format';
import { PayrollPagerBar } from '../payroll-pager.bar';

const VEHICLES = ['Own bike', 'Own car', 'Company vehicle', 'Public transport'] as const;
const TRIP_STATUSES = ['In progress', 'Completed', 'Auto closed'] as const;
const APPROVALS = ['Pending', 'Approved', 'Rejected'] as const;
type Tab = 'summary' | 'trips' | 'queue' | 'rates';
type EmployeeSortKey =
  | 'employeeName'
  | 'designation'
  | 'totalTrips'
  | 'payableKm'
  | 'bikeTa'
  | 'carTa'
  | 'additionalAllowance'
  | 'totalPayable'
  | 'approvalStatus'
  | 'settlementStatus';
type DrawerTab = 'overview' | 'trips' | 'history';

interface ServiceCallGroup {
  key: string;
  callNo: string | null;
  complaint: string | null;
  trips: TadaTripItem[];
  unlinked: boolean;
}

type DocumentScope =
  | { kind: 'call'; key: string; callId: number | null; callNo: string | null }
  | { kind: 'trip'; tripId: number; callKey: string };

interface OverviewCall {
  key: string;
  callNo: string | null;
  complaint: string | null;
  count: number;
  claimed: string | null;
  approved: string | null;
  unlinked: boolean;
}

interface AuditParts {
  approvedAmount: string | null;
  adjustmentReason: string | null;
  documentDecision: string | null;
  comment: string | null;
}

interface HistoryAudit {
  item: TadaDecisionHistoryItem;
  parts: AuditParts;
}

interface HistoryRow {
  trip: TadaTripItem;
  number: number;
  audits: HistoryAudit[];
  latest: HistoryAudit | null;
  approvedAmount: string | null;
  adjustmentAmount: string | null;
}

interface HistoryCallGroup {
  key: string;
  callNo: string | null;
  trips: HistoryRow[];
  unlinked: boolean;
}

/** A file from GET /core/documents, or a trip receipt the TA/DA trip detail already returns. */
interface SupportingDocument {
  id: number;
  fileName: string;
  category: string | null;
  contentType: string | null;
  uploadedAt: string | null;
  status: string | null;
  via: 'record' | 'trip';
  source: string | null;
}
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
  search: string;
}

interface KpiCard {
  label: string;
  icon: string;
  value: string;
  delta: string | null;
  tone: 'up' | 'down' | 'muted';
}

type TripPreset = 'today' | 'yesterday' | '7' | '15' | 'this' | 'last' | 'month' | 'custom';

const TRIP_PRESETS: readonly { id: Exclude<TripPreset, 'month'>; label: string }[] = [
  { id: 'today', label: 'Today' },
  { id: 'yesterday', label: 'Yesterday' },
  { id: '7', label: 'Last 7 Days' },
  { id: '15', label: 'Last 15 Days' },
  { id: 'this', label: 'This Month' },
  { id: 'last', label: 'Last Month' },
  { id: 'custom', label: 'Custom Range' },
];

const TRIP_DATE_FORMATS = {
  ...MAT_NATIVE_DATE_FORMATS,
  parse: { ...MAT_NATIVE_DATE_FORMATS.parse, dateInput: 'DD-MM-YYYY' },
  display: { ...MAT_NATIVE_DATE_FORMATS.display, dateInput: 'DD-MM-YYYY' },
};

@Injectable()
class TripDateAdapter extends NativeDateAdapter {
  override format(date: Date, displayFormat: object): string {
    return String(displayFormat) === 'DD-MM-YYYY' ? formatDay(date) : super.format(date, displayFormat);
  }

  override parse(value: unknown): Date | null {
    if (typeof value !== 'string') return super.parse(value);
    const match = /^(\d{2})-(\d{2})-(\d{4})$/.exec(value.trim());
    if (!match) return null;
    const day = Number(match[1]);
    const month = Number(match[2]);
    const year = Number(match[3]);
    const date = new Date(year, month - 1, day);
    if (date.getFullYear() !== year || date.getMonth() !== month - 1 || date.getDate() !== day) return null;
    return date;
  }
}

const PAYROLL_MONTH_FORMATS = {
  ...MAT_NATIVE_DATE_FORMATS,
  parse: { ...MAT_NATIVE_DATE_FORMATS.parse, dateInput: 'MMMM, YYYY' },
  display: { ...MAT_NATIVE_DATE_FORMATS.display, dateInput: 'MMMM, YYYY' },
};

@Injectable()
class PayrollMonthAdapter extends NativeDateAdapter {
  override format(date: Date, displayFormat: object): string {
    return String(displayFormat) === 'MMMM, YYYY' ? payrollMonthText(date) : super.format(date, displayFormat);
  }
}

@Component({
  selector: 'trishul-payroll-month',
  imports: [MatFormField, MatLabel, MatInput, MatDatepicker, MatDatepickerInput, MatDatepickerToggle, MatSuffix],
  providers: [
    provideNativeDateAdapter(),
    { provide: DateAdapter, useClass: PayrollMonthAdapter },
    { provide: MAT_DATE_FORMATS, useValue: PAYROLL_MONTH_FORMATS },
  ],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <mat-form-field class="payroll-month" appearance="outline" subscriptSizing="dynamic">
      <mat-label>Payroll month</mat-label>
      <input matInput [matDatepicker]="picker" [value]="date()" (click)="picker.open()" readonly />
      <mat-datepicker-toggle matIconSuffix [for]="picker" />
      <mat-datepicker #picker startView="year" (monthSelected)="choose($event, picker)" />
    </mat-form-field>
  `,
  styles: `
    :host { display: block; }
    .payroll-month { width: 13.5rem; }
  `,
})
class PayrollMonthField {
  readonly month = input.required<string>();
  readonly monthChange = output<string>();
  protected readonly date = computed(() => {
    const [year, mon] = this.month().split('-').map(Number);
    return new Date(year || 2000, (mon || 1) - 1, 1);
  });

  protected choose(value: Date, picker: MatDatepicker<Date>): void {
    picker.close();
    const next = `${value.getFullYear()}-${String(value.getMonth() + 1).padStart(2, '0')}`;
    if (next !== this.month()) this.monthChange.emit(next);
  }
}

function payrollMonthText(date: Date): string {
  return `${date.toLocaleDateString('en-GB', { month: 'long' })}, ${date.getFullYear()}`;
}

/** Employee summary, trip lines, rates, approval and payroll settlement for TA/DA. */
@Component({
  selector: 'trishul-tada-report-page',
  imports: [
    DatePipe, MatButton, MatIconButton, MatCheckbox, MatDatepicker, MatDatepickerInput, MatDatepickerToggle, PayrollMonthField,
    MatMenu, MatMenuItem, MatMenuTrigger, MatFormField, MatLabel, MatPrefix, MatSuffix, MatIcon, MatInput,
    MatSelect, MatOption, MatProgressBar,
    PageHeader, StatusBadge, PayrollPagerBar,
  ],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './tada-report.page.html',
  styleUrls: ['../payroll.shared.scss', './tada-report.page.scss'],
  providers: [
    provideNativeDateAdapter(),
    { provide: DateAdapter, useClass: TripDateAdapter },
    { provide: MAT_DATE_FORMATS, useValue: TRIP_DATE_FORMATS },
  ],
})
export class TadaReportPage {
  private readonly api = inject(TadaApi);
  private readonly documents = inject(DocumentApi);
  private readonly employeesApi = inject(EmployeesApi);
  private readonly organization = inject(OrganizationApi);
  private readonly dialog = inject(MatDialog);
  private readonly snackBar = inject(MatSnackBar);
  private readonly auth = inject(AuthStore);
  private readonly document = inject(DOCUMENT);
  private readonly drawerPanel = viewChild<ElementRef<HTMLElement>>('drawer');

  protected readonly canManage = this.auth.hasPermission('core.employee.manage');
  protected readonly vehicles = VEHICLES;
  protected readonly tripStatuses = TRIP_STATUSES;
  protected readonly approvals = APPROVALS;
  protected readonly pageSizes = [5, 10, 20];
  protected readonly approvalSeverity: Record<string, StatusSeverity> = {
    Pending: 'warn', Approved: 'success', Rejected: 'danger', Sent: 'info', Paid: 'success', Open: 'neutral',
  };
  protected readonly tripSeverity: Record<string, StatusSeverity> = {
    'In progress': 'warn', Completed: 'success', 'Auto closed': 'info',
  };

  protected readonly tab = signal<Tab>('summary');
  protected readonly loading = signal(true);
  protected readonly exporting = signal(false);
  protected readonly acting = signal(false);
  protected readonly error = signal('');
  protected readonly employees = signal<TadaEmployeeItem[]>([]);
  protected readonly trips = signal<TadaTripItem[]>([]);
  protected readonly expandedTrips = signal<TadaTripItem[]>([]);
  protected readonly expandedId = signal<number | null>(null);
  protected readonly total = signal(0);
  protected readonly employeeSummary = signal<TadaEmployeeSummary | null>(null);
  protected readonly tripSummary = signal<TadaSummary | null>(null);
  protected readonly rates = signal<TadaRates | null>(null);
  protected readonly pendingCount = signal<number | null>(null);
  protected readonly selected = signal<number[]>([]);
  protected readonly companies = signal<CompanyOption[]>([]);
  protected readonly branches = signal<BranchListItem[]>([]);
  protected readonly departments = signal<DepartmentOption[]>([]);
  protected readonly draft = signal<Filters>(emptyFilters());
  protected readonly applied = signal<Filters>(emptyFilters());
  protected readonly summaryQuery = signal('');
  protected readonly sort = signal('employeeCode');
  protected readonly employeeSort = signal<{ key: EmployeeSortKey; dir: 'asc' | 'desc' } | null>(null);
  protected readonly sortedEmployees = computed(() => sortEmployees(this.employees(), this.employeeSort(), this.rates()));
  protected readonly pageIndex = signal(0);
  protected readonly pageSize = signal(5);
  protected readonly drawerEmployee = signal<TadaEmployeeItem | null>(null);
  protected readonly drawerTab = signal<DrawerTab>('overview');
  protected readonly drawerLoading = signal(false);
  protected readonly monthLabel = monthLabel;
  protected readonly payrollMonthDate = computed(() => {
    const [year, mon] = this.applied().month.split('-').map(Number);
    return new Date(year, (mon || 1) - 1, 1);
  });
  protected readonly decisionHistory = signal<TadaDecisionHistoryItem[] | null>(null);
  protected readonly drawerProfile = signal<{ department: string | null; location: string | null } | null>(null);
  protected readonly historyQuery = signal('');
  protected readonly historyStatus = signal('All');
  protected readonly historyFrom = signal<Date | null>(null);
  protected readonly historyTo = signal<Date | null>(null);
  protected readonly historyDateError = signal('');
  protected readonly historyLoading = signal(false);
  private readonly historySource = signal<TadaTripItem[] | null>(null);
  private historyRequest = 0;
  private historyTimer: ReturnType<typeof setTimeout> | null = null;
  private tripFilterTimer: ReturnType<typeof setTimeout> | null = null;
  private historyKey = '';
  protected readonly historyPage = signal(0);
  protected readonly historyTripId = signal<number | null>(null);
  protected readonly expandedHistoryCalls = signal<ReadonlySet<string>>(new Set());
  protected readonly historyPageSize = 5;
  protected readonly selectedListTrip = signal<TadaTripItem | null>(null);
  protected readonly selectedTrip = signal<TadaTripDetail | null>(null);
  protected readonly documentScope = signal<DocumentScope | null>(null);
  private readonly shownDocuments = signal<SupportingDocument[]>([]);
  protected readonly tripDocumentsLoading = signal(false);
  protected readonly tripDocumentsError = signal('');
  protected readonly supportingDocuments = computed(() => this.shownDocuments());
  protected readonly documentChoice = signal<'verified' | 'missing' | 'not-applicable'>('not-applicable');
  protected readonly documentReason = signal('');
  protected readonly approveAmount = signal('');
  protected readonly adjustmentReason = signal('');
  protected readonly tripQuery = signal('');
  protected readonly tripMode = signal('All');
  protected readonly tripReview = signal('All');
  protected readonly tripPresets = TRIP_PRESETS;
  protected readonly tripPreset = signal<TripPreset>('month');
  protected readonly draftTripFrom = signal<Date | null>(null);
  protected readonly draftTripTo = signal<Date | null>(null);
  protected readonly tripDateError = signal('');
  private readonly appliedTripQuery = signal('');
  private readonly appliedTripMode = signal('All');
  private readonly appliedTripReview = signal('All');
  private readonly appliedTripFrom = signal<Date | null>(null);
  private readonly appliedTripTo = signal<Date | null>(null);
  private readonly rangeTrips = signal<TadaTripItem[] | null>(null);
  private tripRangeRequest = 0;
  protected readonly collapsedCalls = signal<ReadonlySet<string>>(new Set());
  protected readonly documentReasons = [
    'Employee unable to provide ticket/receipt',
    'Document is unreadable',
    'Document does not match this trip',
  ];
  protected readonly adjustmentReasons = [
    'Approved as per company policy',
    'Fare higher than eligible',
    'Partial distance approved',
  ];
  private reviewTripId: number | null = null;
  private summaryTimer: ReturnType<typeof setTimeout> | null = null;
  private appliedSummary = '';
  private tableRequest = 0;
  private documentTouched = false;
  private documentRequest = 0;

  protected readonly branchChoices = computed(() => {
    const companyId = this.draft().companyId;
    return this.branches().filter((branch) => companyId == null || branch.companyId === companyId);
  });
  protected readonly pageCount = computed(() => Math.max(1, Math.ceil(this.total() / this.pageSize())));
  protected readonly pages = computed(() => {
    const count = this.pageCount();
    const start = Math.max(0, Math.min(this.pageIndex() - 2, count - 5));
    return Array.from({ length: Math.min(5, count) }, (_, index) => start + index);
  });
  protected readonly rangeLabel = computed(() => {
    const total = this.total();
    const noun = this.tab() === 'trips' ? 'trips' : 'employees';
    if (!total) return `Showing 0 of 0 ${noun}`;
    const start = this.pageIndex() * this.pageSize() + 1;
    const shown = this.tab() === 'trips' ? this.trips().length : this.employees().length;
    return `Showing ${start}–${Math.min(total, start + shown - 1)} of ${total} ${noun}`;
  });
  protected readonly allSelected = computed(() => {
    const ids = this.employees().map((row) => row.employeeId);
    return ids.length > 0 && ids.every((id) => this.selected().includes(id));
  });
  protected readonly someSelected = computed(() => this.selected().length > 0 && !this.allSelected());
  protected readonly recentTrips = computed(() =>
    [...this.expandedTrips()].sort((left, right) => right.startAt.localeCompare(left.startAt)).slice(0, 3),
  );
  protected readonly filteredDrawerTrips = computed(() => {
    const query = this.appliedTripQuery().trim().toLowerCase();
    const mode = this.appliedTripMode();
    const review = this.appliedTripReview();
    const from = isoDay(this.appliedTripFrom());
    const to = isoDay(this.appliedTripTo());
    return (this.rangeTrips() ?? this.expandedTrips()).filter((trip) => {
      if (from && trip.tripDate < from) return false;
      if (to && trip.tripDate > to) return false;
      if (mode !== 'All' && trip.vehicleType !== mode) return false;
      if (review !== 'All' && (trip.reviewStatus || 'Pending') !== review) return false;
      if (!query) return true;
      return [trip.callNo, trip.complaintDescription, trip.travelFrom, trip.travelTo].filter((part) => !!part).join(' ').toLowerCase().includes(query);
    });
  });
  protected readonly filteredTripPayable = computed(() =>
    this.filteredDrawerTrips().reduce((sum, trip) => sum + Number(trip.taAmount || 0), 0).toFixed(2),
  );
  protected readonly tripRangeLabel = computed(() => {
    const from = this.appliedTripFrom();
    const to = this.appliedTripTo();
    if (!from || !to) return 'Choose a from and to date.';
    return `${formatDay(from)} – ${formatDay(to)}`;
  });
  protected readonly callGroups = computed((): ServiceCallGroup[] => {
    const ordered = [...this.filteredDrawerTrips()].sort((left, right) => right.startAt.localeCompare(left.startAt) || right.id - left.id);
    if (!ordered.length) return [];
    const buckets = new Map<string, ServiceCallGroup>();
    for (const trip of ordered) {
      const unlinked = trip.callId == null && !trip.callNo;
      const key = unlinked ? 'unlinked' : `call:${trip.callId ?? trip.callNo}`;
      const group = buckets.get(key) ?? {
        key,
        callNo: unlinked ? null : trip.callNo || null,
        complaint: unlinked ? null : trip.complaintDescription || null,
        trips: [],
        unlinked,
      };
      group.trips.push(trip);
      buckets.set(key, group);
    }
    const groups = [...buckets.values()].sort((left, right) => {
      if (left.unlinked !== right.unlinked) return left.unlinked ? 1 : -1;
      return (left.callNo || '').localeCompare(right.callNo || '');
    });
    const narrowed = this.tripPreset() !== 'month' || !!this.appliedTripQuery() || this.appliedTripMode() !== 'All' || this.appliedTripReview() !== 'All';
    if (!narrowed && !groups.some((group) => group.unlinked)) {
      groups.push({ key: 'unlinked', callNo: null, complaint: null, trips: [], unlinked: true });
    }
    return groups;
  });
  protected readonly linkedCallCount = computed(() => this.callGroups().filter((group) => !group.unlinked).length);
  protected readonly historyRows = computed((): HistoryRow[] => buildHistoryRows(this.expandedTrips(), this.decisionHistory() ?? []));
  protected readonly overviewCalls = computed(() => {
    const money = new Map(this.historyRows().map((row) => [row.trip.id, row]));
    const ordered = [...this.expandedTrips()].sort((left, right) => left.startAt.localeCompare(right.startAt) || left.id - right.id);
    const buckets = new Map<string, OverviewCall>();
    for (const trip of ordered) {
      const unlinked = trip.callId == null && !trip.callNo;
      const key = unlinked ? 'unlinked' : `call:${trip.callId ?? trip.callNo}`;
      const group = buckets.get(key) ?? {
        key,
        callNo: unlinked ? null : trip.callNo || null,
        complaint: unlinked ? null : trip.complaintDescription || null,
        count: 0,
        claimed: null,
        approved: null,
        unlinked,
      };
      group.count += 1;
      buckets.set(key, group);
    }
    for (const group of buckets.values()) {
      const trips = ordered.filter((trip) => group.unlinked ? trip.callId == null && !trip.callNo : `call:${trip.callId ?? trip.callNo}` === group.key);
      group.claimed = sumMoney(trips.map((trip) => trip.taAmount));
      group.approved = sumMoney(trips.map((trip) => money.get(trip.id)?.approvedAmount ?? null));
    }
    return [...buckets.values()].sort((left, right) => {
      if (left.unlinked !== right.unlinked) return left.unlinked ? 1 : -1;
      return (left.callNo || '').localeCompare(right.callNo || '');
    });
  });
  protected readonly payrollMonthStart = computed(() => monthBounds(this.applied().month).from);
  protected readonly payrollMonthEnd = computed(() => monthBounds(this.applied().month).to);
  protected readonly filteredHistory = computed(() =>
    buildHistoryRows(this.historySource() ?? this.expandedTrips(), this.decisionHistory() ?? []),
  );
  protected readonly historyGroups = computed((): HistoryCallGroup[] => {
    const buckets = new Map<string, HistoryCallGroup>();
    for (const row of this.filteredHistory()) {
      const key = tripCallKey(row.trip);
      const group = buckets.get(key) ?? {
        key,
        callNo: key === 'unlinked' ? null : row.trip.callNo || null,
        trips: [],
        unlinked: key === 'unlinked',
      };
      group.trips.push(row);
      buckets.set(key, group);
    }
    return [...buckets.values()].sort((left, right) => {
      if (left.unlinked !== right.unlinked) return left.unlinked ? 1 : -1;
      return (left.callNo || '').localeCompare(right.callNo || '');
    });
  });
  protected readonly historyPageCount = computed(() => Math.max(1, Math.ceil(this.historyGroups().length / this.historyPageSize)));
  protected readonly historyPages = computed(() => Array.from({ length: this.historyPageCount() }, (_, index) => index));
  protected readonly historyPageIndex = computed(() => Math.min(this.historyPage(), this.historyPageCount() - 1));
  protected readonly historyGroupSlice = computed(() => {
    const start = this.historyPageIndex() * this.historyPageSize;
    return this.historyGroups().slice(start, start + this.historyPageSize);
  });
  protected readonly selectedHistory = computed(() => this.historyRows().find((row) => row.trip.id === this.historyTripId()) ?? null);
  protected readonly paymentRecords = computed(() => readPayments(this.decisionHistory() ?? []));
  protected readonly drawerFigures = computed(() => {
    let payableKm = 0;
    let ta = 0;
    let approved = 0;
    let pending = 0;
    let rejected = 0;
    for (const trip of this.expandedTrips()) {
      const review = trip.reviewStatus || 'Pending';
      if (review === 'Approved' || review === 'Sent') approved += 1;
      else if (review === 'Rejected') rejected += 1;
      else pending += 1;
      if (trip.payable && (trip.vehicleType === 'Own bike' || trip.vehicleType === 'Own car')) payableKm += Number(trip.applicableDistanceKm || 0);
      ta += this.settledFare(trip);
    }
    return { total: this.expandedTrips().length, payableKm: payableKm.toFixed(2), ta: ta.toFixed(2), approved, pending, rejected };
  });
  protected readonly modeBreakdown = computed(() =>
    this.vehicles.map((mode) => {
      const rows = this.expandedTrips().filter((trip) => trip.vehicleType === mode);
      const payable = rows.filter((trip) => trip.payable);
      const distanceBased = mode === 'Own bike' || mode === 'Own car';
      const km = payable.reduce((sum, trip) => sum + Number(trip.applicableDistanceKm || 0), 0);
      const amount = payable.reduce((sum, trip) => sum + this.settledFare(trip), 0);
      const hasAmount = amount > 0 || payable.some((trip) => trip.taAmount != null);
      return { mode, count: rows.length, km: km.toFixed(2), amount: distanceBased || hasAmount ? amount.toFixed(2) : null, distanceBased };
    }),
  );
  protected readonly cards = computed((): KpiCard[] => {
    const summary = this.employeeSummary();
    const payable = payableKmFromAllowances(summary, this.rates(), false);
    const previousPayable = payableKmFromAllowances(summary, this.rates(), true);
    const pending = this.pendingCount();
    const engineers = summary?.serviceEngineers ?? 0;
    const share = pending != null && engineers > 0
      ? `${Math.round((pending / engineers) * 100)}% of ${engineers} employees`
      : null;
    return [
      this.card('Employees with Trips', 'groups', summary?.serviceEngineers, summary?.previousServiceEngineers, false),
      this.card('Total Trips', 'route', summary?.trips, summary?.previousTrips, false),
      this.card('Total Travel KM', 'straighten', summary ? Number(summary.travelKm) : null, summary ? Number(summary.previousTravelKm) : null, false, summary ? this.km(summary.travelKm) : '—'),
      this.card('Payable KM', 'speed', payable, previousPayable, false, payable == null ? '—' : this.km(payable)),
      this.card('TA Amount', 'payments', summary ? Number(summary.bikeAllowance) + Number(summary.carAllowance) : null, summary ? Number(summary.previousBikeAllowance) + Number(summary.previousCarAllowance) : null, true),
      {
        label: 'Pending Approval',
        icon: 'pending_actions',
        value: pending == null ? '—' : String(pending),
        delta: share,
        tone: 'muted',
      },
    ];
  });

  constructor() {
    this.loadOptions();
    this.load();
    const outsideClick = (event: Event) => this.closeWhenClickedOutside(event);
    this.document.addEventListener('click', outsideClick, true);
    inject(DestroyRef).onDestroy(() => {
      this.document.removeEventListener('click', outsideClick, true);
      if (this.summaryTimer) clearTimeout(this.summaryTimer);
      if (this.historyTimer) clearTimeout(this.historyTimer);
      if (this.tripFilterTimer) clearTimeout(this.tripFilterTimer);
    });
  }

  @HostListener('document:keydown.escape')
  protected closeDrawer(): void {
    this.drawerEmployee.set(null);
    this.decisionHistory.set(null);
    this.drawerProfile.set(null);
    this.historyTripId.set(null);
    this.selectedListTrip.set(null);
    this.selectedTrip.set(null);
    this.clearSupportingDocuments();
  }

  /**
   * Capture phase, so the click still reaches the page control underneath.
   * A summary-row click closes here and then openDrawer() selects that employee before the screen paints.
   * Overlay clicks (menus, selects, dialogs) are not the main page.
   */
  private closeWhenClickedOutside(event: Event): void {
    if (!this.drawerEmployee()) return;
    const target = event.target;
    if (!(target instanceof Node)) return;
    if (this.drawerPanel()?.nativeElement.contains(target)) return;
    if (target instanceof Element && target.closest('.cdk-overlay-container')) return;
    this.drawerEmployee.set(null);
    this.decisionHistory.set(null);
    this.drawerProfile.set(null);
    this.historyTripId.set(null);
    this.selectedListTrip.set(null);
    this.selectedTrip.set(null);
    this.clearSupportingDocuments();
  }

  protected km(value: string | number | null): string {
    if (value == null || value === '') return '—';
    return Number(value).toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  }

  protected money(value: string | number | null): string {
    if (value == null || value === '') return '—';
    return inr(Number(value), 2);
  }

  protected clock(value: string | null): string {
    if (!value) return '—';
    return new Date(value).toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit' });
  }

  protected initial(name: string): string {
    return name.trim().charAt(0).toUpperCase() || '?';
  }

  protected payableKm(row: TadaEmployeeItem): string {
    return this.km(Number(row.bikeKm) + Number(row.carKm));
  }

  protected bikeTa(row: TadaEmployeeItem): string {
    return this.money(lineAmount(row.bikeKm, this.rates()?.bikePerKm ?? null));
  }

  protected carTa(row: TadaEmployeeItem): string {
    return this.money(lineAmount(row.carKm, this.rates()?.carPerKm ?? null));
  }

  protected onTab(next: Tab): void {
    if (this.tab() === next) return;
    this.tab.set(next);
    this.pageIndex.set(0);
    this.selected.set([]);
    this.sort.set(next === 'trips' ? '-startAt' : 'employeeCode');
    if (next !== 'rates') this.loadTable();
  }

  protected patch(partial: Partial<Filters>): void {
    this.draft.update((current) => ({ ...current, ...partial }));
  }

  protected onMonth(value: string): void {
    if (!/^\d{4}-(0[1-9]|1[0-2])$/.test(value) || value === this.applied().month) return;
    this.patch({ month: value });
    this.applied.update((current) => ({ ...current, month: value }));
    this.pageIndex.set(0);
    this.selected.set([]);
    this.loading.set(true);
    const open = this.drawerEmployee();
    if (open) {
      this.expandedId.set(null);
      this.expandedTrips.set([]);
      this.rangeTrips.set(null);
      this.selectedListTrip.set(null);
      this.selectedTrip.set(null);
      this.clearSupportingDocuments();
      this.resetHistoryFilters();
      this.historyTripId.set(null);
      this.decisionHistory.set(null);
    }
    this.load();
    if (open) this.reloadDrawerForMonth(open);
  }

  protected choosePayrollMonth(value: Date, picker: MatDatepicker<Date>): void {
    picker.close();
    this.onMonth(`${value.getFullYear()}-${String(value.getMonth() + 1).padStart(2, '0')}`);
  }

  protected onSummaryInput(value: string): void {
    this.summaryQuery.set(value);
    this.queueSummarySearch();
  }

  protected clearSummarySearch(): void {
    this.summaryQuery.set('');
    this.queueSummarySearch();
  }

  private queueSummarySearch(): void {
    if (this.summaryTimer) clearTimeout(this.summaryTimer);
    const delay = this.summaryQuery().trim() ? 180 : 0;
    this.summaryTimer = setTimeout(() => this.runSummarySearch(), delay);
  }

  protected runSummarySearch(): void {
    const trimmed = this.summaryQuery().trim();
    if (this.summaryQuery() !== trimmed) this.summaryQuery.set(trimmed);
    if (trimmed === this.appliedSummary) return;
    this.appliedSummary = trimmed;
    this.pageIndex.set(0);
    this.selected.set([]);
    this.loadTable();
  }

  protected applyFilters(): void {
    this.applied.set({ ...this.draft(), search: this.draft().search.trim() });
    this.draft.update((current) => ({ ...current, search: current.search.trim() }));
    this.pageIndex.set(0);
    this.selected.set([]);
    this.load();
  }

  protected resetFilters(): void {
    const month = this.applied().month;
    const fresh = { ...emptyFilters(), month };
    this.draft.set(fresh);
    this.applied.set(fresh);
    this.pageIndex.set(0);
    this.selected.set([]);
    this.load();
  }

  protected sortBy(key: string): void {
    this.sort.update((current) => (current === key ? `-${key}` : key));
    this.loadTable();
  }

  protected toggleEmployeeSort(key: EmployeeSortKey, event: Event): void {
    event.preventDefault();
    event.stopPropagation();
    this.employeeSort.update((current) =>
      current?.key === key
        ? { key, dir: current.dir === 'asc' ? 'desc' : 'asc' }
        : { key, dir: 'asc' },
    );
  }

  protected ariaSort(key: EmployeeSortKey): 'ascending' | 'descending' | 'none' {
    const current = this.employeeSort();
    if (current?.key !== key) return 'none';
    return current.dir === 'asc' ? 'ascending' : 'descending';
  }

  protected goTo(index: number): void {
    this.pageIndex.set(index);
    this.selected.set([]);
    this.loadTable();
  }

  protected onPageSize(value: string): void {
    this.pageSize.set(Number(value));
    this.pageIndex.set(0);
    this.loadTable();
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

  protected openDrawer(row: TadaEmployeeItem, tab: DrawerTab = 'overview'): void {
    if (this.drawerEmployee()?.employeeId !== row.employeeId || !this.historyFrom()) {
      this.resetHistoryFilters();
      this.historyTripId.set(null);
      this.drawerProfile.set(null);
    }
    this.drawerEmployee.set(row);
    this.drawerTab.set(tab);
    this.loadHistory(row);
    this.loadProfile(row);
    if (this.expandedId() === row.employeeId && this.expandedTrips().length) {
      this.ensureSelectedTrip(this.expandedTrips());
      return;
    }
    this.collapsedCalls.set(new Set());
    this.expandedId.set(row.employeeId);
    this.expandedTrips.set([]);
    this.selectedListTrip.set(null);
    this.selectedTrip.set(null);
    this.clearSupportingDocuments();
    this.drawerLoading.set(true);
    this.api.employeeTrips(row.employeeId, this.applied().month).subscribe({
      next: (items) => {
        if (this.drawerEmployee()?.employeeId !== row.employeeId) return;
        this.expandedTrips.set(items);
        this.rangeTrips.set(null);
        this.resetTripFilters();
        this.drawerLoading.set(false);
        this.ensureSelectedTrip(items);
      },
      error: () => {
        this.drawerLoading.set(false);
        this.snackBar.open('The trips for this employee could not be loaded.', 'OK', { duration: 4000 });
      },
    });
  }

  protected approve(): void {
    const rows = this.pendingSelection();
    if (!rows) return;
    this.confirmAction(rows, {
      title: 'Approve TA/DA',
      confirmText: 'Confirm Approval',
      requireReason: false,
      onConfirm: () => this.submitDecision(rows, 'Approved'),
    });
  }

  protected reject(): void {
    const rows = this.pendingSelection();
    if (!rows) return;
    this.confirmAction(rows, {
      title: 'Reject TA/DA',
      confirmText: 'Confirm Rejection',
      requireReason: true,
      destructive: true,
      onConfirm: (reason) => this.submitDecision(rows, 'Rejected', reason),
    });
  }

  protected sendToPayroll(): void {
    const rows = this.payrollSelection();
    if (!rows) return;
    this.confirmAction(rows, {
      title: 'Send to payroll',
      confirmText: 'Send to Payroll',
      requireReason: false,
      onConfirm: () => this.settle(rows.map((row) => row.employeeId)),
    });
  }

  protected decideOne(row: TadaEmployeeItem, decision: 'Approved' | 'Rejected'): void {
    if (this.acting()) return;
    if (row.approvalStatus !== 'Pending' || row.settlementStatus !== 'Open') {
      this.snackBar.open('Only pending employees can be approved or rejected.', 'OK', { duration: 5000 });
      return;
    }
    const reject = decision === 'Rejected';
    this.confirmAction([row], {
      title: reject ? 'Reject TA/DA' : 'Approve TA/DA',
      confirmText: reject ? 'Confirm Rejection' : 'Confirm Approval',
      requireReason: reject,
      destructive: reject,
      detailed: true,
      onConfirm: (reason) => this.submitDecision([row], decision, reason),
    });
  }

  protected canSettlePayment(row: TadaEmployeeItem): boolean {
    return !!this.canManage && row.settlementStatus !== 'Paid' && (row.pendingTrips ?? 0) === 0 && (row.approvedTrips ?? 0) > 0;
  }

  protected settledFare(trip: TadaTripItem): number {
    if (trip.taAmount != null) return Number(trip.taAmount) || 0;
    const review = trip.reviewStatus || 'Pending';
    if (trip.vehicleType !== 'Public transport' || (review !== 'Approved' && review !== 'Sent')) return 0;
    const fromHistory = this.historyRows().find((row) => row.trip.id === trip.id)?.approvedAmount;
    const fromAudit = (this.decisionHistory() ?? [])
      .filter((item) => item.tripId === trip.id)
      .map((item) => item.remarks?.match(/Approved amount:\s*₹?\s*([0-9][0-9,]*(?:\.\d+)?)/)?.[1])
      .find((amount) => !!amount);
    const approved = fromHistory || fromAudit;
    return approved ? Number(approved.replaceAll(',', '')) || 0 : 0;
  }

  protected settlementAmount(row: TadaEmployeeItem): number | null {
    if (this.expandedId() === row.employeeId && this.expandedTrips().length) {
      return this.expandedTrips()
        .filter((trip) => trip.reviewStatus === 'Approved' || trip.reviewStatus === 'Sent')
        .reduce((sum, trip) => sum + Number(trip.taAmount || 0), 0);
    }
    if ((row.rejectedTrips ?? 0) === 0) return Number(row.taAmount || 0);
    return null;
  }

  protected settlePayment(row: TadaEmployeeItem): void {
    if (this.acting() || !this.canSettlePayment(row)) return;
    const amount = this.settlementAmount(row);
    openTadaPayment(this.dialog, {
      employeeName: row.employeeName,
      employeeCode: row.employeeCode,
      monthLabel: monthLabel(this.applied().month),
      amountLabel: amount == null ? 'Approved trip TA' : this.money(amount.toFixed(2)),
    }).subscribe((result) => {
      if (result) this.pay(row, result);
    });
  }

  protected settleOne(row: TadaEmployeeItem): void {
    if (this.acting()) return;
    if (row.approvalStatus !== 'Approved' || row.settlementStatus !== 'Open') {
      this.snackBar.open('Only approved employees who have not been sent can go to payroll.', 'OK', { duration: 5000 });
      return;
    }
    this.confirmAction([row], {
      title: 'Send to payroll',
      confirmText: 'Send to Payroll',
      requireReason: false,
      detailed: true,
      onConfirm: () => this.settle([row.employeeId]),
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

  private reloadDrawerForMonth(open: TadaEmployeeItem): void {
    const month = this.applied().month;
    this.drawerLoading.set(true);
    this.api.employees({ page: 1, pageSize: 1, sort: 'employeeCode', month, employeeId: open.employeeId, includeSummary: false }).subscribe({
      next: (report) => {
        if (this.applied().month !== month || this.drawerEmployee()?.employeeId !== open.employeeId) return;
        this.openDrawer(report.items[0] ?? emptyEmployeeMonth(open), this.drawerTab());
      },
      error: () => {
        if (this.applied().month !== month || this.drawerEmployee()?.employeeId !== open.employeeId) return;
        this.drawerLoading.set(false);
        this.snackBar.open('This payroll month could not be loaded.', 'OK', { duration: 4000 });
      },
    });
  }

  protected onHistoryDate(which: 'from' | 'to', value: Date | null): void {
    if (which === 'from') this.historyFrom.set(value);
    else this.historyTo.set(value);
    this.queueHistoryLoad(0);
  }

  protected onHistoryStatus(value: string): void {
    this.historyStatus.set(value);
    this.queueHistoryLoad(0);
  }

  protected onHistorySearch(value: string): void {
    this.historyQuery.set(value);
    this.queueHistoryLoad(300);
  }

  protected resetHistoryFilters(): void {
    if (this.historyTimer) clearTimeout(this.historyTimer);
    this.historyRequest += 1;
    this.historyKey = '';
    const range = monthBounds(this.applied().month);
    this.historyFrom.set(range.from);
    this.historyTo.set(range.to);
    this.historyQuery.set('');
    this.historyStatus.set('All');
    this.historyDateError.set('');
    this.historySource.set(null);
    this.historyLoading.set(false);
    this.historyPage.set(0);
    this.expandedHistoryCalls.set(new Set());
  }

  private queueHistoryLoad(delay: number): void {
    if (this.historyTimer) clearTimeout(this.historyTimer);
    this.historyTimer = setTimeout(() => this.loadHistoryTrips(), delay);
  }

  private loadHistoryTrips(): void {
    const from = this.historyFrom();
    const to = this.historyTo();
    const bounds = monthBounds(this.applied().month);
    if (!from || !to || isoDay(from) > isoDay(to)) {
      this.historyDateError.set('From date must be on or before the to date.');
      return;
    }
    if (isoDay(from) < isoDay(bounds.from) || isoDay(to) > isoDay(bounds.to)) {
      this.historyDateError.set('Choose dates inside the selected payroll month.');
      return;
    }
    this.historyDateError.set('');
    const employee = this.drawerEmployee();
    if (!employee) return;
    const search = this.historyQuery().trim();
    const status = this.historyStatus();
    const fullMonth = isoDay(from) === isoDay(bounds.from) && isoDay(to) === isoDay(bounds.to) && !search && status === 'All';
    if (fullMonth) {
      this.historyRequest += 1;
      this.historyKey = '';
      this.historySource.set(null);
      this.historyLoading.set(false);
      this.historyPage.set(0);
      return;
    }
    const key = `${employee.employeeId}|${this.applied().month}|${isoDay(from)}|${isoDay(to)}|${status}|${search}`;
    if (key === this.historyKey) return;
    this.historyPage.set(0);
    this.historyKey = key;
    const request = ++this.historyRequest;
    this.historyLoading.set(true);
    this.api.filterEmployeeTrips(employee.employeeId, this.applied().month, {
      fromDate: isoDay(from),
      toDate: isoDay(to),
      status,
      search,
    }).subscribe({
      next: (items) => {
        if (request !== this.historyRequest) return;
        this.historySource.set(items);
        this.historyLoading.set(false);
      },
      error: () => {
        if (request !== this.historyRequest) return;
        this.historyLoading.set(false);
        this.historyKey = '';
        this.snackBar.open('The history could not be filtered.', 'OK', { duration: 4000 });
      },
    });
  }

  protected historyCallExpanded(key: string): boolean {
    return this.expandedHistoryCalls().has(key);
  }

  protected toggleHistoryCall(key: string): void {
    this.expandedHistoryCalls.update((current) => {
      const next = new Set(current);
      if (next.has(key)) next.delete(key);
      else next.add(key);
      return next;
    });
  }

  protected showHistory(tripId: number): void {
    this.historyTripId.update((current) => current === tripId ? null : tripId);
  }

  protected historyRange(): string {
    const total = this.historyGroups().length;
    if (!total) return 'Showing 0 of 0';
    const start = this.historyPageIndex() * this.historyPageSize + 1;
    return `Showing ${start}–${Math.min(total, start + this.historyPageSize - 1)} of ${total}`;
  }

  protected rejectionReason(audit: HistoryAudit): string | null {
    return audit.item.toStatus === 'Rejected' ? audit.parts.comment : null;
  }

  protected chooseTripPreset(id: TripPreset): void {
    this.tripPreset.set(id);
    this.tripDateError.set('');
    if (id === 'custom') {
      const range = monthBounds(this.applied().month);
      this.draftTripFrom.set(range.from);
      this.draftTripTo.set(range.to);
      this.appliedTripFrom.set(range.from);
      this.appliedTripTo.set(range.to);
      this.tripRangeRequest += 1;
      this.rangeTrips.set(null);
      this.syncFilteredSelection();
      return;
    }
    const range = id === 'month' ? monthBounds(this.applied().month) : presetRange(id);
    this.draftTripFrom.set(range.from);
    this.draftTripTo.set(range.to);
    this.applyTripFilters();
  }

  protected setTripDate(which: 'from' | 'to', value: Date | null): void {
    this.tripPreset.set('custom');
    this.tripDateError.set('');
    if (which === 'from') this.draftTripFrom.set(value);
    else this.draftTripTo.set(value);
    this.applyTripFilters();
  }

  protected onTripSearch(value: string): void {
    this.tripQuery.set(value);
    this.queueTripFilters(300);
  }

  protected onTripMode(value: string): void {
    this.tripMode.set(value);
    this.applyTripFilters();
  }

  protected onTripReview(value: string): void {
    this.tripReview.set(value);
    this.applyTripFilters();
  }

  private queueTripFilters(delay: number): void {
    if (this.tripFilterTimer) clearTimeout(this.tripFilterTimer);
    this.tripFilterTimer = setTimeout(() => this.applyTripFilters(), delay);
  }

  protected applyTripFilters(): void {
    if (this.tripFilterTimer) clearTimeout(this.tripFilterTimer);
    this.tripFilterTimer = null;
    const from = this.draftTripFrom();
    const to = this.draftTripTo();
    if (!from || !to || isoDay(from) > isoDay(to)) {
      this.tripDateError.set('From date must be on or before the to date.');
      return;
    }
    this.tripDateError.set('');
    this.appliedTripFrom.set(startOfDay(from));
    this.appliedTripTo.set(startOfDay(to));
    this.appliedTripQuery.set(this.tripQuery().trim());
    this.appliedTripMode.set(this.tripMode());
    this.appliedTripReview.set(this.tripReview());
    this.loadTripRange();
  }

  protected resetTripFilters(): void {
    if (this.tripFilterTimer) clearTimeout(this.tripFilterTimer);
    this.tripFilterTimer = null;
    const range = monthBounds(this.applied().month);
    this.tripPreset.set('month');
    this.tripQuery.set('');
    this.tripMode.set('All');
    this.tripReview.set('All');
    this.draftTripFrom.set(range.from);
    this.draftTripTo.set(range.to);
    this.tripDateError.set('');
    this.appliedTripQuery.set('');
    this.appliedTripMode.set('All');
    this.appliedTripReview.set('All');
    this.appliedTripFrom.set(range.from);
    this.appliedTripTo.set(range.to);
    this.tripRangeRequest += 1;
    this.rangeTrips.set(null);
    this.syncFilteredSelection();
  }

  private loadTripRange(): void {
    const employee = this.drawerEmployee();
    const from = this.appliedTripFrom();
    const to = this.appliedTripTo();
    if (!employee || !from || !to) return;
    const months = monthsCovering(from, to);
    if (months.length > 36) {
      this.tripDateError.set('Choose a date range of 36 months or less.');
      return;
    }
    const request = ++this.tripRangeRequest;
    if (months.length === 1 && months[0] === this.applied().month) {
      this.rangeTrips.set(null);
      this.syncFilteredSelection();
      return;
    }
    this.drawerLoading.set(true);
    forkJoin(months.map((month) => this.api.employeeTrips(employee.employeeId, month))).subscribe({
      next: (lists) => {
        if (request !== this.tripRangeRequest || this.drawerEmployee()?.employeeId !== employee.employeeId) return;
        const byId = new Map<number, TadaTripItem>();
        for (const list of lists) for (const trip of list) byId.set(trip.id, trip);
        this.rangeTrips.set([...byId.values()]);
        this.drawerLoading.set(false);
        this.syncFilteredSelection();
      },
      error: () => {
        if (request !== this.tripRangeRequest) return;
        this.drawerLoading.set(false);
        this.snackBar.open('Trips for that date range could not be loaded.', 'OK', { duration: 4000 });
      },
    });
  }

  private syncFilteredSelection(): void {
    const trips = this.filteredDrawerTrips();
    const current = this.selectedListTrip();
    if (current && trips.some((trip) => trip.id === current.id)) return;
    if (!trips.length) {
      this.selectedListTrip.set(null);
      this.selectedTrip.set(null);
      this.clearSupportingDocuments();
      return;
    }
    const next = [...trips].sort((left, right) => left.startAt.localeCompare(right.startAt) || left.id - right.id)[0];
    this.openReview(next);
  }

  protected openCallTrips(key: string, tripId?: number): void {
    this.resetTripFilters();
    const collapsed = new Set(this.expandedTrips().map((trip) => tripCallKey(trip)));
    collapsed.add('unlinked');
    collapsed.delete(key);
    this.collapsedCalls.set(collapsed);
    this.drawerTab.set('trips');
    const trips = this.expandedTrips()
      .filter((trip) => tripCallKey(trip) === key)
      .sort((left, right) => left.startAt.localeCompare(right.startAt) || left.id - right.id);
    const next = (tripId == null ? undefined : trips.find((trip) => trip.id === tripId))
      ?? trips.find((trip) => (trip.reviewStatus || 'Pending') === 'Pending')
      ?? trips[0];
    if (next) this.openReview(next);
    setTimeout(() => this.document.getElementById(`call-group-${key}`)?.scrollIntoView({ block: 'nearest' }));
  }

  protected callDocumentActive(key: string): boolean {
    const scope = this.documentScope();
    if (!scope) return false;
    return scope.kind === 'call' ? scope.key === key : scope.callKey === key;
  }

  protected tripDocumentActive(tripId: number): boolean {
    const scope = this.documentScope();
    return scope?.kind === 'trip' && scope.tripId === tripId;
  }

  protected documentScopeLabel(): string {
    const trip = this.selectedListTrip();
    const scope = this.documentScope();
    if (!trip || scope?.kind !== 'trip' || scope.tripId !== trip.id) return '';
    const when = trip.tripDate;
    return trip.callNo ? `${trip.callNo} · ${when}` : when;
  }

  protected toggleCallGroup(key: string): void {
    this.collapsedCalls.update((current) => {
      const next = new Set(current);
      if (next.has(key)) next.delete(key);
      else next.add(key);
      return next;
    });
  }

  protected callExpanded(key: string): boolean {
    return !this.collapsedCalls().has(key);
  }

  protected tripDistanceLabel(trip: TadaTripItem): string | null {
    if (trip.vehicleType !== 'Own bike' && trip.vehicleType !== 'Own car') return null;
    return `${this.km(trip.applicableDistanceKm)} km`;
  }

  protected openReview(trip: TadaTripItem): void {
    const same = this.selectedListTrip()?.id === trip.id;
    this.selectedListTrip.set(trip);
    if (!same) this.prepareReview(trip, null);
    const request = this.beginDocumentLoad({ kind: 'trip', tripId: trip.id, callKey: tripCallKey(trip) });
    this.api.trip(trip.id).subscribe({
      next: (detail) => {
        if (this.selectedListTrip()?.id !== trip.id || request !== this.documentRequest) return;
        this.selectedTrip.set(detail);
        if (!this.documentTouched) this.prepareReview(trip, detail);
        this.shownDocuments.set(this.tripOnlyDocuments(detail.documents ?? []));
        this.tripDocumentsLoading.set(false);
      },
      error: () => {
        if (this.selectedListTrip()?.id !== trip.id) return;
        this.selectedTrip.set(null);
        if (request !== this.documentRequest) return;
        this.shownDocuments.set([]);
        this.tripDocumentsError.set('The documents for this trip could not be loaded.');
        this.tripDocumentsLoading.set(false);
      },
    });
  }

  protected fareReady(): boolean {
    const trip = this.selectedListTrip();
    if (!trip || trip.vehicleType !== 'Public transport') return true;
    const detail = this.selectedTrip();
    if (!detail || detail.id !== trip.id) return false;
    return (detail.documents ?? []).some((file) => file.source === 'Fare receipt' && (file.verificationStatus === 'Verified' || file.verificationStatus === 'Not required'));
  }

  protected canApproveTrip(): boolean {
    const trip = this.selectedListTrip();
    if (!trip || !trip.payable || (trip.reviewStatus || 'Pending') !== 'Pending') return false;
    const entered = this.approveAmount().trim();
    if (entered !== '') {
      const amount = Number(entered);
      if (!Number.isFinite(amount) || amount < 0) return false;
    } else if (trip.taAmount != null) {
      return false;
    }
    const adjustment = this.adjustmentValue();
    if (adjustment != null && adjustment !== 0 && !this.adjustmentReason()) return false;
    if (trip.vehicleType === 'Public transport') {
      if (this.documentChoice() === 'verified' && this.fareReady()) return true;
      return this.documentChoice() === 'missing' && !!this.documentReason() && entered !== '' && Number.isFinite(Number(entered)) && Number(entered) >= 0;
    }
    if (this.documentChoice() === 'missing') return false;
    return true;
  }

  protected setDocumentChoice(choice: 'verified' | 'missing' | 'not-applicable'): void {
    this.documentTouched = true;
    this.documentChoice.set(choice);
  }

  protected adjustmentValue(): number | null {
    const trip = this.selectedListTrip();
    if (trip?.taAmount == null || this.approveAmount().trim() === '') return null;
    const entered = Number(this.approveAmount());
    if (!Number.isFinite(entered)) return null;
    return Number(trip.taAmount) - entered;
  }

  protected adjustmentText(): string {
    const value = this.adjustmentValue();
    if (value == null) return '—';
    const text = this.money(Math.abs(value).toFixed(2));
    if (value > 0) return `+${text}`;
    if (value < 0) return `−${text}`;
    return text;
  }

  protected priceRows(trip: TadaTripItem): PriceRow[] {
    if (trip.vehicleType === 'Public transport') {
      return [
        { label: 'Claimed fare', value: trip.taAmount ? this.money(trip.taAmount) : 'Not recorded', icon: 'payments', calculated: false },
        { label: 'Applicable fare', value: 'Ticket fare', icon: 'confirmation_number', calculated: false },
        { label: 'Calculated Amount', value: 'Per-kilometre TA is not applied', icon: 'payments', calculated: true },
      ];
    }
    const source = distanceSource(trip);
    const distance = trip.applicableDistanceKm == null ? '—' : `${this.km(trip.applicableDistanceKm)} KM`;
    if (trip.vehicleType === 'Company vehicle') {
      return [
        { label: 'Applicable TA Rate (Company Vehicle)', value: `${this.money('0')} / KM`, icon: 'local_shipping', calculated: false },
        { label: source ?? 'Distance', value: distance, icon: 'straighten', calculated: false },
        { label: 'Calculated Amount', value: this.money('0'), icon: 'payments', calculated: true },
      ];
    }
    const rate = trip.ratePerKm;
    return [
      { label: `Applicable TA Rate (${this.modeLabel(trip.vehicleType)})`, value: rate == null ? '—' : `${this.money(rate)} / KM`, icon: this.modeIcon(trip.vehicleType), calculated: false },
      { label: source ?? 'Distance', value: distance, icon: 'straighten', calculated: false },
      { label: 'Calculated Amount', value: trip.taAmount ? this.money(trip.taAmount) : '—', icon: 'payments', calculated: true },
    ];
  }

  protected priceFormula(trip: TadaTripItem): string {
    if (trip.vehicleType === 'Public transport') return 'Applicable fare is the ticket fare. Own-vehicle per-kilometre rates are not used.';
    if (trip.vehicleType === 'Company vehicle') return 'No per-kilometre TA is applicable.';
    if (trip.applicableDistanceKm == null || trip.ratePerKm == null || trip.taAmount == null) return 'Distance or the configured rate is not available.';
    return `${this.km(trip.applicableDistanceKm)} KM × ${this.money(trip.ratePerKm)} / KM = ${this.money(trip.taAmount)}`;
  }

  protected companyFare(trip: { vehicleType: string | null; taAmount: string | null }): string | null {
    if (trip.vehicleType !== 'Own bike' && trip.vehicleType !== 'Own car') return null;
    return trip.taAmount;
  }

  protected fareDelta(trip: { vehicleType: string | null; taAmount: string | null }): number | null {
    const standard = this.companyFare(trip);
    if (trip.taAmount == null || standard == null) return null;
    const claimed = Number(trip.taAmount);
    const base = Number(standard);
    if (!Number.isFinite(claimed) || !Number.isFinite(base)) return null;
    const delta = claimed - base;
    return delta > 0.004 ? delta : null;
  }

  protected modeLabel(mode: string | null | undefined): string {
    if (mode === 'Own bike') return 'Own Bike';
    if (mode === 'Own car') return 'Own Car';
    if (mode === 'Company vehicle') return 'Company Vehicle';
    if (mode === 'Public transport') return 'Public Transport';
    return mode || 'Trip';
  }

  protected modeIcon(mode: string | null | undefined): string {
    if (mode === 'Own bike') return 'two_wheeler';
    if (mode === 'Own car') return 'directions_car';
    if (mode === 'Company vehicle') return 'local_shipping';
    return 'directions_transit';
  }

  protected reviewLabel(status: string | null | undefined): string {
    if (!status || status === 'Pending') return 'Pending Approval';
    return status;
  }

  protected documentStatus(trip: TadaTripItem): string {
    return trip.vehicleType === 'Public transport' ? 'Receipt required' : 'Not required';
  }

  protected documentIcon(contentType: string | null): string {
    return documentIcon(contentType);
  }

  protected openSupportingDocument(file: SupportingDocument, download: boolean): void {
    const request = file.via === 'record'
      ? this.documents.content(file.id, !download)
      : this.api.document(file.id);
    request.subscribe({
      next: (blob) => {
        const url = URL.createObjectURL(blob);
        if (download) {
          const link = this.document.createElement('a');
          link.href = url;
          link.download = file.fileName || 'document';
          link.click();
        } else {
          this.document.defaultView?.open(url, '_blank', 'noopener');
        }
        setTimeout(() => URL.revokeObjectURL(url), 60_000);
      },
      error: () => this.snackBar.open('The document could not be opened.', 'OK', { duration: 4000 }),
    });
  }

  private approvalBlockReason(trip: TadaTripItem): string {
    if (trip.vehicleType === 'Public transport' && this.documentChoice() === 'missing' && !this.documentReason()) {
      return 'Select why the ticket is not available.';
    }
    if (trip.vehicleType === 'Public transport' && !this.approveAmount().trim()) {
      return 'Enter the fare to approve.';
    }
    return 'Enter the amount to approve.';
  }

  protected submitTripReview(decision: 'Approved' | 'Rejected'): void {
    const trip = this.selectedListTrip();
    const employee = this.drawerEmployee();
    if (!trip || !employee || this.acting()) return;
    if (decision === 'Approved' && !this.canApproveTrip()) {
      this.snackBar.open(this.approvalBlockReason(trip), 'OK', { duration: 4000 });
      return;
    }
    this.acting.set(true);
    openTripDecision(this.dialog, {
      decision,
      lines: [
        { label: 'Employee Name', value: employee.employeeName },
        { label: 'Employee ID', value: employee.employeeCode },
        { label: 'Service Call Number', value: trip.callNo || 'Unavailable' },
        { label: 'Trip Date', value: this.tripDay(trip.tripDate) },
        ...(decision === 'Approved' ? [{ label: 'Approved Amount', value: this.money(this.approveAmount().trim() || null) }] : []),
      ],
      submit: (remarks) => {
        const note = this.reviewParts(remarks);
        if (note.length > 500) {
          return throwError(() => new HttpErrorResponse({ error: { detail: 'The remarks are longer than 500 characters.' } }));
        }
        return this.api.decideTrip(trip.id, decision, note).pipe(
          map((detail) => {
            this.snackBar.open(decision === 'Rejected' ? 'Trip rejected.' : 'Trip approved.', 'OK', { duration: 3000 });
            this.load();
            const open = this.drawerEmployee();
            if (open) this.reloadDrawerForMonth(open);
            return detail;
          }),
        );
      },
    }).subscribe(() => this.acting.set(false));
  }

  private tripDay(iso: string): string {
    const [year, month, day] = iso.split('-').map(Number);
    if (!year || !month || !day) return iso;
    return new Date(year, month - 1, day).toLocaleDateString('en-GB', { day: '2-digit', month: 'short', year: 'numeric' });
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

  private pendingSelection(): TadaEmployeeItem[] | null {
    if (this.acting()) return null;
    if (!this.selected().length) {
      this.snackBar.open('Select at least one employee.', 'OK', { duration: 4000 });
      return null;
    }
    const rows = this.selectedRows().filter((row) => row.approvalStatus === 'Pending' && row.settlementStatus === 'Open');
    if (!rows.length) {
      this.snackBar.open('Only pending employees can be approved or rejected.', 'OK', { duration: 5000 });
      return null;
    }
    return rows;
  }

  private payrollSelection(): TadaEmployeeItem[] | null {
    if (this.acting()) return null;
    if (!this.selected().length) {
      this.snackBar.open('Select at least one employee.', 'OK', { duration: 4000 });
      return null;
    }
    const rows = this.selectedRows().filter((row) => row.approvalStatus === 'Approved' && row.settlementStatus === 'Open');
    if (!rows.length) {
      this.snackBar.open('Only approved employees who have not been sent can go to payroll.', 'OK', { duration: 5000 });
      return null;
    }
    return rows;
  }

  private confirmAction(
    rows: readonly TadaEmployeeItem[],
    options: {
      title: string;
      confirmText: string;
      requireReason: boolean;
      destructive?: boolean;
      detailed?: boolean;
      onConfirm: (reason: string) => void;
    },
  ): void {
    const one = options.detailed && rows.length === 1 ? rows[0] : null;
    const payable = rows.reduce((sum, row) => sum + Number(row.totalPayable), 0);
    openTadaConfirm(this.dialog, {
      title: options.title,
      confirmText: options.confirmText,
      comments: options.requireReason ? 'rejection' : 'none',
      destructive: options.destructive,
      lines: one
        ? [
            { label: 'Employee', value: one.employeeName },
            { label: 'Employee code', value: one.employeeCode },
            { label: 'Payroll month', value: monthLabel(this.applied().month) },
            { label: 'Total trips', value: String(one.totalTrips) },
            { label: 'Total payable', value: this.money(one.totalPayable) },
          ]
        : [
            { label: 'Employees', value: String(rows.length) },
            { label: 'Total payable', value: this.money(payable) },
            { label: 'Payroll month', value: monthLabel(this.applied().month) },
          ],
    }).subscribe((result) => {
      if (!result || this.acting()) return;
      options.onConfirm(result.reason);
    });
  }

  private submitDecision(rows: readonly TadaEmployeeItem[], decision: 'Approved' | 'Rejected', reason = ''): void {
    if (this.acting()) return;
    this.acting.set(true);
    this.api.decide({
      payrollMonth: this.applied().month,
      employeeIds: rows.map((row) => row.employeeId),
      decision,
      ...(decision === 'Rejected' ? { remarks: reason } : {}),
    }).subscribe({
      next: (result) => this.afterBulk(
        result.updated,
        result.skipped.map((skip) => `${skip.employeeCode}: ${skip.reason}`),
        decision.toLowerCase(),
      ),
      error: () => {
        this.acting.set(false);
        this.snackBar.open(
          decision === 'Rejected' ? 'The rejection could not be saved.' : 'The approval could not be saved.',
          'OK',
          { duration: 4000 },
        );
      },
    });
  }

  private pay(row: TadaEmployeeItem, payment: TadaPaymentResult): void {
    if (this.acting()) return;
    this.acting.set(true);
    this.api.settle({
      payrollMonth: this.applied().month,
      employeeIds: [row.employeeId],
      paymentDate: payment.paymentDate,
      paymentMode: payment.paymentMode,
      paymentReference: payment.paymentReference || null,
      remarks: payment.remarks || null,
    }).subscribe({
      next: (result) => {
        this.afterBulk(result.updated, result.skipped.map((skip) => `${skip.employeeCode}: ${skip.reason}`), 'settled');
        if (result.updated && this.drawerEmployee()?.employeeId === row.employeeId) {
          this.expandedTrips.set([]);
          this.decisionHistory.set(null);
          const open = this.drawerEmployee();
          if (open) this.openDrawer(open, this.drawerTab());
        }
      },
      error: () => {
        this.acting.set(false);
        this.snackBar.open('The payment could not be saved.', 'OK', { duration: 4000 });
      },
    });
  }

  private settle(employeeIds: number[]): void {
    if (this.acting()) return;
    this.acting.set(true);
    this.api.settle({ payrollMonth: this.applied().month, employeeIds }).subscribe({
      next: (result) => this.afterBulk(result.updated, result.skipped.map((skip) => `${skip.employeeCode}: ${skip.reason}`), 'sent to payroll'),
      error: () => {
        this.acting.set(false);
        this.snackBar.open('Payroll settlement could not be saved.', 'OK', { duration: 4000 });
      },
    });
  }

  private afterBulk(updated: number, skipped: string[], verb: string): void {
    this.acting.set(false);
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
    this.loadKpis();
    this.loadTable();
  }

  private loadTable(): void {
    if (this.tab() === 'rates') {
      this.loading.set(false);
      return;
    }
    this.loading.set(true);
    this.error.set('');
    const request = ++this.tableRequest;
    if (this.tab() === 'trips') {
      this.api.report({ ...this.tripParams(this.pageIndex() + 1, this.pageSize()), includeSummary: false }).subscribe({
        next: (report) => {
          if (request !== this.tableRequest) return;
          this.trips.set(report.items);
          this.total.set(report.total);
          this.tripSummary.set(report.summary);
          this.rates.set(report.rates);
          this.loading.set(false);
        },
        error: (error: HttpErrorResponse) => {
          if (request !== this.tableRequest) return;
          this.fail(error);
        },
      });
      return;
    }
    this.api.employees({ ...this.employeeParams(this.pageIndex() + 1, this.pageSize()), includeSummary: false }).subscribe({
      next: (report) => {
        if (request !== this.tableRequest) return;
        this.employees.set(report.items);
        this.total.set(report.total);
        this.rates.set(report.rates);
        this.loading.set(false);
        this.refreshDrawer(report.items);
      },
      error: (error: HttpErrorResponse) => {
        if (request !== this.tableRequest) return;
        this.fail(error);
      },
    });
  }

  private loadKpis(): void {
    const approval = this.applied().approval;
    this.api.employees(this.employeeParams(1, 1, { ignoreTab: true })).subscribe({
      next: (report) => {
        this.employeeSummary.set(report.summary);
        this.rates.set(report.rates);
        if (approval === 'Pending') this.pendingCount.set(report.summary.serviceEngineers);
        else if (approval === 'Approved' || approval === 'Rejected') this.pendingCount.set(0);
        else this.loadPendingCount();
      },
      error: () => {
        this.employeeSummary.set(null);
        this.pendingCount.set(null);
      },
    });
  }

  private loadPendingCount(): void {
    this.api.employees(this.employeeParams(1, 1, { ignoreTab: true, approval: 'Pending' })).subscribe({
      next: (report) => this.pendingCount.set(report.summary.serviceEngineers),
      error: () => this.pendingCount.set(null),
    });
  }

  private prepareReview(trip: TadaTripItem, detail: TadaTripDetail | null): void {
    if (this.reviewTripId !== trip.id) {
      this.reviewTripId = trip.id;
      this.documentTouched = false;
      this.documentReason.set('');
      this.adjustmentReason.set('');
      this.approveAmount.set(trip.taAmount == null ? '' : Number(trip.taAmount).toFixed(2));
    }
    const ownVehicle = trip.vehicleType === 'Own bike' || trip.vehicleType === 'Own car' || trip.vehicleType === 'Company vehicle';
    if (ownVehicle) {
      this.documentChoice.set('not-applicable');
      return;
    }
    const verified = (detail?.documents ?? []).some((file) => file.source === 'Fare receipt' && (file.verificationStatus === 'Verified' || file.verificationStatus === 'Not required'));
    this.documentChoice.set(verified ? 'verified' : 'missing');
  }

  private reviewParts(remarks: string): string {
    const parts: string[] = [];
    const amount = this.approveAmount().trim();
    if (amount) parts.push(`Approved amount: ₹${amount}`);
    if (this.adjustmentReason()) parts.push(`Adjustment reason: ${this.adjustmentReason()}`);
    if (this.documentChoice() === 'missing' && this.documentReason()) parts.push(`Document: ${this.documentReason()}`);
    if (remarks.trim()) parts.push(remarks.trim());
    return parts.join('. ');
  }

  private beginDocumentLoad(scope: DocumentScope): number {
    const request = ++this.documentRequest;
    this.documentScope.set(scope);
    this.shownDocuments.set([]);
    this.tripDocumentsError.set('');
    this.tripDocumentsLoading.set(true);
    return request;
  }

  private toTripDocument(file: TadaTripDocument): SupportingDocument {
    return {
      id: file.id,
      fileName: file.fileName,
      category: file.category || file.source,
      contentType: file.contentType ?? null,
      uploadedAt: null,
      status: file.verificationStatus ?? null,
      via: 'trip',
      source: file.source,
    };
  }

  private tripOnlyDocuments(files: readonly TadaTripDocument[]): SupportingDocument[] {
    return files.filter((file) => file.source !== 'Service call').map((file) => this.toTripDocument(file));
  }

  private clearSupportingDocuments(): void {
    this.documentRequest += 1;
    this.documentScope.set(null);
    this.shownDocuments.set([]);
    this.tripDocumentsLoading.set(false);
    this.tripDocumentsError.set('');
  }

  private ensureSelectedTrip(items: readonly TadaTripItem[]): void {
    if (!items.length) {
      this.selectedListTrip.set(null);
      this.selectedTrip.set(null);
      this.clearSupportingDocuments();
      return;
    }
    const current = items.find((trip) => trip.id === this.selectedListTrip()?.id);
    const latest = [...items].sort((left, right) => right.startAt.localeCompare(left.startAt))[0];
    this.openReview(current ?? latest);
  }

  private loadProfile(row: TadaEmployeeItem): void {
    this.employeesApi.get(row.employeeId).subscribe({
      next: (detail) => {
        if (this.drawerEmployee()?.employeeId !== row.employeeId) return;
        this.drawerProfile.set({ department: detail.department ?? null, location: detail.branchName ?? null });
      },
      error: () => {
        if (this.drawerEmployee()?.employeeId === row.employeeId) this.drawerProfile.set({ department: null, location: null });
      },
    });
  }

  private loadHistory(row: TadaEmployeeItem): void {
    this.decisionHistory.set(null);
    this.api.history(row.employeeId, this.applied().month).subscribe({
      next: (items) => {
        if (this.drawerEmployee()?.employeeId === row.employeeId) this.decisionHistory.set(items);
      },
      error: () => {
        if (this.drawerEmployee()?.employeeId === row.employeeId) this.decisionHistory.set([]);
      },
    });
  }

  private refreshDrawer(rows: readonly TadaEmployeeItem[]): void {
    const open = this.drawerEmployee();
    if (!open) return;
    const fresh = rows.find((row) => row.employeeId === open.employeeId);
    if (fresh) this.drawerEmployee.set(fresh);
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
    }).subscribe({
      next: (options) => {
        this.companies.set(options.companies);
        this.branches.set(options.branches.items);
        this.departments.set(options.departments);
      },
      error: () => this.snackBar.open('Filter lists could not be loaded.', 'OK', { duration: 4000 }),
    });
  }

  private employeeParams(
    page: number,
    pageSize: number,
    options?: { ignoreTab?: boolean; approval?: Approval | null },
  ) {
    const filters = this.applied();
    const approval = options?.ignoreTab
      ? (options.approval === undefined ? filters.approval : options.approval)
      : (this.tab() === 'queue' ? 'Pending' : filters.approval);
    const summarySearch = !options?.ignoreTab && this.tab() !== 'trips' ? this.summaryQuery().trim() : '';
    const search = summarySearch || filters.search;
    return {
      page,
      pageSize,
      sort: this.sort(),
      month: filters.month,
      ...(search ? { search } : {}),
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
      ...((this.summaryQuery().trim() || filters.search) ? { search: this.summaryQuery().trim() || filters.search } : {}),
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
    return pageAll((page) => this.api.employees({ ...this.employeeParams(page, 200), includeSummary: false }).pipe(
      map((report) => ({ items: report.items, total: report.total })),
    ));
  }

  private allTrips() {
    return pageAll((page) => this.api.report({ ...this.tripParams(page, 200), includeSummary: false }).pipe(
      map((report) => ({ items: report.items, total: report.total })),
    ));
  }

  private card(
    label: string,
    icon: string,
    current: number | null | undefined,
    previous: number | null | undefined,
    asMoney: boolean,
    text?: string,
  ): KpiCard {
    const value = text ?? (current == null ? '—' : asMoney ? inr(current, 2) : String(current));
    const delta = percentChange(current ?? null, previous ?? null);
    return { label, icon, value, delta, tone: delta == null ? 'muted' : delta.startsWith('-') ? 'down' : 'up' };
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

const APPROVAL_RANK: Record<string, number> = { Pending: 0, Approved: 1, Rejected: 2 };
const SETTLEMENT_RANK: Record<string, number> = { Open: 0, Sent: 1, Paid: 2 };

function sortEmployees(
  rows: readonly TadaEmployeeItem[],
  spec: { key: EmployeeSortKey; dir: 'asc' | 'desc' } | null,
  rates: TadaRates | null,
): TadaEmployeeItem[] {
  if (!spec) return [...rows];
  const dir = spec.dir === 'asc' ? 1 : -1;
  const bikeRate = rates?.bikePerKm ?? null;
  const carRate = rates?.carPerKm ?? null;
  const value = (row: TadaEmployeeItem): number | string => {
    switch (spec.key) {
      case 'employeeName': return row.employeeName;
      case 'designation': return row.designation ?? '';
      case 'totalTrips': return row.totalTrips;
      case 'payableKm': return Number(row.bikeKm) + Number(row.carKm);
      case 'bikeTa': return lineAmount(row.bikeKm, bikeRate);
      case 'carTa': return lineAmount(row.carKm, carRate);
      case 'additionalAllowance': return Number(row.additionalAllowance);
      case 'totalPayable': return Number(row.totalPayable);
      case 'approvalStatus': return APPROVAL_RANK[row.approvalStatus] ?? 0;
      case 'settlementStatus': return SETTLEMENT_RANK[row.settlementStatus] ?? 0;
    }
  };
  return [...rows].sort((left, right) => {
    const a = value(left);
    const b = value(right);
    let order = typeof a === 'number' && typeof b === 'number'
      ? a - b
      : String(a).localeCompare(String(b), undefined, { sensitivity: 'base', numeric: true });
    if (!order && spec.key === 'employeeName') {
      order = (left.designation ?? '').localeCompare(right.designation ?? '', undefined, { sensitivity: 'base', numeric: true });
    }
    return dir * (order || left.employeeCode.localeCompare(right.employeeCode));
  });
}

function monthLabel(month: string): string {
  const [year, mon] = month.split('-').map(Number);
  if (!year || !mon) return month;
  return payrollMonthText(new Date(year, mon - 1, 1));
}

function emptyEmployeeMonth(row: TadaEmployeeItem): TadaEmployeeItem {
  return {
    ...row,
    totalTrips: 0,
    pendingTrips: 0,
    approvedTrips: 0,
    rejectedTrips: 0,
    bikeKm: '0.00',
    carKm: '0.00',
    totalKm: '0.00',
    taAmount: '0.00',
    additionalAllowance: '0.00',
    totalPayable: '0.00',
    approvalStatus: 'Pending',
    settlementStatus: 'Open',
  };
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
    search: '',
  };
}

interface PriceRow {
  label: string;
  value: string;
  icon: string;
  calculated: boolean;
}

function distanceSource(trip: TadaTripItem): 'Adjusted Distance' | 'Map Distance' | 'GPS Distance' | null {
  if (trip.isDistanceAdjusted && trip.adjustedDistanceKm != null) return 'Adjusted Distance';
  if (trip.mapDistanceKm != null) return 'Map Distance';
  if (trip.gpsDistanceKm != null) return 'GPS Distance';
  return null;
}

function lineAmount(km: string, rate: string | null): number {
  if (!rate) return 0;
  const amount = Number(km) * Number(rate);
  if (!Number.isFinite(amount)) return 0;
  return Math.round(amount * 100) / 100;
}

function payableKmFromAllowances(
  summary: TadaEmployeeSummary | null,
  rates: TadaRates | null,
  previous: boolean,
): number | null {
  if (!summary || !rates) return null;
  const bikeMoney = Number(previous ? summary.previousBikeAllowance : summary.bikeAllowance);
  const carMoney = Number(previous ? summary.previousCarAllowance : summary.carAllowance);
  const bikeRate = Number(rates.bikePerKm);
  if (!bikeRate) return null;
  const bikeKm = bikeMoney / bikeRate;
  const carRate = rates.carPerKm ? Number(rates.carPerKm) : 0;
  const carKm = carRate ? carMoney / carRate : 0;
  return bikeKm + carKm;
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

function readPayments(items: readonly TadaDecisionHistoryItem[]): { id: number; amount: string; date: string; mode: string; reference: string; note: string }[] {
  const known = ['Paid amount', 'Payment date', 'Payment mode', 'Payment reference'];
  return items
    .filter((row) => row.tripId == null && row.toStatus === 'Paid' && row.remarks)
    .map((item) => {
      const fields = new Map<string, string>();
      const notes: string[] = [];
      for (const part of (item.remarks ?? '').split(' | ')) {
        const index = part.indexOf(': ');
        const label = index >= 0 ? part.slice(0, index) : '';
        if (known.includes(label)) fields.set(label, part.slice(index + 2).trim());
        else if (part.trim()) notes.push(part.trim());
      }
      return {
        id: item.id,
        amount: fields.get('Paid amount') || '',
        date: fields.get('Payment date') || '',
        mode: fields.get('Payment mode') || '',
        reference: fields.get('Payment reference') || '',
        note: notes.join(' '),
      };
    });
}

function tripCallKey(trip: { callId?: number | null; callNo?: string | null }): string {
  return trip.callId == null && !trip.callNo ? 'unlinked' : `call:${trip.callId ?? trip.callNo}`;
}

function buildHistoryRows(trips: readonly TadaTripItem[], audits: readonly TadaDecisionHistoryItem[]): HistoryRow[] {
  const ordered = [...trips].sort((left, right) => left.startAt.localeCompare(right.startAt) || left.id - right.id);
  const numbers = new Map<number, number>();
  const counters = new Map<string, number>();
  for (const trip of ordered) {
    const key = tripCallKey(trip);
    const next = (counters.get(key) ?? 0) + 1;
    counters.set(key, next);
    numbers.set(trip.id, next);
  }
  const byTrip = new Map<number, TadaDecisionHistoryItem[]>();
  for (const item of audits) {
    if (item.tripId == null) continue;
    const list = byTrip.get(item.tripId) ?? [];
    list.push(item);
    byTrip.set(item.tripId, list);
  }
  return ordered.map((trip) => {
    const events = [...(byTrip.get(trip.id) ?? [])]
      .sort((left, right) => right.changedAt.localeCompare(left.changedAt) || right.id - left.id)
      .map((item) => ({ item, parts: readAudit(item.remarks) }));
    const latest = events[0] ?? null;
    const approval = events.find((event) => event.parts.approvedAmount) ?? null;
    const claimed = trip.taAmount == null ? null : Number(trip.taAmount);
    const approved = approval?.parts.approvedAmount == null ? null : Number(approval.parts.approvedAmount);
    const adjustment = claimed != null && approved != null && Number.isFinite(claimed) && Number.isFinite(approved)
      ? (claimed - approved).toFixed(2)
      : null;
    return {
      trip,
      number: numbers.get(trip.id) ?? 0,
      audits: events,
      latest,
      approvedAmount: approval?.parts.approvedAmount ?? null,
      adjustmentAmount: adjustment,
    };
  });
}

function readAudit(remarks: string | null | undefined): AuditParts {
  const text = remarks?.trim() ?? '';
  if (!text) return { approvedAmount: null, adjustmentReason: null, documentDecision: null, comment: null };
  const approvedAmount = text.match(/Approved amount:\s*₹?\s*([0-9][0-9,]*(?:\.\d+)?)/)?.[1]?.replaceAll(',', '') ?? null;
  const adjustmentReason = text.match(/Adjustment reason:\s*([^.]*)/)?.[1]?.trim() || null;
  const documentDecision = text.match(/Document:\s*([^.]*)/)?.[1]?.trim() || null;
  const comment = text
    .replace(/Approved amount:\s*₹?\s*[0-9][0-9,]*(?:\.\d+)?\.?\s*/g, '')
    .replace(/Adjustment reason:\s*[^.]+\.?\s*/g, '')
    .replace(/Document:\s*[^.]+\.?\s*/g, '')
    .trim() || null;
  return { approvedAmount, adjustmentReason, documentDecision, comment };
}

function sumMoney(values: readonly (string | null)[]): string | null {
  const numbers = values.filter((value): value is string => value != null && value !== '').map((value) => Number(value));
  if (!numbers.length || numbers.some((value) => !Number.isFinite(value))) return null;
  return numbers.reduce((total, value) => total + value, 0).toFixed(2);
}

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

function formatDay(date: Date): string {
  return `${String(date.getDate()).padStart(2, '0')}-${String(date.getMonth() + 1).padStart(2, '0')}-${date.getFullYear()}`;
}

function startOfDay(date: Date): Date {
  return new Date(date.getFullYear(), date.getMonth(), date.getDate());
}

function isoDay(date: Date | null): string {
  if (!date) return '';
  return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}-${String(date.getDate()).padStart(2, '0')}`;
}

function monthBounds(month: string): { from: Date; to: Date } {
  const [year, mon] = month.split('-').map(Number);
  return { from: new Date(year, (mon || 1) - 1, 1), to: new Date(year, mon || 1, 0) };
}

function presetRange(id: Exclude<TripPreset, 'month' | 'custom'>): { from: Date; to: Date } {
  const today = startOfDay(new Date());
  if (id === 'today') return { from: today, to: today };
  if (id === 'yesterday') {
    const day = new Date(today);
    day.setDate(day.getDate() - 1);
    return { from: day, to: day };
  }
  if (id === '7' || id === '15') {
    const from = new Date(today);
    from.setDate(from.getDate() - (id === '7' ? 6 : 14));
    return { from, to: today };
  }
  if (id === 'this') {
    return { from: new Date(today.getFullYear(), today.getMonth(), 1), to: new Date(today.getFullYear(), today.getMonth() + 1, 0) };
  }
  return { from: new Date(today.getFullYear(), today.getMonth() - 1, 1), to: new Date(today.getFullYear(), today.getMonth(), 0) };
}

function monthsCovering(from: Date, to: Date): string[] {
  const months: string[] = [];
  let year = from.getFullYear();
  let month = from.getMonth();
  const end = to.getFullYear() * 12 + to.getMonth();
  while (year * 12 + month <= end && months.length < 48) {
    months.push(`${year}-${String(month + 1).padStart(2, '0')}`);
    month += 1;
    if (month > 11) {
      month = 0;
      year += 1;
    }
  }
  return months;
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
