import { DatePipe, DecimalPipe } from '@angular/common';
import {
  ChangeDetectionStrategy,
  ChangeDetectorRef,
  Component,
  computed,
  inject,
  NgZone,
  OnInit,
  signal,
  viewChild,
} from '@angular/core';
import { FormsModule } from '@angular/forms';
import { MatButton, MatIconButton } from '@angular/material/button';
import { MatCheckbox } from '@angular/material/checkbox';
import { MatDialog } from '@angular/material/dialog';
import { provideNativeDateAdapter } from '@angular/material/core';
import { MatDatepicker, MatDatepickerInput } from '@angular/material/datepicker';
import { MatFormField, MatPrefix } from '@angular/material/form-field';
import { MatIcon } from '@angular/material/icon';
import { MatInput } from '@angular/material/input';
import { MatMenu, MatMenuItem, MatMenuTrigger } from '@angular/material/menu';
import { MatProgressBar } from '@angular/material/progress-bar';
import { MatOption, MatSelect } from '@angular/material/select';
import { MatSnackBar } from '@angular/material/snack-bar';
import { MatTooltip } from '@angular/material/tooltip';
import { Router } from '@angular/router';
import { AuthStore } from '@trishul/core-auth';
import {
  ATTENDANCE_FINALIZE_PERMISSION,
  AttendanceApi,
  FinalizationAssignee,
  FinalizationChecklistItem,
  FinalizationFollowupWrite,
  FinalizationGroupBy,
  FinalizationGroupRow,
  FinalizationKpi,
  FinalizationRowStatus,
  FinalizationSummary,
  FollowupStatus,
} from '@trishul/hr-data-access';
import { PageHeader, confirmAction } from '@trishul/shared-ui';
import { filter } from 'rxjs';
import { FinalizationTab } from './attendance.models';

const MONTH_LABELS = [
  'Jan',
  'Feb',
  'Mar',
  'Apr',
  'May',
  'Jun',
  'Jul',
  'Aug',
  'Sep',
  'Oct',
  'Nov',
  'Dec',
] as const;

const EMPTY_KPI: FinalizationKpi = {
  totalEmployees: 0,
  attendanceReady: 0,
  withExceptions: 0,
  pendingRegularization: 0,
  finalized: 0,
};

/** Attendance Finalization — API-backed monthly readiness and lock. */
@Component({
  selector: 'trishul-attendance-finalization-page',
  imports: [
    DecimalPipe,
    DatePipe,
    FormsModule,
    MatButton,
    MatCheckbox,
    MatFormField,
    MatIcon,
    MatIconButton,
    MatInput,
    MatDatepicker,
    MatDatepickerInput,
    MatMenu,
    MatMenuItem,
    MatMenuTrigger,
    MatOption,
    MatPrefix,
    MatProgressBar,
    MatSelect,
    MatTooltip,
    PageHeader,
  ],
  changeDetection: ChangeDetectionStrategy.OnPush,
  providers: [provideNativeDateAdapter()],
  templateUrl: './attendance-finalization.page.html',
  styleUrl: './attendance-finalization.page.scss',
})
export class AttendanceFinalizationPage implements OnInit {
  private readonly api = inject(AttendanceApi);
  private readonly auth = inject(AuthStore);
  private readonly snackBar = inject(MatSnackBar);
  private readonly dialog = inject(MatDialog);
  private readonly router = inject(Router);
  private readonly zone = inject(NgZone);
  private readonly cdr = inject(ChangeDetectorRef);
  private readonly picker = viewChild(MatDatepicker);

  protected readonly canLockAttendance = this.auth.hasPermission(ATTENDANCE_FINALIZE_PERMISSION);

  private readonly now = new Date();
  protected readonly year = signal(this.now.getFullYear());
  protected readonly monthIndex = signal(this.now.getMonth());

  protected readonly contentTab = signal<FinalizationTab>('department');
  protected readonly search = signal('');
  protected readonly groupFilter = signal('');
  protected readonly statusFilter = signal<FinalizationRowStatus | ''>('');
  protected readonly selectedIds = signal<Set<number>>(new Set());
  protected readonly menuRow = signal<FinalizationGroupRow | null>(null);

