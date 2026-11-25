import { DecimalPipe } from '@angular/common';
import { HttpErrorResponse } from '@angular/common/http';
import {
  ChangeDetectionStrategy,
  Component,
  OnInit,
  computed,
  inject,
  signal,
} from '@angular/core';
import { MatIconButton } from '@angular/material/button';
import { MatIcon } from '@angular/material/icon';
import { MatProgressSpinner } from '@angular/material/progress-spinner';
import { MatSnackBar } from '@angular/material/snack-bar';
import { RouterLink } from '@angular/router';
import {
  AttendanceApi,
  AttendanceDashboard,
  AttendanceDashboardDepartmentRow,
  AttendanceDashboardExceptionItem,
  AttendanceDashboardOverviewSlice,
  AttendanceDashboardQuickAction,
  AttendanceDashboardTrendPoint,
} from '@trishul/hr-data-access';
import { PageHeader } from '@trishul/shared-ui';
import { DashboardOverviewSlice } from './attendance.models';

interface DonutSlice extends DashboardOverviewSlice {
  dash: string;
  offset: number;
}

interface KpiCard {
  id: string;
  label: string;
  value: number;
  percent?: number;
  icon: string;
  tone: 'total' | 'present' | 'absent' | 'late' | 'early' | 'short';
}

/** Attendance Dashboard — live KPIs from GET /hr/attendance/dashboard. */
@Component({
  selector: 'trishul-attendance-dashboard-page',
  imports: [DecimalPipe, MatIcon, MatIconButton, MatProgressSpinner, PageHeader, RouterLink],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './attendance-dashboard.page.html',
  styleUrl: './attendance-dashboard.page.scss',
})
export class AttendanceDashboardPage implements OnInit {
  private readonly api = inject(AttendanceApi);
  private readonly snackBar = inject(MatSnackBar);

  protected readonly loading = signal(false);
  protected readonly error = signal<string | null>(null);
  protected readonly selectedDate = signal(new Date());
  protected readonly dateLabel = signal('');
  protected readonly attendanceRate = signal(0);
  protected readonly kpiCards = signal<KpiCard[]>([]);
  protected readonly overview = signal<AttendanceDashboardOverviewSlice[]>([]);
  protected readonly departments = signal<AttendanceDashboardDepartmentRow[]>([]);
  protected readonly exceptions = signal<AttendanceDashboardExceptionItem[]>([]);
  protected readonly exceptionsTotal = signal(0);
  protected readonly actions = signal<AttendanceDashboardQuickAction[]>([]);
  protected readonly trend = signal<AttendanceDashboardTrendPoint[]>([]);
  protected readonly isMonthFinalized = signal(false);

  protected readonly slices = computed((): DonutSlice[] => {
    const circumference = 2 * Math.PI * 42;
    let cursor = 0;
    return this.overview().map((slice) => {
      const length = (slice.percent / 100) * circumference;
      const item: DonutSlice = {
        ...slice,
        dash: `${length} ${circumference - length}`,
        offset: -cursor,
      };
      cursor += length;
      return item;
    });
  });

  protected readonly trendLine = computed(() => {
    const points = this.trend();
    if (!points.length) return '';
    const min = 80;
    const max = 100;
    const width = 280;
    const height = 100;
    const padX = 12;
    const padY = 14;
    return points
      .map((point, index) => {
        const x = padX + (index / Math.max(points.length - 1, 1)) * (width - padX * 2);
        const y = padY + (1 - (point.percent - min) / (max - min)) * (height - padY * 2);
        return `${x.toFixed(1)},${y.toFixed(1)}`;
      })
      .join(' ');
  });

  protected readonly trendArea = computed(() => {
    const line = this.trendLine();
    if (!line) return '';
    const first = line.split(' ')[0];
    const last = line.split(' ').at(-1);
    if (!first || !last) return '';
    const firstX = first.split(',')[0];
    const lastX = last.split(',')[0];
    return `${firstX},86 ${line} ${lastX},86`;
  });

  ngOnInit(): void {
    this.reload();
  }

  protected shiftDate(delta: number): void {
    const next = new Date(this.selectedDate());
    next.setDate(next.getDate() + delta);
    this.selectedDate.set(next);
    this.reload();
  }

  protected reload(): void {
    this.loading.set(true);
    this.error.set(null);
    this.api.dashboard(toIsoDate(this.selectedDate())).subscribe({
      next: (page) => {
        this.apply(page);
        this.loading.set(false);
      },
      error: (err: unknown) => {
        this.loading.set(false);
        this.error.set(messageFrom(err));
        this.snackBar.open(this.error() ?? 'Failed to load attendance dashboard.', 'OK', {
          duration: 4000,
        });
      },
    });
  }

  private apply(page: AttendanceDashboard): void {
    this.dateLabel.set(page.dateLabel);
    this.attendanceRate.set(page.attendanceRate);
    this.overview.set(page.overview);
    this.departments.set(page.departments);
    this.exceptions.set(page.exceptions);
    this.exceptionsTotal.set(page.exceptionsTotal);
    this.actions.set(page.actions);
    this.trend.set(page.trend);
    this.isMonthFinalized.set(page.isMonthFinalized);
    const k = page.kpi;
    this.kpiCards.set([
      { id: 'total', label: 'Total Employees', value: k.total, icon: 'groups', tone: 'total' },
      {
        id: 'present',
        label: 'Present',
        value: k.present,
        percent: k.presentPct,
        icon: 'check_circle',
        tone: 'present',
      },
      {
        id: 'absent',
        label: 'Absent',
        value: k.absent,
        percent: k.absentPct,
        icon: 'person_off',
        tone: 'absent',
      },
      {
        id: 'late',
        label: 'Late Arrival',
        value: k.late,
        percent: k.latePct,
        icon: 'schedule',
        tone: 'late',
      },
      {
        id: 'early',
        label: 'Early Exit',
        value: k.earlyExit,
        percent: k.earlyExitPct,
        icon: 'logout',
        tone: 'early',
      },
      {
        id: 'short',
        label: 'Short Hours',
        value: k.shortHours,
        percent: k.shortHoursPct,
        icon: 'timer',
        tone: 'short',
      },
    ]);
  }
}

function toIsoDate(value: Date): string {
  const y = value.getFullYear();
  const m = String(value.getMonth() + 1).padStart(2, '0');
  const d = String(value.getDate()).padStart(2, '0');
  return `${y}-${m}-${d}`;
}

function messageFrom(err: unknown): string {
  if (err instanceof HttpErrorResponse) {
    const detail = err.error?.detail ?? err.error?.message;
    if (typeof detail === 'string') return detail;
  }
  return err instanceof Error ? err.message : 'Failed to load attendance dashboard.';
}
