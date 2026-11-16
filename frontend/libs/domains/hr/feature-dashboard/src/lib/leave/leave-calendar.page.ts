import { DecimalPipe } from '@angular/common';
import { ChangeDetectionStrategy, Component, computed, DestroyRef, inject, signal, viewChild } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { MatButton, MatIconButton } from '@angular/material/button';
import { MatFormField, MatLabel, MatPrefix } from '@angular/material/form-field';
import { MatIcon } from '@angular/material/icon';
import { MatInput } from '@angular/material/input';
import { MatOption, MatSelect } from '@angular/material/select';
import { MatDrawer, MatDrawerContainer, MatDrawerContent } from '@angular/material/sidenav';
import { MatSnackBar } from '@angular/material/snack-bar';
import { RouterLink } from '@angular/router';
import {
  EmployeeLeaveOption,
  LeaveApi,
  LeaveCalendarBoard,
  LeaveCalendarTypeOption,
} from '@trishul/hr-data-access';
import { PageHeader, StatusBadge } from '@trishul/shared-ui';
import {
  CalendarHoliday,
  CalendarLeaveEntry,
  CalendarViewMode,
  EmployeeCalendarInfo,
  LeaveCalendarSummary,
} from './leave-calendar.models';

const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
const MONTH_NAMES = ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December'];
const WEEKDAYS = ['Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday'];
const COLORS = ['#7C4DFF', '#2E7D32', '#EF6C00', '#C2185B', '#1565C0', '#00838F', '#6A1B9A', '#455A64'];
const TONES = new Set(['cl', 'el', 'sl', 'co']);
const EMPTY_SUMMARY: LeaveCalendarSummary = {
  totalEmployees: 0, onLeaveToday: 0, onLeavePercent: 0, pendingApproval: 0, approvedMtd: 0, rejectedMtd: 0, upcomingLeaves: 0,
};

interface CalendarEntryView extends CalendarLeaveEntry {
  employee: EmployeeCalendarInfo;
}

interface CalendarCell {
  date: Date;
  iso: string;
  inMonth: boolean;
  isToday: boolean;
  isSelected: boolean;
  holiday: CalendarHoliday | null;
  entries: CalendarEntryView[];
}

@Component({
  selector: 'trishul-leave-calendar-page',
  imports: [
    DecimalPipe, FormsModule, MatButton, MatDrawer, MatDrawerContainer, MatDrawerContent, MatFormField, MatIcon,
    MatIconButton, MatInput, MatLabel, MatOption, MatPrefix, MatSelect, PageHeader, RouterLink, StatusBadge,
  ],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './leave-calendar.page.html',
  styleUrl: './leave-calendar.page.scss',
})
export class LeaveCalendarPage {
  private readonly api = inject(LeaveApi);
  private readonly snack = inject(MatSnackBar);
  private readonly drawer = viewChild.required<MatDrawer>('drawer');
  private readonly destroyRef = inject(DestroyRef);
  private loadToken = 0;

  protected readonly weekdays = WEEKDAYS;
  protected readonly modes: { id: CalendarViewMode; label: string }[] = [
    { id: 'month', label: 'Month' },
    { id: 'week', label: 'Week' },
    { id: 'day', label: 'Day' },
  ];
  protected readonly legend = [
    { tone: 'cl', label: 'Casual Leave' },
    { tone: 'el', label: 'Earned Leave' },
    { tone: 'sl', label: 'Sick Leave' },
    { tone: 'co', label: 'Comp-Off' },
    { tone: 'pending', label: 'Pending' },
    { tone: 'holiday', label: 'Holiday' },
  ];
  protected readonly severities = { Pending: 'warn', Approved: 'success', Rejected: 'danger' } as const;