  protected readonly loading = signal(false);
  protected readonly error = signal('');
  protected readonly locking = signal(false);
  protected readonly savingId = signal<string | null>(null);
  protected readonly reminding = signal(false);

  protected readonly kpi = signal<FinalizationKpi>(EMPTY_KPI);
  protected readonly summary = signal<FinalizationSummary | null>(null);
  protected readonly checklist = signal<FinalizationChecklistItem[]>([]);
  protected readonly groups = signal<FinalizationGroupRow[]>([]);
  protected readonly assignees = signal<FinalizationAssignee[]>([]);
  protected readonly openItemId = signal<string | null>(null);
  protected readonly sideTab = signal<'tasks' | 'history'>('tasks');
  protected readonly drafts = signal<Record<string, FollowupDraft>>({});
  protected readonly canFinalize = signal(false);
  protected readonly isFinalized = signal(false);

  protected readonly monthLabel = computed(
    () => `${MONTH_LABELS[this.monthIndex()]!} ${this.year()}`,
  );

  protected readonly pickedMonth = computed(() => new Date(this.year(), this.monthIndex(), 1));

  protected readonly groupLabel = computed(() =>
    this.contentTab() === 'department' ? 'Department' : 'Location',
  );

  protected readonly groupOptions = computed(() =>
    [...new Set(this.groups().map((row) => row.name))].sort((a, b) => a.localeCompare(b)),
  );

  protected readonly filteredRows = computed(() => {
    const q = this.search().trim().toLowerCase();
    const group = this.groupFilter();
    const status = this.statusFilter();
    return this.groups().filter((row) => {
      if (group && row.name !== group) return false;
      if (status && row.status !== status) return false;
      if (!q) return true;
      return row.name.toLowerCase().includes(q);
    });
  });

  protected readonly allSelected = computed(() => {
    const rows = this.filteredRows();
    return rows.length > 0 && rows.every((row) => this.selectedIds().has(row.id));
  });

  protected readonly someSelected = computed(() => {
    const rows = this.filteredRows();
    const selected = rows.filter((row) => this.selectedIds().has(row.id)).length;
    return selected > 0 && selected < rows.length;
  });

  protected readonly checklistDoneCount = computed(
    () => this.checklist().filter((item) => item.done).length,
  );

  protected readonly pendingGroups = computed(
    () => this.groups().filter((row) => row.status === 'Pending').length,
  );

  protected readonly overallStatus = computed(() => {
    if (this.isFinalized()) return 'Finalized';
    if (this.checklist().length > 0 && this.checklist().every((item) => item.done)) return 'Ready';
    return 'In Progress';
  });

  protected readonly notificationHistory = computed(() =>
    this.checklist()
      .flatMap((item) =>
        item.reminders.map((entry) => ({
          ...entry,
          task: taskTitle(item.id),
        })),
      )
      .sort((left, right) => right.id - left.id),
  );

  ngOnInit(): void {
    this.reload();
  }

  protected setTab(tab: FinalizationTab): void {
    this.contentTab.set(tab);
    this.search.set('');
    this.groupFilter.set('');
    this.statusFilter.set('');
    this.selectedIds.set(new Set());
    this.reload();
  }

  protected shiftMonth(delta: number): void {
    const date = new Date(this.year(), this.monthIndex() + delta, 1);
    this.year.set(date.getFullYear());
    this.monthIndex.set(date.getMonth());
    this.selectedIds.set(new Set());
    this.reload();
  }

  protected openPicker(): void {
    this.picker()?.open();
  }

  protected onMonthPicked(value: Date, picker: MatDatepicker<Date>): void {
    picker.close();
    if (value.getFullYear() === this.year() && value.getMonth() === this.monthIndex()) return;
    this.year.set(value.getFullYear());
    this.monthIndex.set(value.getMonth());
    this.selectedIds.set(new Set());
    this.reload();
  }

  protected onSearch(value: string): void {
    this.search.set(value);
  }

  protected onGroupFilter(value: string): void {
    this.groupFilter.set(value);
  }

  protected onStatusFilter(value: FinalizationRowStatus | ''): void {
    this.statusFilter.set(value);
  }

  protected isSelected(id: number): boolean {
    return this.selectedIds().has(id);
  }

