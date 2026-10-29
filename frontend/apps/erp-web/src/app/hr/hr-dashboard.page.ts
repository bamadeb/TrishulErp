import {
  ChangeDetectionStrategy,
  Component,
  computed,
  signal,
} from '@angular/core';
import { MatButton } from '@angular/material/button';
import { MatFormField, MatLabel } from '@angular/material/form-field';
import { MatIcon } from '@angular/material/icon';
import { MatOption, MatSelect } from '@angular/material/select';
import { RouterLink } from '@angular/router';
import { PageHeader, StatusBadge } from '@trishul/shared-ui';
import {
  approvalStatusFilters,
  approvalStatusSeverity,
  attendanceDays,
  celebrations,
  departmentDistribution,
  holidays,
  hrSummary,
  pendingApprovals,
  quickActions,
  recentActivities,
  summaryCards,
} from './hr-dashboard.mock-data';

/** HR home. Every figure on this screen comes from local sample data. */
@Component({
  selector: 'trishul-hr-dashboard-page',
  imports: [
    RouterLink,
    MatButton,
    MatFormField,
    MatLabel,
    MatSelect,
    MatOption,
    MatIcon,
    PageHeader,
    StatusBadge,
  ],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './hr-dashboard.page.html',
  styleUrl: './hr-dashboard.page.scss',
})
export class HrDashboardPage {
  protected readonly summary = hrSummary;
  protected readonly summaryCards = summaryCards;
  protected readonly attendanceDays = attendanceDays;
  protected readonly celebrations = celebrations;
  protected readonly holidays = holidays;
  protected readonly activities = recentActivities;
  protected readonly quickActions = quickActions;
  protected readonly approvalStatuses = approvalStatusFilters;
  protected readonly approvalSeverity = approvalStatusSeverity;
  protected readonly departments = departmentDistribution.map((row) => ({
    ...row,
    percent: (row.employees / hrSummary.totalEmployees) * 100,
  }));

  protected readonly selectedDate = signal(attendanceDays[0]?.date ?? '');
  protected readonly approvalStatus = signal<(typeof approvalStatusFilters)[number]>('All');

  protected readonly attendance = computed(
    () =>
      attendanceDays.find((day) => day.date === this.selectedDate()) ?? null,
  );

  protected readonly approvals = computed(() => {
    const status = this.approvalStatus();
    return status === 'All'
      ? pendingApprovals
      : pendingApprovals.filter((row) => row.status === status);
  });
}
