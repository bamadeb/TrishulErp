import { DecimalPipe } from '@angular/common';
import {
  ChangeDetectionStrategy,
  Component,
  computed,
  inject,
  OnInit,
  signal,
} from '@angular/core';
import { FormsModule } from '@angular/forms';
import { MatButton, MatIconButton } from '@angular/material/button';
import { MatCheckbox } from '@angular/material/checkbox';
import { MatDialog } from '@angular/material/dialog';
import { MatFormField, MatPrefix } from '@angular/material/form-field';
import { MatIcon } from '@angular/material/icon';
import { MatInput } from '@angular/material/input';
import { MatMenu, MatMenuItem, MatMenuTrigger } from '@angular/material/menu';
import { MatOption, MatSelect } from '@angular/material/select';
import { MatSlideToggle } from '@angular/material/slide-toggle';
import { MatSnackBar } from '@angular/material/snack-bar';
import { MatTooltip } from '@angular/material/tooltip';
import { RouterLink } from '@angular/router';
import { AuthStore, HasPermission } from '@trishul/core-auth';
import {
  ATTENDANCE_RULES_MANAGE_PERMISSION,
  ATTENDANCE_SHIFT_MANAGE_PERMISSION,
  AttendanceApi,
  AttendanceHolidayItem,
  AttendanceRules,
  LeaveYearInfo,
  ShiftAssignmentItem,
  ShiftAssignmentOptions,
  ShiftItem,
  WeekdayCode,
} from '@trishul/hr-data-access';
import { confirmAction, PageHeader } from '@trishul/shared-ui';
import { forkJoin } from 'rxjs';
import { AttendanceRulesEditDialog } from './attendance-rules-edit.dialog';
import { RulesTab } from './attendance.models';
import { ShiftAssignmentDialog } from './shift-assignment.dialog';
import { ShiftFormDialog } from './shift-form.dialog';

interface RuleBlock {
  id: string;
  title: string;
  icon: string;
  tone: string;
  items: { label: string; value: string; accent?: 'success' | 'link' | 'neutral' }[];
  note?: string;
}

const WEEKDAY_LABEL: Record<WeekdayCode, string> = {
  MON: 'Monday',
  TUE: 'Tuesday',
  WED: 'Wednesday',
  THU: 'Thursday',
  FRI: 'Friday',
  SAT: 'Saturday',
  SUN: 'Sunday',
};

const CODE_TONES = ['#2563eb', '#7c3aed', '#ea580c', '#6366f1', '#0891b2', '#db2777', '#1d4ed8', '#64748b'];

function ordinal(day: number): string {
  const mod100 = day % 100;
  if (mod100 >= 11 && mod100 <= 13) return `${day}th`;
  if (day % 10 === 1) return `${day}st`;
  if (day % 10 === 2) return `${day}nd`;
  if (day % 10 === 3) return `${day}rd`;
  return `${day}th`;
}

/** Shift & Attendance Rules — API-backed (hr.shift, system_setting, employee_shift, holiday). */
@Component({
  selector: 'trishul-attendance-rules-page',
  imports: [
    DecimalPipe,
    FormsModule,
    HasPermission,
    MatButton,
    MatCheckbox,
    MatFormField,
    MatIcon,
    MatIconButton,
    MatInput,
    MatMenu,
    MatMenuItem,
    MatMenuTrigger,
    MatOption,
    MatPrefix,
    MatSelect,
    MatSlideToggle,
    MatTooltip,
    PageHeader,
    RouterLink,
  ],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './attendance-rules.page.html',
  styleUrl: './attendance-rules.page.scss',
})
export class AttendanceRulesPage implements OnInit {
  private readonly api = inject(AttendanceApi);
  private readonly auth = inject(AuthStore);
  private readonly dialog = inject(MatDialog);
  private readonly snackBar = inject(MatSnackBar);

  protected readonly shiftManage = ATTENDANCE_SHIFT_MANAGE_PERMISSION;
  protected readonly rulesManage = ATTENDANCE_RULES_MANAGE_PERMISSION;
  protected readonly canManageShifts = this.auth.hasPermission(ATTENDANCE_SHIFT_MANAGE_PERMISSION);
  protected readonly canManageRules = this.auth.hasPermission(ATTENDANCE_RULES_MANAGE_PERMISSION);

  protected readonly contentTab = signal<RulesTab>('shifts');
  protected readonly loading = signal(false);
  protected readonly error = signal('');