  protected readonly cursor = signal(new Date(new Date().getFullYear(), new Date().getMonth(), 1));
  protected readonly selected = signal(strip(new Date()));
  protected readonly view = signal<CalendarViewMode>('month');
  protected readonly department = signal<number | null>(null);
  protected readonly designation = signal<number | null>(null);
  protected readonly location = signal<number | null>(null);
  protected readonly leaveType = signal<number | null>(null);
  protected readonly search = signal('');
  protected readonly active = signal<CalendarEntryView | null>(null);
  protected readonly summary = signal<LeaveCalendarSummary>(EMPTY_SUMMARY);
  protected readonly entries = signal<CalendarEntryView[]>([]);
  protected readonly holidays = signal<CalendarHoliday[]>([]);
  protected readonly departments = signal<EmployeeLeaveOption[]>([]);
  protected readonly designations = signal<EmployeeLeaveOption[]>([]);
  protected readonly locations = signal<EmployeeLeaveOption[]>([]);
  protected readonly leaveTypes = signal<LeaveCalendarTypeOption[]>([]);
  protected readonly error = signal('');

  protected readonly monthKey = computed(() => monthId(this.cursor()));
  protected readonly months = computed(() => Array.from({ length: 13 }, (_, index) => {
    const date = new Date(this.cursor().getFullYear(), this.cursor().getMonth() - 6 + index, 1);
    return { id: monthId(date), label: `${MONTH_NAMES[date.getMonth()]} ${date.getFullYear()}` };
  }));
  protected readonly cells = computed(() => buildCells(this.cursor(), this.view(), this.selected(), this.entries(), this.holidays()));
  protected readonly chipLimit = computed(() => (this.view() === 'week' ? 4 : 2));
  protected readonly selectedEntries = computed(() => entriesOn(iso(this.selected()), this.entries()));
  protected readonly selectedConfirmed = computed(() => this.selectedEntries().filter((entry) => entry.status === 'Approved'));
  protected readonly selectedPending = computed(() => this.selectedEntries().filter((entry) => entry.status === 'Pending'));
  protected readonly selectedHoliday = computed(() => this.holidays().find((holiday) => holiday.date === iso(this.selected())) ?? null);
  protected readonly upcoming = computed(() => {
    const today = iso(strip(new Date()));
    const end = iso(addDays(strip(new Date()), 7));
    return this.entries()
      .filter((entry) => entry.status === 'Approved' && entry.fromDate > today && entry.fromDate <= end)
      .sort((a, b) => a.fromDate.localeCompare(b.fromDate) || a.employee.name.localeCompare(b.employee.name));
  });

  constructor() {
    this.reload();
    this.destroyRef.onDestroy(() => this.loadToken++);
  }

  protected setDepartment(value: number | null): void {
    this.department.set(value);
    this.reload();
  }

  protected setDesignation(value: number | null): void {
    this.designation.set(value);
    this.reload();
  }

  protected setLocation(value: number | null): void {
    this.location.set(value);
    this.reload();
  }

  protected setLeaveType(value: number | null): void {
    this.leaveType.set(value);
    this.reload();
  }

  protected setSearch(value: string): void {
    this.search.set(value);
    this.reload();
  }

  protected setMonth(key: string): void {
    const [year, month] = key.split('-').map(Number);
    const day = Math.min(this.selected().getDate(), new Date(year, month, 0).getDate());
    this.cursor.set(new Date(year, month - 1, 1));
    this.selected.set(new Date(year, month - 1, day));
    this.reload();
  }

  protected step(direction: -1 | 1): void {
    if (this.view() === 'day') this.moveSelected(direction);
    else if (this.view() === 'week') this.moveSelected(direction * 7);
    else this.shiftMonth(direction);
    this.reload();
  }

  protected stepLabel(direction: -1 | 1): string {
    const unit = this.view() === 'day' ? 'day' : this.view() === 'week' ? 'week' : 'month';
    return `${direction < 0 ? 'Previous' : 'Next'} ${unit}`;
  }

  protected goToday(): void {
    const today = strip(new Date());
    this.selected.set(today);
    this.cursor.set(new Date(today.getFullYear(), today.getMonth(), 1));
    this.reload();
  }

  protected selectDate(date: Date): void {
    const day = strip(date);
    const monthChanged = day.getMonth() !== this.cursor().getMonth() || day.getFullYear() !== this.cursor().getFullYear();
    this.selected.set(day);
    if (monthChanged) {
      this.cursor.set(new Date(day.getFullYear(), day.getMonth(), 1));
      this.reload();
    }
  }

  protected choose(entry: CalendarEntryView, date: Date, event: Event): void {
    event.stopPropagation();
    this.selectDate(date);
    this.open(entry);
  }

