import { DatePipe } from '@angular/common';
import { ChangeDetectionStrategy, Component, effect, input, output, signal } from '@angular/core';
import { MatButton, MatIconButton } from '@angular/material/button';
import { MatIcon } from '@angular/material/icon';
import { StatusBadge, StatusSeverity } from '@trishul/shared-ui';
import { DailyAttendanceRow } from './attendance.models';

@Component({
  selector: 'trishul-attendance-daily-drawer',
  imports: [DatePipe, MatButton, MatIcon, MatIconButton, StatusBadge],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './attendance-daily.drawer.html',
  styleUrl: './attendance-daily.drawer.scss',
})
export class AttendanceDailyDrawer {
  readonly row = input.required<DailyAttendanceRow>();
  readonly selectedDate = input.required<Date>();
  readonly closed = output<void>();
  readonly regularize = output<DailyAttendanceRow>();
  readonly addRemark = output<DailyAttendanceRow>();
  readonly viewPunchLog = output<DailyAttendanceRow>();

  protected readonly tab = signal<'punches' | 'info' | 'history'>('punches');
  protected readonly severities: Partial<Record<string, StatusSeverity>> = {
    Present: 'success',
    Late: 'warn',
    'Missing Punch': 'warn',
    Absent: 'danger',
    'On Leave': 'info',
    'Off Day': 'info',
    Holiday: 'neutral',
  };

  constructor() {
    effect(() => {
      this.row();
      this.tab.set('punches');
    });
  }

  protected initials(name: string): string {
    return name
      .split(/\s+/)
      .slice(0, 2)
      .map((part) => part[0]?.toUpperCase() ?? '')
      .join('');
  }
}
