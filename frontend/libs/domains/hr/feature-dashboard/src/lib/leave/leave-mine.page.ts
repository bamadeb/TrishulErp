import { DatePipe, NgTemplateOutlet } from '@angular/common';
import { ChangeDetectionStrategy, Component, computed, effect, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { MatButton, MatIconButton } from '@angular/material/button';
import { provideNativeDateAdapter } from '@angular/material/core';
import { MatDatepicker, MatDatepickerInput, MatDatepickerToggle } from '@angular/material/datepicker';
import { MatDialog } from '@angular/material/dialog';
import { MatFormField, MatLabel } from '@angular/material/form-field';
import { MatIcon } from '@angular/material/icon';
import { MatInput } from '@angular/material/input';
import { MatMenu, MatMenuItem, MatMenuTrigger } from '@angular/material/menu';
import { MatOption, MatSelect } from '@angular/material/select';
import { MatSnackBar } from '@angular/material/snack-bar';
import { MatTab, MatTabGroup } from '@angular/material/tabs';
import { AuthStore } from '@trishul/core-auth';
import { LeaveApi, MineBalance, MineCompOff, MineHoliday, MineRequestItem } from '@trishul/hr-data-access';
import { PageHeader, StatusBadge, StatusSeverity } from '@trishul/shared-ui';
import { LeaveApplyDialog, LeaveApplyDialogData, LeaveConfirmDialog, LeaveTypeChoice } from './leave-apply.dialog';
import { LeaveDrawerBalance, LeaveRequestDrawer } from './leave-mine.drawer';
import { MineLeaveRequest, MineLeaveStatus } from './leave-mine.models';

type Kpi = '' | 'balance' | 'approved' | 'pending' | 'rejected' | 'upcoming';

@Component({
  selector: 'trishul-leave-mine-page',
  imports: [
    DatePipe,
    FormsModule,
    NgTemplateOutlet,
    MatButton,
    MatDatepicker,
    MatDatepickerInput,
    MatDatepickerToggle,
    MatFormField,
    MatIcon,
    MatIconButton,
    MatInput,
    MatLabel,
    MatMenu,
    MatMenuItem,
    MatMenuTrigger,
    MatOption,
    MatSelect,
    MatTab,
    MatTabGroup,
    PageHeader,
    StatusBadge,
    LeaveRequestDrawer,
  ],
  providers: [provideNativeDateAdapter()],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './leave-mine.page.html',
  styleUrl: './leave-mine.page.scss',
})
export class LeaveMinePage {
  private readonly dialog = inject(MatDialog);
  private readonly snackBar = inject(MatSnackBar);
  private readonly leaveApi = inject(LeaveApi);
  private readonly auth = inject(AuthStore);

  protected readonly severities: Partial<Record<string, StatusSeverity>> = {
    Pending: 'warn',
    Approved: 'success',
    Rejected: 'danger',
    Cancelled: 'neutral',
    Available: 'success',
    Partial: 'warn',
    Used: 'neutral',
    Expiring: 'warn',
    Expired: 'danger',
  };
  protected readonly years = [2026, 2025];
  protected readonly year = signal(2026);
  protected readonly tab = signal(0);
  protected readonly kpi = signal<Kpi>('');
  protected readonly focusUpcoming = signal(false);
  protected readonly type = signal('');
  protected readonly status = signal<MineLeaveStatus | ''>('');
  protected readonly search = signal('');
  protected readonly periodFrom = signal<Date | null>(new Date(2026, 3, 1));
  protected readonly periodTo = signal<Date | null>(new Date(2027, 2, 31));
  protected readonly page = signal(0);
  protected readonly pageSize = signal(5);
  protected readonly calendar = signal(new Date(new Date().getFullYear(), new Date().getMonth(), 1));
  protected readonly showAllHolidays = signal(false);
  protected readonly error = signal('');
  protected readonly balances = signal<BalanceCard[]>([]);
  protected readonly leaveTypes = signal<string[]>([]);
  protected readonly leaveChoices = signal<LeaveTypeChoice[]>([]);
  protected readonly requests = signal<MineLeaveRequest[]>([]);
  protected readonly holidays = signal<{ date: string; name: string }[]>([]);
  protected readonly compOff = signal<CompOffView>({ earned: 0, available: 0, used: 0, expiring: '—', lines: [] });
  protected readonly detail = signal<MineLeaveRequest | null>(null);
  protected readonly menuRow = signal<MineLeaveRequest | null>(null);
  protected readonly employeeName = signal('');
  protected readonly employeeCode = signal('');
  protected readonly employeeId = signal<number | null>(null);
  private boundUserId: number | null = null;

  constructor() {
    effect(() => {
      const userId = this.auth.user()?.id ?? null;
      if (userId === this.boundUserId) return;
      this.boundUserId = userId;
      this.employeeName.set('');
      this.employeeCode.set('');
      this.employeeId.set(null);
      this.balances.set([]);
      this.requests.set([]);
      this.compOff.set({ earned: 0, available: 0, used: 0, expiring: '—', lines: [] });
      if (userId != null) this.reload();
    });
  }

  protected readonly filtered = computed(() => {
    const from = this.periodFrom();
    const to = this.periodTo();
    const term = this.search().trim().toLowerCase();
    const today = strip(new Date());
    return this.requests()
      .filter((row) => {
        const start = new Date(`${row.from}T00:00:00`);
        if (from && start < strip(from)) return false;
        if (to && start > strip(to)) return false;
        if (this.type() && row.leaveType !== this.type()) return false;
        if (this.status() && row.status !== this.status()) return false;
        if (this.focusUpcoming() && (row.status === 'Rejected' || row.status === 'Cancelled' || start < today)) return false;
        if (term && !`${row.id} ${row.reason}`.toLowerCase().includes(term)) return false;
        return true;
      })
      .sort((left, right) => right.requestId - left.requestId);
  });

  protected readonly history = computed(() => this.filtered().filter((row) => row.status !== 'Pending'));
  protected readonly summary = computed(() => {
    const rows = this.requests();
    const today = strip(new Date());
    return {
      pending: rows.filter((row) => row.status === 'Pending').length,
      approved: rows.filter((row) => row.status === 'Approved').length,
      rejected: rows.filter((row) => row.status === 'Rejected').length,
      upcoming: rows.filter((row) => row.status !== 'Rejected' && row.status !== 'Cancelled' && new Date(`${row.from}T00:00:00`) >= today).length,
    };
  });
  protected readonly totalDays = computed(() => this.balances().reduce((sum, card) => sum + card.available, 0));
  protected readonly requestPage = computed(() => slice(this.filtered(), this.page(), this.pageSize()));
  protected readonly historyPage = computed(() => slice(this.history(), this.page(), this.pageSize()));
  protected readonly cells = computed(() => monthCells(this.calendar()));
  protected readonly upcomingHolidays = computed(() => {
    const today = iso(new Date());
    const rows = this.holidays().filter((holiday) => holiday.date >= today);
    return this.showAllHolidays() ? rows : rows.slice(0, 3);
  });

  protected chooseYear(year: number): void {
    this.year.set(year);
    this.periodFrom.set(new Date(year, 3, 1));
    this.periodTo.set(new Date(year + 1, 2, 31));
    this.page.set(0);
    this.reload();
  }

  protected chooseTab(index: number): void {
    if (index === this.tab()) return;
    this.tab.set(index);
    this.page.set(0);
  }

  protected pickKpi(kind: Kpi): void {
    this.kpi.set(kind);
    this.page.set(0);
    if (kind === 'balance') {
      this.tab.set(2);
      return;
    }
    this.tab.set(0);
    this.focusUpcoming.set(kind === 'upcoming');
    this.status.set(kind === 'approved' ? 'Approved' : kind === 'pending' ? 'Pending' : kind === 'rejected' ? 'Rejected' : '');
  }

  protected chooseStatus(value: MineLeaveStatus | ''): void {
    this.status.set(value);
    this.focusUpcoming.set(false);
    this.kpi.set('');
    this.page.set(0);
  }

  protected setPageSize(size: number): void {
    this.pageSize.set(Number(size));
    this.page.set(0);
  }

  protected stepPage(offset: number): void {
    this.page.update((value) => value + offset);
  }

  protected fromIndex(total: number): number {
    return total ? this.page() * this.pageSize() + 1 : 0;
  }

  protected toIndex(total: number): number {
    return Math.min(total, (this.page() + 1) * this.pageSize());
  }

  protected lastPage(total: number): number {
    return Math.max(0, Math.ceil(total / this.pageSize()) - 1);
  }

  protected shiftMonth(offset: number): void {
    const current = this.calendar();
    this.calendar.set(new Date(current.getFullYear(), current.getMonth() + offset, 1));
  }

  protected pickDay(day: Date): void {
    this.periodFrom.set(day);
    this.periodTo.set(day);
    this.page.set(0);
    this.tab.set(0);
  }

  protected mark(day: Date): string {
    const key = iso(day);
    if (this.holidays().some((holiday) => holiday.date === key)) return 'holiday';
    const match = this.requests().find((row) => key >= row.from && key <= row.to && row.status !== 'Rejected');
    return match?.status === 'Pending' ? 'pending' : match ? 'approved' : '';
  }

  protected isToday(day: Date): boolean {
    return iso(day) === iso(new Date());
  }

  protected inMonth(day: Date): boolean {
    return day.getMonth() === this.calendar().getMonth();
  }

  protected amount(value: number): string {
    return Number.isInteger(value) ? String(value) : value.toFixed(1);
  }

  protected pendingTitle(row: MineLeaveRequest): string {
    if (row.status !== 'Pending') return 'No approval is pending.';
    if (row.needsHrAttention || !row.pendingWithName) return 'Awaiting Assignment. HR attention required.';
    return row.pendingWithRole ? `${row.pendingWithName}, ${row.pendingWithRole}` : row.pendingWithName;
  }

  protected balanceFor(row: MineLeaveRequest): LeaveDrawerBalance | null {
    const card = this.balances().find((item) => item.leaveTypeId === row.leaveTypeId);
    return card ? { leaveTypeId: card.leaveTypeId, available: card.available } : null;
  }

  protected show(row: MineLeaveRequest): void {
    this.detail.set(row);
  }

  protected apply(): void {
    this.open(null, 'create');
  }

  protected open(request: MineLeaveRequest | null, mode: 'create' | 'edit' | 'view'): void {
    this.dialog
      .open<LeaveApplyDialog, LeaveApplyDialogData, boolean>(LeaveApplyDialog, {
        data: {
          mode,
          request,
          leaveTypes: this.leaveChoices(),
          canAuthorizeBackdate: this.auth.hasPermission('hr.leave.manage'),
        },
        width: '680px',
        maxWidth: 'calc(100vw - 32px)',
        maxHeight: '90vh',
      })
      .afterClosed()
      .subscribe((saved) => {
        if (saved) this.reload();
      });
  }

  protected remove(row: MineLeaveRequest): void {
    this.dialog
      .open<LeaveConfirmDialog, string, boolean>(LeaveConfirmDialog, { data: row.id })
      .afterClosed()
      .subscribe((confirmed) => {
        if (!confirmed) return;
        this.leaveApi.cancelMineRequest(row.requestId).subscribe({
          next: () => {
            this.snackBar.open(`${row.id} withdrawn.`, 'Close', { duration: 2500 });
            if (this.detail()?.requestId === row.requestId) this.detail.set(null);
            this.reload();
          },
          error: (error: unknown) => this.snackBar.open(problemDetail(error, 'The leave request could not be withdrawn.'), 'Close', { duration: 4000 }),
        });
      });
  }

  protected exportRows(): void {
    const header = ['Request ID', 'Leave type', 'From', 'To', 'Days', 'Reason', 'Pending With', 'Status'];
    const lines = this.filtered().map((row) => [
      row.id, row.leaveType, row.from, row.to, String(row.days), row.reason, pendingExport(row), row.status,
    ]);
    const csv = [header, ...lines].map((line) => line.map((value) => `"${value.replaceAll('"', '""')}"`).join(',')).join('\r\n');
    const url = URL.createObjectURL(new Blob([csv], { type: 'text/csv;charset=utf-8' }));
    const link = document.createElement('a');
    link.href = url;
    link.download = 'my-leave.csv';
    link.click();
    URL.revokeObjectURL(url);
  }

  protected download(_row: MineLeaveRequest): void {
    this.snackBar.open('No document is stored for this request.', 'Close', { duration: 2500 });
  }

  private reload(): void {
    const year = this.year();
    this.leaveApi.mineProfile().subscribe({
      next: (profile) => {
        const linked = this.auth.user()?.employeeId ?? null;
        if (linked != null && profile.employeeId !== linked) {
          this.employeeName.set('');
          this.employeeCode.set('');
          this.employeeId.set(null);
          this.error.set('Leave could not be scoped to your employee profile.');
          return;
        }
        this.employeeId.set(profile.employeeId);
        this.employeeCode.set(profile.employeeCode);
        this.employeeName.set(profile.employeeName);
      },
      error: () => {
        this.employeeName.set('');
        this.employeeCode.set('');
        this.employeeId.set(null);
      },
    });
    this.leaveApi.mineBalances(year).subscribe({
      next: (board) => {
        this.balances.set(board.items.map(mapBalance));
        this.leaveTypes.set(board.items.map((item) => `${item.name} (${item.code})`));
        this.leaveChoices.set(board.items.map((item) => ({
          id: item.leaveTypeId,
          label: `${item.name} (${item.code})`,
          maxBackdateDays: item.maxBackdateDays ?? null,
          backdateRequiresAuthorization: item.backdateRequiresAuthorization ?? false,
        })));
      },
      error: (error: unknown) => this.error.set(problemDetail(error, 'Leave balances could not be loaded.')),
    });
    this.leaveApi.mineRequests(year).subscribe({
      next: (page) => {
        const rows = page.items.map(mapRequest);
        this.requests.set(rows);
        const open = this.detail();
        if (open) this.detail.set(rows.find((row) => row.requestId === open.requestId) ?? null);
      },
      error: (error: unknown) => this.error.set(problemDetail(error, 'Leave requests could not be loaded.')),
    });
    this.leaveApi.mineHolidays(year).subscribe({
      next: (rows) => this.holidays.set(rows.map(mapHoliday)),
      error: (error: unknown) => this.error.set(problemDetail(error, 'Holidays could not be loaded.')),
    });
    this.leaveApi.mineCompOff(year).subscribe({
      next: (row) => this.compOff.set(mapCompOff(row)),
      error: (error: unknown) => this.error.set(problemDetail(error, 'Comp-Off could not be loaded.')),
    });
  }
}

interface BalanceCard {
  leaveTypeId: number;
  code: string;
  name: string;
  available: number;
  entitlement: number;
  used: number;
  pending: number;
  tone: string;
}

interface CompOffView {
  earned: number;
  available: number;
  used: number;
  expiring: string;
  lines: { earnedOn: string; days: number; note: string; expires: string; status: string }[];
}

const TONES: Record<string, string> = { CL: 'info', EL: 'success', SL: 'warn', CO: 'tertiary' };

function mapBalance(row: MineBalance): BalanceCard {
  return {
    leaveTypeId: row.leaveTypeId,
    code: row.code,
    name: row.name,
    available: Number(row.available),
    entitlement: Number(row.opening) + Number(row.credited),
    used: Number(row.availed),
    pending: Number(row.pending),
    tone: TONES[row.code] ?? 'info',
  };
}

function mapRequest(row: MineRequestItem): MineLeaveRequest {
  return {
    id: row.displayId,
    requestId: row.requestId,
    leaveTypeId: row.leaveTypeId,
    leaveType: row.leaveType,
    from: row.fromDate,
    to: row.toDate,
    days: Number(row.days),
    reason: row.reason ?? '',
    status: row.status,
    part: row.isHalfDay ? 'First half' : 'Full day',
    contact: '',
    fileName: null,
    appliedAt: row.appliedAt,
    pendingWithName: row.pendingWithName,
    pendingWithRole: row.pendingWithRole,
    needsHrAttention: row.needsHrAttention,
  };
}

function pendingExport(row: MineLeaveRequest): string {
  if (row.status !== 'Pending') return '—';
  if (row.needsHrAttention || !row.pendingWithName) return 'Awaiting Assignment';
  return row.pendingWithRole ? `${row.pendingWithName} (${row.pendingWithRole})` : row.pendingWithName;
}

function mapHoliday(row: MineHoliday): { date: string; name: string } {
  return { date: row.holidayDate, name: row.name };
}

function mapCompOff(row: MineCompOff): CompOffView {
  return {
    earned: Number(row.earned),
    available: Number(row.available),
    used: Number(row.used),
    expiring: row.expiring == null ? '—' : String(Number(row.expiring)),
    lines: (row.lines ?? []).map((line) => ({
      earnedOn: line.earnedOn,
      days: Number(line.days),
      note: line.note,
      expires: line.expires,
      status: line.status,
    })),
  };
}

function problemDetail(error: unknown, fallback: string): string {
  const detail = (error as { error?: { detail?: string } }).error?.detail;
  return typeof detail === 'string' && detail ? detail : fallback;
}

function slice<T>(rows: T[], page: number, size: number): T[] {
  return rows.slice(page * size, page * size + size);
}

function strip(value: Date): Date {
  return new Date(value.getFullYear(), value.getMonth(), value.getDate());
}

function iso(value: Date): string {
  const month = String(value.getMonth() + 1).padStart(2, '0');
  const day = String(value.getDate()).padStart(2, '0');
  return `${value.getFullYear()}-${month}-${day}`;
}

function monthCells(cursor: Date): Date[] {
  const first = new Date(cursor.getFullYear(), cursor.getMonth(), 1);
  const start = new Date(first);
  start.setDate(1 - first.getDay());
  return Array.from({ length: 42 }, (_, index) => {
    const day = new Date(start);
    day.setDate(start.getDate() + index);
    return day;
  });
}
