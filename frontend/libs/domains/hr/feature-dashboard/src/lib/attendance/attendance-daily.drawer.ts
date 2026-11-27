import { DatePipe, DecimalPipe } from '@angular/common';
import { ChangeDetectionStrategy, Component, input, output, signal } from '@angular/core';
import { MatButton, MatIconButton } from '@angular/material/button';
import { MatIcon } from '@angular/material/icon';
import { RegularizationRow } from '@trishul/hr-data-access';
import { StatusBadge, StatusSeverity } from '@trishul/shared-ui';
import { AttendanceRegularizeDrawer } from './attendance-regularize-drawer';
import { DailyAttendanceRow } from './attendance.models';

/** Lightweight details drawer for Daily Attendance UI mock. */
@Component({
  selector: 'trishul-attendance-daily-drawer',
  imports: [DatePipe, DecimalPipe, MatButton, MatIcon, MatIconButton, StatusBadge, AttendanceRegularizeDrawer],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './attendance-daily.drawer.html',
  styleUrl: './attendance-daily.drawer.scss',
  host: {
    '[class.form]': 'showRequestForm() && !request()',
    '[class.wide]': '!!request()',
  },
})
export class AttendanceDailyDrawer {
  readonly row = input.required<DailyAttendanceRow>();
  readonly selectedDate = input.required<Date>();
  /** Regularization for this employee on the selected date, when one exists. */
  readonly request = input<RegularizationRow | null>(null);
  /** Case 3: no request, so the existing request form fills this drawer. */
  readonly showRequestForm = input(false);
  readonly closed = output<void>();
  readonly regularize = output<DailyAttendanceRow>();
  readonly submitted = output<void>();
  readonly shiftOpen = output<DailyAttendanceRow>();

  protected readonly detailTab = signal<'details' | 'punches' | 'history'>('details');
  /** Set when this drawer is opened from Attendance Exceptions. */
  readonly exceptionType = input<string | null>(null);
  readonly exceptionStatus = input<string | null>(null);

  protected readonly severities: Partial<Record<string, StatusSeverity>> = {
    Present: 'success',
    Late: 'warn',
    'In Progress': 'info',
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

  protected requestCode(id: number): string {
    return `REG-${String(id).padStart(4, '0')}`;
  }

  /** Exception review status for display; API value Pending → Unresolved. */
  protected exceptionReviewLabel(status: string | null | undefined): string {
    if (!status) return '—';
    return status === 'Pending' ? 'Unresolved' : status;
  }

  protected clock(value: string | null | undefined): string {
    if (!value) return '—';
    if (/am|pm/i.test(value) && !value.includes('T')) return value;
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) return value;
    return new Intl.DateTimeFormat('en-US', { hour: '2-digit', minute: '2-digit', hour12: true }).format(date);
  }

  protected dateIso(): string {
    const day = this.selectedDate();
    const month = String(day.getMonth() + 1).padStart(2, '0');
    const date = String(day.getDate()).padStart(2, '0');
    return `${day.getFullYear()}-${month}-${date}`;
  }

  protected initials(name: string): string {
    return name
      .split(/\s+/)
      .slice(0, 2)
      .map((part) => part[0]?.toUpperCase() ?? '')
      .join('');
  }
}