  protected readonly shifts = signal<ShiftItem[]>([]);
  protected readonly shiftSummary = signal({ total: 0, active: 0, inactive: 0 });
  protected readonly search = signal('');
  protected readonly status = signal<'Active' | 'Inactive' | ''>('');
  protected readonly selectedIds = signal<Set<number>>(new Set());
  protected readonly menuShift = signal<ShiftItem | null>(null);

  protected readonly rules = signal<AttendanceRules | null>(null);
  protected readonly leaveYear = signal<LeaveYearInfo | null>(null);

  protected readonly assignments = signal<ShiftAssignmentItem[]>([]);
  protected readonly showAssignmentHistory = signal(false);
  protected readonly assignmentSearch = signal('');
  protected readonly assignmentOptions = signal<ShiftAssignmentOptions | null>(null);

  protected readonly holidays = signal<AttendanceHolidayItem[]>([]);
  protected readonly holidayError = signal('');

  protected readonly overnightCount = computed(
    () => this.shifts().filter((row) => row.isOvernight).length,
  );

  protected readonly filteredShifts = computed(() => {
    const q = this.search().trim().toLowerCase();
    const status = this.status();
    return this.shifts().filter((row) => {
      if (status === 'Active' && !row.isActive) return false;
      if (status === 'Inactive' && row.isActive) return false;
      if (!q) return true;
      return `${row.code} ${row.name}`.toLowerCase().includes(q);
    });
  });

  protected readonly ruleBlocks = computed<RuleBlock[]>(() => {
    const rules = this.rules();
    if (!rules) return [];
    const offs = rules.weeklyOffDays.map((d) => WEEKDAY_LABEL[d]).join(', ') || 'None';
    const graceDays = rules.graceDaysPerMonth || 3;
    const graceMinutes = rules.lateArrivalGraceMinutes;
    return [
      {
        id: 'hours',
        title: 'Working Hours',
        icon: 'schedule',
        tone: 'blue',
        items: [
          { label: 'Standard Work Duration', value: `${rules.standardWorkHours} Hours / Day` },
          { label: 'Working Days', value: `${rules.workingDaysPerWeek} Days / Week` },
        ],
      },
      {
        id: 'grace',
        title: 'Grace Time',
        icon: 'hourglass_empty',
        tone: 'amber',
        items: [
          { label: 'Late Arrival Grace', value: `${graceMinutes} Minutes` },
          { label: 'Grace Days', value: `${graceDays} Days / Employee / Month` },
          { label: 'Salary On Grace Days', value: 'No deduction', accent: 'success' },
          { label: 'From The Next Late Day', value: 'Half-day salary deduction' },
          { label: 'Early Exit Grace', value: `${rules.earlyExitGraceMinutes} Minutes` },
        ],
        note: `Each employee gets ${graceMinutes} minutes of grace on ${graceDays} days per calendar month. Those ${graceDays} days have no salary deduction. From the ${ordinal(graceDays + 1)} late-arrival day onwards, half-day salary deduction applies. Grace usage is tracked employee-wise and month-wise. Late arrivals and deductions are retained for payroll.`,
      },
      {
        id: 'ot',
        title: 'Overtime (OT)',
        icon: 'layers',
        tone: 'violet',
        items: [
          { label: 'OT Calculation', value: `After ${rules.otAfterHours} Hours` },
          {
            label: 'OT Approval',
            value: rules.otApprovalRequired ? 'Required' : 'Not required',
            accent: rules.otApprovalRequired ? 'success' : 'neutral',
          },
        ],
      },
      {
        id: 'off',
        title: 'Weekly Off',
        icon: 'event_busy',
        tone: 'slate',
        items: [
          { label: 'Weekly Off Days', value: offs },
          { label: 'Applies To', value: rules.weeklyOffAppliesTo },
        ],
      },
      {
        id: 'holidays',
        title: 'Holidays',
        icon: 'celebration',
        tone: 'pink',
        items: [
          { label: 'Holiday Calendar', value: rules.leaveYearLabel },
          {
            label: 'Total Holidays',
            value: `${rules.holidayCount} Days`,
            accent: 'link',
          },
        ],
      },
      {
        id: 'marking',
        title: 'Attendance Marking',
        icon: 'verified_user',
        tone: 'green',
        items: [
          {
            label: 'Auto Attendance (App)',
            value: rules.autoAttendanceEnabled ? 'Enabled' : 'Disabled',
            accent: rules.autoAttendanceEnabled ? 'success' : 'neutral',
          },
          {
            label: 'Manual Attendance (With Approval)',
            value: rules.manualAttendanceEnabled ? 'Enabled' : 'Disabled',
            accent: rules.manualAttendanceEnabled ? 'success' : 'neutral',
          },
        ],
      },
    ];
  });