  protected open(entry: CalendarEntryView): void {
    this.active.set(entry);
    void this.drawer().open();
  }

  protected close(): void {
    void this.drawer().close();
  }

  protected reset(): void {
    this.department.set(null);
    this.designation.set(null);
    this.location.set(null);
    this.leaveType.set(null);
    this.search.set('');
    this.reload();
  }

  protected exportRows(): void {
    const [year, month] = this.monthKey().split('-').map(Number);
    const start = iso(new Date(year, month - 1, 1));
    const end = iso(new Date(year, month, 0));
    const rows = this.entries().filter((entry) => entry.fromDate <= end && entry.toDate >= start);
    const header = ['Request', 'Employee ID', 'Employee', 'Department', 'Designation', 'Location', 'Leave Type', 'From', 'To', 'Days', 'Status', 'Approved By', 'Reason'];
    const lines = rows.map((entry) => [
      entry.id, entry.employee.code, entry.employee.name, entry.employee.department, entry.employee.designation,
      entry.employee.location, entry.leaveType, entry.fromDate, entry.toDate, String(entry.days), entry.status,
      entry.approvedBy ?? '', entry.reason,
    ].map(csv).join(','));
    const blob = new Blob([[header.join(','), ...lines].join('\n')], { type: 'text/csv' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = `leave-calendar-${this.monthKey()}.csv`;
    link.click();
    URL.revokeObjectURL(url);
    this.snack.open(`Exported ${rows.length} leave rows.`, 'Close', { duration: 2500 });
  }

  protected when(value: Date | string): string {
    if (typeof value === 'string') {
      const [year, month, day] = value.split('-');
      return `${day}-${MONTHS[Number(month) - 1]}-${year}`;
    }
    return `${String(value.getDate()).padStart(2, '0')}-${MONTHS[value.getMonth()]}-${value.getFullYear()}`;
  }

  protected span(entry: CalendarLeaveEntry): string {
    const from = this.when(entry.fromDate);
    const to = this.when(entry.toDate);
    return from === to ? from : `${from} – ${to}`;
  }

  protected tone(entry: CalendarLeaveEntry): string {
    if (entry.status === 'Pending') return 'pending';
    const code = entry.leaveCode.toLowerCase();
    return TONES.has(code) ? code : 'other';
  }

  protected dayLabel(days: number): string {
    return `${days} day${days === 1 ? '' : 's'}`;
  }

  private reload(): void {
    const token = ++this.loadToken;
    const cursor = this.cursor();
    this.api.leaveCalendar({
      year: cursor.getFullYear(),
      month: cursor.getMonth() + 1,
      departmentId: this.department(),
      designationId: this.designation(),
      branchId: this.location(),
      leaveTypeId: this.leaveType(),
      search: this.search().trim(),
    }).subscribe({
      next: (board) => {
        if (token !== this.loadToken) return;
        this.apply(board);
        this.error.set('');
      },
      error: (error: unknown) => {
        if (token !== this.loadToken) return;
        this.error.set(problemDetail(error, 'The leave calendar could not be loaded.'));
      },
    });
  }

  private apply(board: LeaveCalendarBoard): void {
    this.summary.set({
      totalEmployees: board.summary.totalEmployees,
      onLeaveToday: board.summary.onLeaveToday,
      onLeavePercent: Number(board.summary.onLeavePercent),
      pendingApproval: board.summary.pendingApproval,
      approvedMtd: board.summary.approvedMtd,
      rejectedMtd: board.summary.rejectedMtd,
      upcomingLeaves: board.summary.upcomingLeaves,
    });
    this.entries.set(board.entries.map(toEntry));
    this.holidays.set(board.holidays.map((holiday) => ({ date: holiday.holidayDate, name: holiday.name })));
    this.departments.set(board.departments);
    this.designations.set(board.designations);
    this.locations.set(board.locations);
    this.leaveTypes.set(board.leaveTypes);
  }

  private shiftMonth(direction: -1 | 1): void {
    const cursor = this.cursor();
    const next = new Date(cursor.getFullYear(), cursor.getMonth() + direction, 1);
    const day = Math.min(this.selected().getDate(), new Date(next.getFullYear(), next.getMonth() + 1, 0).getDate());
    this.cursor.set(next);
    this.selected.set(new Date(next.getFullYear(), next.getMonth(), day));
  }

  private moveSelected(days: number): void {
    const next = addDays(this.selected(), days);
    this.selected.set(next);
    this.cursor.set(new Date(next.getFullYear(), next.getMonth(), 1));
  }
}

function toEntry(row: LeaveCalendarBoard['entries'][number]): CalendarEntryView {
  const employee = row.employee;
  return {
    id: row.displayId,
    employeeId: employee.employeeId,
    leaveCode: row.leaveCode,
    leaveType: row.leaveType,
    fromDate: row.fromDate,
    toDate: row.toDate,
    days: Number(row.days),
    status: row.status,
    reason: row.reason ?? '',
    approvedBy: row.approvedBy,
    employee: {
      employeeId: employee.employeeId,
      code: employee.code,
      name: employee.name,
      department: employee.department ?? '',
      designation: employee.designation ?? '',
      location: employee.location ?? '',
      initials: initials(employee.name),
      color: colorFor(employee.code),
    },
  };
}

function buildCells(
  cursor: Date, view: CalendarViewMode, selected: Date, entries: CalendarEntryView[], holidays: CalendarHoliday[],
): CalendarCell[] {
  const today = iso(strip(new Date()));
  const selectedKey = iso(selected);
  return datesFor(cursor, view, selected).map((date) => {
    const key = iso(date);
    return {
      date,
      iso: key,
      inMonth: date.getMonth() === cursor.getMonth() && date.getFullYear() === cursor.getFullYear(),
      isToday: key === today,
      isSelected: key === selectedKey,
      holiday: holidays.find((holiday) => holiday.date === key) ?? null,
      entries: entriesOn(key, entries),
    };
  });
}

function entriesOn(key: string, entries: CalendarEntryView[]): CalendarEntryView[] {
  return entries
    .filter((entry) => entry.status !== 'Rejected' && entry.fromDate <= key && key <= entry.toDate)
    .sort((a, b) => Number(a.status === 'Pending') - Number(b.status === 'Pending') || a.employee.name.localeCompare(b.employee.name));
}

function datesFor(cursor: Date, view: CalendarViewMode, selected: Date): Date[] {
  if (view === 'day') return [strip(selected)];
  if (view === 'week') {
    const start = addDays(selected, -selected.getDay());
    return Array.from({ length: 7 }, (_, index) => addDays(start, index));
  }
  const first = new Date(cursor.getFullYear(), cursor.getMonth(), 1);
  const start = addDays(first, -first.getDay());
  const days = Array.from({ length: 42 }, (_, index) => addDays(start, index));
  const trailing = days.slice(35);
  return trailing.every((day) => day.getMonth() !== cursor.getMonth()) ? days.slice(0, 35) : days;
}

function strip(value: Date): Date {
  return new Date(value.getFullYear(), value.getMonth(), value.getDate());
}

function addDays(value: Date, days: number): Date {
  const next = strip(value);
  next.setDate(next.getDate() + days);
  return next;
}

function iso(value: Date): string {
  const month = String(value.getMonth() + 1).padStart(2, '0');
  const day = String(value.getDate()).padStart(2, '0');
  return `${value.getFullYear()}-${month}-${day}`;
}

function monthId(value: Date): string {
  return `${value.getFullYear()}-${String(value.getMonth() + 1).padStart(2, '0')}`;
}

function csv(value: string): string {
  return `"${value.replaceAll('"', '""')}"`;
}

function initials(name: string): string {
  const parts = name.split(' ').filter(Boolean);
  return ((parts[0]?.[0] ?? '') + (parts[1]?.[0] ?? '')).toUpperCase();
}

function colorFor(code: string): string {
  const total = [...code].reduce((sum, char) => sum + char.charCodeAt(0), 0);
  return COLORS[total % COLORS.length];
}

function problemDetail(error: unknown, fallback: string): string {
  const detail = (error as { error?: { detail?: string } }).error?.detail;
  return typeof detail === 'string' && detail ? detail : fallback;
}
