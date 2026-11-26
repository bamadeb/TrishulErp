import { ChangeDetectionStrategy, Component, DestroyRef, computed, inject, input, output, signal } from '@angular/core';
import { takeUntilDestroyed, toObservable } from '@angular/core/rxjs-interop';
import { MatButton, MatIconButton } from '@angular/material/button';
import { MatIcon } from '@angular/material/icon';
import { Router } from '@angular/router';
import { AuthStore } from '@trishul/core-auth';
import {
  ATTENDANCE_SHIFT_MANAGE_PERMISSION,
  AttendanceApi,
  ShiftAssignmentItem,
  ShiftItem,
} from '@trishul/hr-data-access';
import { forkJoin, of, switchMap, catchError } from 'rxjs';

/** Right-side shift details. Uses the existing shift and assignment APIs. */
@Component({
  selector: 'trishul-attendance-shift-drawer',
  imports: [MatButton, MatIcon, MatIconButton],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './attendance-shift.drawer.html',
  styleUrl: './attendance-shift.drawer.scss',
})
export class AttendanceShiftDrawer {
  private readonly api = inject(AttendanceApi);
  private readonly router = inject(Router);
  private readonly destroyRef = inject(DestroyRef);
  private readonly request = computed(() => ({
    name: this.shiftName(),
    employeeId: this.employeeId(),
  }));

  readonly shiftName = input.required<string>();
  readonly employeeId = input<number | null>(null);
  readonly employeeName = input('');
  readonly closed = output<void>();

  protected readonly canManage = inject(AuthStore).hasPermission(ATTENDANCE_SHIFT_MANAGE_PERMISSION);
  protected readonly loading = signal(true);
  protected readonly error = signal<string | null>(null);
  protected readonly shift = signal<ShiftItem | null>(null);
  protected readonly assignedCount = signal(0);
  protected readonly assignment = signal<ShiftAssignmentItem | null>(null);
  protected readonly breakLabel = signal('No scheduled break');
  protected readonly netHours = signal('—');

  constructor() {
    toObservable(this.request)
      .pipe(
        switchMap(({ name, employeeId }) => {
          this.loading.set(true);
          this.error.set(null);
          return this.api.listShifts({ page: 1, pageSize: 200 }).pipe(
            switchMap((page) => {
              const shift = matchShift(page.items, name);
              if (!shift) {
                return of({ shift: null as ShiftItem | null, total: 0, assignment: null as ShiftAssignmentItem | null });
              }
              return forkJoin({
                count: this.api.listShiftAssignments({
                  shiftId: shift.id,
                  currentOnly: true,
                  page: 1,
                  pageSize: 1,
                }),
                mine: employeeId
                  ? this.api.listShiftAssignments({
                      shiftId: shift.id,
                      employeeId,
                      currentOnly: false,
                      page: 1,
                      pageSize: 20,
                    })
                  : of({ items: [] as ShiftAssignmentItem[], total: 0 }),
              }).pipe(
                switchMap(({ count, mine }) =>
                  of({
                    shift,
                    total: count.total,
                    assignment: pickAssignment(mine.items),
                  }),
                ),
              );
            }),
            catchError(() => {
              this.error.set('Shift details could not be loaded.');
              return of({ shift: null as ShiftItem | null, total: 0, assignment: null as ShiftAssignmentItem | null });
            }),
          );
        }),
        takeUntilDestroyed(this.destroyRef),
      )
      .subscribe((result) => {
        this.shift.set(result.shift);
        this.assignedCount.set(result.total);
        this.assignment.set(result.assignment);
        if (result.shift) {
          const brk = breakForShift(result.shift.startTime, result.shift.endTime);
          this.breakLabel.set(
            brk ? `${clockLabel(brk.start)} – ${clockLabel(brk.end)} (${brk.minutes} min)` : 'No scheduled break',
          );
          this.netHours.set(netHours(result.shift.workHours, brk?.minutes ?? 0));
        } else if (!this.error()) {
          this.error.set('This shift was not found.');
        }
        this.loading.set(false);
      });
  }

  protected clock(value: string): string {
    return clockLabel(value);
  }

  protected dateLabel(value: string | null | undefined): string {
    if (!value) return 'Open';
    const [year, month, day] = value.slice(0, 10).split('-').map(Number);
    const date = new Date(year!, (month ?? 1) - 1, day ?? 1);
    if (Number.isNaN(date.getTime())) return value;
    return new Intl.DateTimeFormat('en-GB', { day: '2-digit', month: 'short', year: 'numeric' }).format(date);
  }

  protected manageShifts(): void {
    void this.router.navigateByUrl('/hr/attendance/rules');
  }
}

function matchShift(items: ShiftItem[], label: string): ShiftItem | null {
  const wanted = label.split('(')[0]?.trim().toLowerCase();
  if (!wanted || wanted === '—' || wanted === '-') return null;
  const matches = items.filter((item) => item.name.trim().toLowerCase() === wanted);
  return matches.find((item) => item.isActive) ?? matches[0] ?? null;
}

function pickAssignment(items: ShiftAssignmentItem[]): ShiftAssignmentItem | null {
  return items.find((item) => item.isCurrent) ?? items[0] ?? null;
}

/** Lunch deducted by the attendance calculation when it falls inside the shift. */
function breakForShift(start: string, end: string): { start: string; end: string; minutes: number } | null {
  const lunchStart = 13 * 60 + 30;
  const lunchEnd = 14 * 60;
  let from = clockMinutes(start);
  let to = clockMinutes(end);
  if (to <= from) to += 24 * 60;
  const minutes = Math.max(0, Math.min(to, lunchEnd) - Math.max(from, lunchStart));
  if (minutes <= 0) return null;
  return { start: '13:30', end: '14:00', minutes };
}

function netHours(workHours: string, breakMinutes: number): string {
  const total = Math.max(0, clockMinutes(workHours) - breakMinutes);
  return `${String(Math.floor(total / 60)).padStart(2, '0')}:${String(total % 60).padStart(2, '0')}`;
}

function clockMinutes(value: string): number {
  const [hours, minutes] = value.split(':').map(Number);
  return (hours || 0) * 60 + (minutes || 0);
}

function clockLabel(value: string): string {
  const [hours, minutes] = value.split(':').map(Number);
  if (hours == null || minutes == null || Number.isNaN(hours) || Number.isNaN(minutes)) return value;
  const date = new Date();
  date.setHours(hours, minutes, 0, 0);
  return new Intl.DateTimeFormat('en-US', { hour: 'numeric', minute: '2-digit' }).format(date);
}