  protected toggleRow(id: number, checked: boolean): void {
    this.selectedIds.update((set) => {
      const next = new Set(set);
      if (checked) next.add(id);
      else next.delete(id);
      return next;
    });
  }

  protected toggleAll(checked: boolean): void {
    this.selectedIds.update((set) => {
      const next = new Set(set);
      for (const row of this.filteredRows()) {
        if (checked) next.add(row.id);
        else next.delete(row.id);
      }
      return next;
    });
  }

  protected refresh(): void {
    this.reload();
  }

  protected exportExcel(): void {
    const rows = this.filteredRows();
    if (!rows.length) {
      this.snackBar.open('No rows to export.', 'OK', { duration: 2000 });
      return;
    }
    const label = this.groupLabel();
    const header = [
      label,
      'Employees',
      'Present',
      'Absent',
      'Leave',
      'Exceptions',
      'Pending Regularization',
      'Readiness %',
      'Status',
    ];
    const lines = [
      header.join(','),
      ...rows.map((row) =>
        [
          csv(row.name),
          row.employees,
          row.present,
          row.absent,
          row.leave,
          row.exceptions,
          row.pendingRegularization,
          row.readiness,
          row.status,
        ].join(','),
      ),
    ];
    const blob = new Blob([lines.join('\n')], { type: 'text/csv;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `attendance-finalization-${this.year()}-${String(this.monthIndex() + 1).padStart(2, '0')}.csv`;
    a.click();
    URL.revokeObjectURL(url);
    this.snackBar.open(`Exported ${rows.length} ${label.toLowerCase()}(s).`, 'OK', { duration: 2200 });
  }

  protected viewDetails(row?: FinalizationGroupRow | null): void {
    const target = row ?? this.menuRow();
    if (!target) return;
    const groupBy = this.contentTab();
    const queryParams =
      groupBy === 'department'
        ? { department: target.name, year: this.year(), month: this.monthIndex() + 1 }
        : { location: target.name, year: this.year(), month: this.monthIndex() + 1 };
    void this.router.navigate(['/hr/attendance/monthly-muster'], { queryParams });
    this.snackBar.open(
      `${target.name}: ${target.readiness}% ready · ${target.exceptions} exception(s) · ${target.pendingRegularization} pending regularization(s)`,
      'OK',
      { duration: 3200 },
    );
  }

  protected finalizeAttendance(): void {
    if (!this.canLockAttendance) {
      this.snackBar.open('You do not have permission to finalize attendance.', 'OK', {
        duration: 3500,
      });
      return;
    }
    if (this.isFinalized()) {
      this.snackBar.open(`Attendance for ${this.monthLabel()} is already finalized.`, 'OK', {
        duration: 2800,
      });
      return;
    }
    if (!this.canFinalize()) {
      const open = this.checklist()
        .filter((item) => !item.done)
        .map((item) => item.label);
      this.snackBar.open(
        open.length
          ? `Cannot finalize yet: ${open.join('; ')}.`
          : 'Cannot finalize attendance for this month yet.',
        'OK',
        { duration: 4500 },
      );
      return;
    }
    confirmAction(this.dialog, {
      title: 'Finalize & lock attendance?',
      message: `Once finalized, attendance for ${this.monthLabel()} will be locked for payroll. This cannot be undone from this screen.`,
      confirmText: 'Finalize & Lock',
      destructive: true,
    })
      .pipe(filter(Boolean))
      .subscribe(() => {
        this.locking.set(true);
        this.api.lockFinalization(this.year(), this.monthIndex() + 1).subscribe({
          next: (result) => {
            this.locking.set(false);
            this.snackBar.open(result.message, 'OK', { duration: 3500 });
            this.reload();
          },
          error: (err: unknown) => {
            this.locking.set(false);
            this.snackBar.open(problem(err, 'Could not finalize attendance.'), 'OK', {
              duration: 4500,
            });
          },
        });
      });
  }

  protected followupClass(status: FollowupStatus): string {
    return `followup ${status.toLowerCase().replace(' ', '-')}`;
  }

  protected taskTitle(id: string): string {
    return taskTitle(id);
  }

  protected ownerText(item: FinalizationChecklistItem): string {
    if (item.ownerName) return item.ownerName;
    switch (item.id) {
      case 'exceptions':
        return 'HR Attendance Officer';
      case 'regularization':
        return 'Reporting Managers';
      case 'ready':
        return 'Department Heads';
      case 'pending':
        return 'HR / Responsible Manager';
      default:
        return '';
    }
  }

  protected openLabel(id: string): string {
    switch (id) {
      case 'exceptions':
        return 'Open Exceptions';
      case 'regularization':
        return 'Open Requests';
      case 'ready':
        return 'Open Departments';
      case 'pending':
        return 'View Missing Data';
      default:
        return 'Open';
    }
  }

  protected taskCount(item: FinalizationChecklistItem): number | null {
    if (item.done) return null;
    if (item.id === 'exceptions') return this.kpi().withExceptions;
    if (item.id === 'regularization') return this.kpi().pendingRegularization;
    if (item.id === 'ready') return this.groups().filter((row) => row.status !== 'Ready').length;
    return null;
  }

  protected dueText(item: FinalizationChecklistItem): string {
    if (item.done) return '';
    return formatDue(item.dueDate || this.defaultDue());
  }

  protected alertState(item: FinalizationChecklistItem): 'sent' | 'failed' | null {
    if (item.reminders.some((entry) => entry.status === 'Sent')) return 'sent';
    if (item.reminders.some((entry) => entry.status === 'Failed')) return 'failed';
    return null;
  }

  private defaultDue(): string {
    const today = new Date();
    const inViewedMonth =
      today.getFullYear() === this.year() && today.getMonth() === this.monthIndex();
    const due = inViewedMonth ? today : new Date(this.year(), this.monthIndex() + 1, 0);
    const pad = (value: number) => String(value).padStart(2, '0');
    return `${due.getFullYear()}-${pad(due.getMonth() + 1)}-${pad(due.getDate())}`;
  }

  protected toggleItem(id: string): void {
    this.openItemId.update((current) => (current === id ? null : id));
  }

  protected draft(id: string): FollowupDraft {
    return this.drafts()[id] ?? { ownerUserId: null, dueDate: '', comment: '' };
  }

  protected patchDraft(id: string, patch: Partial<FollowupDraft>): void {
    this.drafts.update((current) => ({
      ...current,
      [id]: {
        ...(current[id] ?? { ownerUserId: null, dueDate: '', comment: '' }),
        ...patch,
      },
    }));
  }

  protected openModule(item: FinalizationChecklistItem): void {
    if (!item.route) return;
    const year = this.year();
    const month = this.monthIndex() + 1;
    const last = new Date(year, month, 0).getDate();
    const pad = (value: number) => String(value).padStart(2, '0');
    void this.router.navigate([item.route], {
      queryParams: {
        year,
        month,
        from: `${year}-${pad(month)}-01`,
        to: `${year}-${pad(month)}-${pad(last)}`,
      },
    });
  }

  protected saveFollowup(item: FinalizationChecklistItem): void {
    const draft = this.draft(item.id);
    const body: FinalizationFollowupWrite = {
      year: this.year(),
      month: this.monthIndex() + 1,
      checklistId: item.id,
      ownerUserId: draft.ownerUserId,
      dueDate: draft.dueDate || null,
      comment: draft.comment,
    };
    this.savingId.set(item.id);
    this.api.saveFinalizationFollowup(body).subscribe({
      next: (updated) => {
        this.zone.run(() => {
          this.checklist.update((items) => items.map((entry) => (entry.id === updated.id ? updated : entry)));
          this.savingId.set(null);
          this.snackBar.open('Follow-up saved. Checklist completion still comes from attendance records.', 'OK', {
            duration: 2800,
          });
          this.cdr.markForCheck();
        });
      },
      error: (err: unknown) => {
        this.zone.run(() => {
          this.savingId.set(null);
          this.snackBar.open(problem(err, 'Could not save the follow-up.'), 'OK', { duration: 4000 });
          this.cdr.markForCheck();
        });
      },
    });
  }

  protected remind(item?: FinalizationChecklistItem): void {
    const label = item ? item.label : 'every open checklist item';
    confirmAction(this.dialog, {
      title: item ? 'Send reminder?' : 'Remind all open items?',
      message: `This records a reminder for ${label}. It does not approve requests or resolve exceptions. A reminder already recorded today for the same person is skipped.`,
      confirmText: item ? 'Send Reminder' : 'Remind All',
    })
      .pipe(filter(Boolean))
      .subscribe(() => {
        this.reminding.set(true);
        this.api
          .remindFinalization({
            year: this.year(),
            month: this.monthIndex() + 1,
            checklistId: item?.id ?? null,
          })
          .subscribe({
            next: (result) => {
              this.zone.run(() => {
                this.reminding.set(false);
                this.snackBar.open(result.message, 'OK', { duration: 4500 });
                this.reload();
              });
            },
            error: (err: unknown) => {
              this.zone.run(() => {
                this.reminding.set(false);
                this.snackBar.open(problem(err, 'Could not send reminders.'), 'OK', { duration: 4000 });
                this.cdr.markForCheck();
              });
            },
          });
      });
  }

  protected statusClass(status: FinalizationRowStatus): string {
    switch (status) {
      case 'Ready':
        return 'status ready';
      case 'Review':
        return 'status review';
      case 'Pending':
        return 'status pending';
    }
  }

  protected statusIcon(status: FinalizationRowStatus): string {
    switch (status) {
      case 'Ready':
        return 'check_circle';
      case 'Review':
        return 'schedule';
      case 'Pending':
        return 'hourglass_empty';
    }
  }

  protected readinessTone(value: number): string {
    if (value >= 90) return 'high';
    if (value >= 80) return 'mid';
    return 'low';
  }

  private reload(): void {
    this.loading.set(true);
    this.error.set('');
    const groupBy: FinalizationGroupBy =
      this.contentTab() === 'department' ? 'department' : 'location';
    this.api
      .finalization({
        year: this.year(),
        month: this.monthIndex() + 1,
        groupBy,
      })
      .subscribe({
        next: (page) => {
          this.zone.run(() => {
            this.kpi.set(page.kpi);
            this.summary.set(page.summary);
            this.checklist.set(page.checklist);
            this.groups.set(page.groups);
            this.assignees.set(page.assignees ?? []);
            this.drafts.set(draftsFrom(page.checklist));
            this.canFinalize.set(page.canFinalize);
            this.isFinalized.set(page.isFinalized);
            this.loading.set(false);
            this.cdr.markForCheck();
          });
        },
        error: (err: unknown) => {
          this.zone.run(() => {
            this.loading.set(false);
            this.kpi.set(EMPTY_KPI);
            this.summary.set(null);
            this.checklist.set([]);
            this.groups.set([]);
            this.assignees.set([]);
            this.drafts.set({});
            this.canFinalize.set(false);
            this.isFinalized.set(false);
            this.error.set(problem(err, 'Attendance finalization could not be loaded.'));
            this.cdr.markForCheck();
          });
        },
      });
  }
}

function taskTitle(id: string): string {
  switch (id) {
    case 'processed':
      return 'Attendance Processing';
    case 'exceptions':
      return 'Exception Review';
    case 'regularization':
      return 'Regularization Approval';
    case 'ready':
      return 'Department Verification';
    case 'pending':
      return 'Attendance Data Validation';
    default:
      return id;
  }
}

function formatDue(iso: string): string {
  const [year, month, day] = iso.split('-').map(Number);
  if (!year || !month || !day) return iso;
  return new Intl.DateTimeFormat('en-GB', {
    day: '2-digit',
    month: 'short',
    year: 'numeric',
  }).format(new Date(year, month - 1, day));
}

function draftsFrom(items: FinalizationChecklistItem[]): Record<string, FollowupDraft> {
  return Object.fromEntries(
    items.map((item) => [
      item.id,
      {
        ownerUserId: item.ownerUserId,
        dueDate: item.dueDate ?? '',
        comment: item.comment ?? '',
      },
    ]),
  );
}

interface FollowupDraft {
  ownerUserId: number | null;
  dueDate: string;
  comment: string;
}

function csv(value: string): string {
  if (/[",\n]/.test(value)) return `"${value.replace(/"/g, '""')}"`;
  return value;
}

function problem(error: unknown, fallback: string): string {
  const detail = (error as { error?: { detail?: string; title?: string } })?.error;
  if (typeof detail?.detail === 'string' && detail.detail) return detail.detail;
  if (typeof detail?.title === 'string' && detail.title) return detail.title;
  return fallback;
}