  protected readonly filteredAssignments = computed(() => {
    const q = this.assignmentSearch().trim().toLowerCase();
    return this.assignments().filter((row) => {
      if (!q) return true;
      return `${row.employeeCode} ${row.employeeName} ${row.department} ${row.shiftCode} ${row.shiftName}`
        .toLowerCase()
        .includes(q);
    });
  });

  protected readonly allSelected = computed(() => {
    const rows = this.filteredShifts();
    return rows.length > 0 && rows.every((row) => this.selectedIds().has(row.id));
  });

  protected readonly someSelected = computed(() => {
    const rows = this.filteredShifts();
    const selected = rows.filter((row) => this.selectedIds().has(row.id)).length;
    return selected > 0 && selected < rows.length;
  });

  ngOnInit(): void {
    this.reloadAll();
  }

  protected setTab(tab: RulesTab): void {
    this.contentTab.set(tab);
    if (tab === 'holidays') this.reloadHolidays();
    if (tab === 'assignment') this.reloadAssignments();
    if (tab === 'rules') this.reloadRules();
  }

  protected onSearch(value: string): void {
    this.search.set(value);
  }

  protected onStatus(value: 'Active' | 'Inactive' | ''): void {
    this.status.set(value);
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
      for (const row of this.filteredShifts()) {
        if (checked) next.add(row.id);
        else next.delete(row.id);
      }
      return next;
    });
  }

  protected refresh(): void {
    this.reloadAll();
  }

  protected exportExcel(): void {
    const rows = this.filteredShifts();
    if (!rows.length) {
      this.snackBar.open('No shifts to export.', 'OK', { duration: 2000 });
      return;
    }
    const header = ['Code', 'Name', 'In', 'Out', 'Work Hours', 'Grace', 'Status'];
    const lines = [
      header.join(','),
      ...rows.map((row) =>
        [
          row.code,
          csv(row.name),
          formatTime(row.startTime),
          formatTime(row.endTime),
          row.workHours,
          row.graceMinutes,
          row.isActive ? 'Active' : 'Inactive',
        ].join(','),
      ),
    ];
    const blob = new Blob([lines.join('\n')], { type: 'text/csv;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'shifts.csv';
    a.click();
    URL.revokeObjectURL(url);
    this.snackBar.open(`Exported ${rows.length} shift(s).`, 'OK', { duration: 2200 });
  }

  protected addShift(): void {
    if (!this.canManageShifts) return;
    this.openShiftDialog('add', null);
  }

  protected editShift(row?: ShiftItem | null): void {
    if (!this.canManageShifts) return;
    const target = row ?? this.menuShift();
    if (!target) return;
    this.openShiftDialog('edit', target);
  }

  protected deleteShift(row?: ShiftItem | null): void {
    if (!this.canManageShifts) return;
    const target = row ?? this.menuShift();
    if (!target) return;
    confirmAction(this.dialog, {
      title: 'Deactivate shift',
      message: `Deactivate ${target.name}? Existing assignment history is kept.`,
      confirmText: 'Deactivate',
    }).subscribe((ok) => {
      if (!ok) return;
      this.api.deleteShift(target.id, target.rowVersion).subscribe({
        next: () => {
          this.snackBar.open('Shift deactivated.', 'OK', { duration: 2200 });
          this.reloadShifts();
        },
        error: (err: unknown) => this.snackBar.open(problem(err, 'Could not deactivate shift.'), 'OK', { duration: 3500 }),
      });
    });
  }

  protected activateShift(row?: ShiftItem | null): void {
    if (!this.canManageShifts) return;
    const target = row ?? this.menuShift();
    if (!target) return;
    this.api
      .updateShift(target.id, target.rowVersion, {
        code: target.code,
        name: target.name,
        startTime: target.startTime,
        endTime: target.endTime,
        graceMinutes: target.graceMinutes,
        halfDayHours: target.halfDayHours,
        isActive: true,
      })
      .subscribe({
        next: () => {
          this.snackBar.open('Shift activated.', 'OK', { duration: 2200 });
          this.reloadShifts();
        },
        error: (err: unknown) => this.snackBar.open(problem(err, 'Could not activate shift.'), 'OK', { duration: 3500 }),
      });
  }

  protected editRules(): void {
    if (!this.canManageRules) return;
    const current = this.rules();
    if (!current) return;
    this.dialog
      .open(AttendanceRulesEditDialog, { data: current, width: '40rem' })
      .afterClosed()
      .subscribe((body) => {
        if (!body) return;
        this.api.saveRules(body, current.rowVersion).subscribe({
          next: (saved) => {
            this.rules.set(saved);
            this.snackBar.open('Attendance rules saved.', 'OK', { duration: 2500 });
          },
          error: (err: unknown) =>
            this.snackBar.open(problem(err, 'Could not save attendance rules.'), 'OK', { duration: 4000 }),
        });
      });
  }

  protected addAssignment(): void {
    if (!this.canManageShifts) return;
    this.ensureOptions(() => this.openAssignmentDialog('add', null));
  }

  protected editAssignment(row: ShiftAssignmentItem): void {
    if (!this.canManageShifts) return;
    this.ensureOptions(() => this.openAssignmentDialog('edit', row));
  }

  protected endAssignment(row: ShiftAssignmentItem): void {
    if (!this.canManageShifts) return;
    confirmAction(this.dialog, {
      title: 'End assignment',
      message: `End the ${row.shiftCode} assignment for ${row.employeeName}? History is preserved.`,
      confirmText: 'End',
    }).subscribe((ok) => {
      if (!ok) return;
      this.api.deleteShiftAssignment(row.id, row.rowVersion).subscribe({
        next: () => {
          this.snackBar.open('Assignment ended.', 'OK', { duration: 2200 });
          this.reloadAssignments();
        },
        error: (err: unknown) =>
          this.snackBar.open(problem(err, 'Could not end assignment.'), 'OK', { duration: 3500 }),
      });
    });
  }

  protected onHistoryToggle(checked: boolean): void {
    this.showAssignmentHistory.set(checked);
    this.reloadAssignments();
  }

  protected formatTime = formatTime;
  protected formatDate = formatDate;
  protected codeTone = codeTone;
  protected avatarTone = avatarTone;

  protected initials(name: string): string {
    return name
      .split(/\s+/)
      .slice(0, 2)
      .map((part) => part[0]?.toUpperCase() ?? '')
      .join('');
  }

  protected statusClass(active: boolean): string {
    return active ? 'status active' : 'status inactive';
  }

  protected holidayType(category: string): string {
    return category === 'Regional' ? 'Restricted' : category;
  }

  protected appliesTo(row: AttendanceHolidayItem): string {
    return row.appliesTo || 'All Employees';
  }

  private openShiftDialog(mode: 'add' | 'edit', shift: ShiftItem | null): void {
    this.dialog
      .open(ShiftFormDialog, { data: { mode, shift }, width: '26rem', maxHeight: 'none' })
      .afterClosed()
      .subscribe((body) => {
        if (!body) return;
        const req =
          mode === 'edit' && shift
            ? this.api.updateShift(shift.id, shift.rowVersion, body)
            : this.api.createShift(body);
        req.subscribe({
          next: () => {
            this.snackBar.open(mode === 'edit' ? 'Shift updated.' : 'Shift created.', 'OK', {
              duration: 2200,
            });
            this.reloadShifts();
          },
          error: (err: unknown) =>
            this.snackBar.open(problem(err, 'Could not save shift.'), 'OK', { duration: 4000 }),
        });
      });
  }

  private openAssignmentDialog(mode: 'add' | 'edit', assignment: ShiftAssignmentItem | null): void {
    const options = this.assignmentOptions();
    const rules = this.rules();
    if (!options) return;
    this.dialog
      .open(ShiftAssignmentDialog, {
        width: '34rem',
        data: {
          mode,
          assignment,
          employees: options.employees,
          shifts: options.shifts,
          defaultWeeklyOff: rules?.weeklyOffDays ?? ['SUN'],
        },
      })
      .afterClosed()
      .subscribe((result) => {
        if (!result) return;
        const done = (message: string) => {
          this.snackBar.open(message, 'OK', { duration: 2200 });
          this.reloadAssignments();
        };
        const failed = (err: unknown) =>
          this.snackBar.open(problem(err, 'Could not save assignment.'), 'OK', { duration: 4000 });
        if (result.kind === 'many') {
          this.api.assignShiftToEmployees(result.body).subscribe({
            next: (saved) => done(`Shift assigned to ${saved.assigned} employee(s).`),
            error: failed,
          });
          return;
        }
        const req =
          mode === 'edit' && assignment
            ? this.api.updateShiftAssignment(assignment.id, assignment.rowVersion, result.body)
            : this.api.createShiftAssignment(result.body);
        req.subscribe({
          next: () => done(mode === 'edit' ? 'Assignment updated.' : 'Shift assigned.'),
          error: failed,
        });
        return;
      });
  }

  private ensureOptions(then: () => void): void {
    if (this.assignmentOptions()) {
      then();
      return;
    }
    this.api.shiftAssignmentOptions().subscribe({
      next: (options) => {
        this.assignmentOptions.set(options);
        then();
      },
      error: () => this.snackBar.open('Could not load employees and shifts.', 'OK', { duration: 3500 }),
    });
  }

  private reloadAll(): void {
    this.loading.set(true);
    this.error.set('');
    forkJoin({
      shifts: this.api.listShifts({ page: 1, pageSize: 200 }),
      rules: this.api.getRules(),
      leaveYear: this.api.leaveYear(),
      assignments: this.api.listShiftAssignments({
        page: 1,
        pageSize: 200,
        currentOnly: !this.showAssignmentHistory(),
      }),
      options: this.api.shiftAssignmentOptions(),
    }).subscribe({
      next: ({ shifts, rules, leaveYear, assignments, options }) => {
        this.shifts.set(shifts.items);
        this.shiftSummary.set(shifts.summary);
        this.rules.set(rules);
        this.leaveYear.set(leaveYear);
        this.assignments.set(assignments.items);
        this.assignmentOptions.set(options);
        this.loading.set(false);
        if (this.contentTab() === 'holidays') this.reloadHolidays();
      },
      error: (err: unknown) => {
        this.loading.set(false);
        this.error.set(problem(err, 'Shift & attendance rules could not be loaded.'));
      },
    });
  }

  private reloadShifts(): void {
    this.api.listShifts({ page: 1, pageSize: 200 }).subscribe({
      next: (page) => {
        this.shifts.set(page.items);
        this.shiftSummary.set(page.summary);
        this.selectedIds.set(new Set());
      },
      error: (err: unknown) =>
        this.snackBar.open(problem(err, 'Shifts could not be loaded.'), 'OK', { duration: 3500 }),
    });
  }

  private reloadRules(): void {
    this.api.getRules().subscribe({
      next: (rules) => this.rules.set(rules),
      error: (err: unknown) =>
        this.snackBar.open(problem(err, 'Attendance rules could not be loaded.'), 'OK', {
          duration: 3500,
        }),
    });
  }

  private reloadAssignments(): void {
    this.api
      .listShiftAssignments({
        page: 1,
        pageSize: 200,
        currentOnly: !this.showAssignmentHistory(),
        search: this.assignmentSearch() || undefined,
      })
      .subscribe({
        next: (page) => this.assignments.set(page.items),
        error: (err: unknown) =>
          this.snackBar.open(problem(err, 'Shift assignments could not be loaded.'), 'OK', {
            duration: 3500,
          }),
      });
  }

  private reloadHolidays(): void {
    this.holidayError.set('');
    this.api.holidaysForLeaveYear().subscribe({
      next: (page) => {
        this.leaveYear.set(page.leaveYear);
        this.holidays.set(page.items);
        this.rules.update((current) =>
          current
            ? { ...current, leaveYearLabel: page.leaveYear.label, holidayCount: page.total }
            : current,
        );
      },
      error: (err: unknown) =>
        this.holidayError.set(problem(err, 'Holidays could not be loaded.')),
    });
  }
}

function formatTime(value: string): string {
  const [hhRaw, mmRaw] = value.slice(0, 5).split(':');
  const hh = Number(hhRaw);
  const mm = mmRaw ?? '00';
  if (Number.isNaN(hh)) return value;
  const suffix = hh >= 12 ? 'PM' : 'AM';
  const hour12 = ((hh + 11) % 12) + 1;
  return `${String(hour12).padStart(2, '0')}:${mm} ${suffix}`;
}

function formatDate(value: string): string {
  const [y, m, d] = value.slice(0, 10).split('-').map(Number);
  if (!y || !m || !d) return value;
  const months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
  return `${String(d).padStart(2, '0')} ${months[m - 1]} ${y}`;
}

function codeTone(code: string): string {
  let hash = 0;
  for (let i = 0; i < code.length; i++) hash = (hash * 31 + code.charCodeAt(i)) >>> 0;
  return CODE_TONES[hash % CODE_TONES.length]!;
}

function avatarTone(name: string): string {
  return codeTone(name || 'X');
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
