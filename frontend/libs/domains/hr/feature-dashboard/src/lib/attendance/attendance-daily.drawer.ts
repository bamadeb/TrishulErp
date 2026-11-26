import { DatePipe, DecimalPipe } from '@angular/common';
import { ChangeDetectionStrategy, Component, input, output } from '@angular/core';
import { MatButton, MatIconButton } from '@angular/material/button';
import { MatIcon } from '@angular/material/icon';
import { StatusBadge, StatusSeverity } from '@trishul/shared-ui';
import { DailyAttendanceRow } from './attendance.models';

/** Lightweight details drawer for Daily Attendance UI mock. */
@Component({
  selector: 'trishul-attendance-daily-drawer',
  imports: [DatePipe, DecimalPipe, MatButton, MatIcon, MatIconButton, StatusBadge],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './attendance-daily.drawer.html',
  styleUrl: './attendance-daily.drawer.scss',
})
export class AttendanceDailyDrawer {
  readonly row = input.required<DailyAttendanceRow>();
  readonly selectedDate = input.required<Date>();
  readonly closed = output<void>();
  readonly regularize = output<DailyAttendanceRow>();
  readonly shiftOpen = output<DailyAttendanceRow>();
  /** Set when this drawer is opened from Attendance Exceptions. */
  readonly exceptionType = input<string | null>(null);
  readonly exceptionStatus = input<string | null>(null);

  protected readonly severities: Partial<Record<string, StatusSeverity>> = {
    Present: 'success',
    Late: 'warn',
    'Missing Punch': 'warn',
    Absent: 'danger',
    'On Leave': 'info',
    'Off Day': 'info',
    Holiday: 'neutral',
    WFH: 'info',
  };

  /** Google Maps at the punch point (mobile face punches carry their GPS fix). */
  protected mapLink(latitude: number, longitude: number): string {
    return `https://www.google.com/maps?q=${latitude},${longitude}`;
  }

  protected formatDistance(metres: number): string {
    return metres >= 1000 ? `${(metres / 1000).toFixed(1)} km` : `${Math.round(metres)} m`;
  }

  protected initials(name: string): string {
    return name
      .split(/\s+/)
      .slice(0, 2)
      .map((part) => part[0]?.toUpperCase() ?? '')
      .join('');
  }
}
