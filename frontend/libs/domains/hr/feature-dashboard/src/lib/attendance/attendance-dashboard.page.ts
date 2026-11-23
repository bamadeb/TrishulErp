import { DecimalPipe } from '@angular/common';
import {
  ChangeDetectionStrategy,
  Component,
  computed,
  inject,
  signal,
} from '@angular/core';
import { MatIconButton } from '@angular/material/button';
import { MatIcon } from '@angular/material/icon';
import { MatSnackBar } from '@angular/material/snack-bar';
import { RouterLink } from '@angular/router';
import { PageHeader } from '@trishul/shared-ui';
import {
  DASHBOARD_ACTIONS,
  DASHBOARD_ATTENDANCE_RATE,
  DASHBOARD_DATE_LABEL,
  DASHBOARD_DEPARTMENTS,
  DASHBOARD_EXCEPTIONS,
  DASHBOARD_EXCEPTIONS_TOTAL,
  DASHBOARD_KPI,
  DASHBOARD_OVERVIEW,
  DASHBOARD_TREND,
} from './attendance-dashboard.mock';
import { DashboardOverviewSlice } from './attendance.models';

interface DonutSlice extends DashboardOverviewSlice {
  dash: string;
  offset: number;
}

/** Attendance Dashboard — UI-only static mock matching the HRMS reference. */
@Component({
  selector: 'trishul-attendance-dashboard-page',
  imports: [DecimalPipe, MatIcon, MatIconButton, PageHeader, RouterLink],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './attendance-dashboard.page.html',
  styleUrl: './attendance-dashboard.page.scss',
})
export class AttendanceDashboardPage {
  private readonly snackBar = inject(MatSnackBar);

  protected readonly dateLabel = signal(DASHBOARD_DATE_LABEL);
  protected readonly kpiCards = DASHBOARD_KPI;
  protected readonly attendanceRate = DASHBOARD_ATTENDANCE_RATE;
  protected readonly departments = DASHBOARD_DEPARTMENTS;
  protected readonly exceptions = DASHBOARD_EXCEPTIONS;
  protected readonly exceptionsTotal = DASHBOARD_EXCEPTIONS_TOTAL;
  protected readonly actions = DASHBOARD_ACTIONS;
  protected readonly trend = DASHBOARD_TREND;

  protected readonly slices = computed((): DonutSlice[] => {
    const circumference = 2 * Math.PI * 42;
    let cursor = 0;
    return DASHBOARD_OVERVIEW.map((slice) => {
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
    const points = this.trend;
    if (!points.length) return '';
    const min = 80;
    const max = 100;
    const width = 280;
    const height = 100;
    const padX = 12;
    const padY = 14;
    return points
      .map((point, index) => {
        const x =
          padX + (index / Math.max(points.length - 1, 1)) * (width - padX * 2);
        const y =
          padY +
          (1 - (point.percent - min) / (max - min)) * (height - padY * 2);
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

  protected shiftDate(delta: number): void {
    this.snackBar.open(
      delta < 0 ? 'Previous day (sample data).' : 'Next day (sample data).',
      'OK',
      { duration: 2000 },
    );
  }
}
