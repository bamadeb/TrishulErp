import { DatePipe, NgTemplateOutlet } from '@angular/common';
import {
  ChangeDetectionStrategy,
  Component,
  computed,
  effect,
  inject,
  signal,
  untracked,
} from '@angular/core';
import { MatButton } from '@angular/material/button';
import { MatIcon } from '@angular/material/icon';
import { MatProgressBar } from '@angular/material/progress-bar';
import { MatTooltip } from '@angular/material/tooltip';
import { RouterLink } from '@angular/router';
import { ApiClient, Dashboard, DashboardVisit, getDashboard } from '@trishul/core-api';
import { AuthStore } from '@trishul/core-auth';
import { PageHeader, StatusBadge, StatusSeverity } from '@trishul/shared-ui';
import { EMPTY, catchError, finalize } from 'rxjs';

/** One figure on the dashboard; a link when there is a screen that lists those records. */
interface Tile {
  label: string;
  value: number | string;
  icon: string;
  hint?: string | undefined;
  tone?: 'danger' | 'warn' | 'good' | undefined;
  link?: string | undefined;
  query?: Record<string, string> | undefined;
}

const PRIORITY_SEVERITY: Record<string, StatusSeverity> = {
  Critical: 'danger',
  High: 'warn',
  Normal: 'info',
  Low: 'neutral',
};

/** yyyy-mm-dd in the user's own time zone. */
function isoDay(offset = 0): string {
  const day = new Date();
  day.setDate(day.getDate() + offset);
  return day.toLocaleDateString('en-CA');
}

/**
 * Home page. The server decides which sections the user gets from their role's permissions
 * (GET /rpt/dashboard): an engineer sees their own work, the call desk (team lead, back office,
 * management) the calls overview, and anyone with ASC access the ASC overview. Figures follow the
 * selected branch and brand.
 */
@Component({
  selector: 'trishul-dashboard-page',
  imports: [
    DatePipe,
    NgTemplateOutlet,
    RouterLink,
    MatButton,
    MatIcon,
    MatProgressBar,
    MatTooltip,
    PageHeader,
    StatusBadge,
  ],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './dashboard.page.html',
  styleUrl: './dashboard.page.scss',
})
export class DashboardPage {
  private readonly api = inject(ApiClient);
  protected readonly auth = inject(AuthStore);

  protected readonly data = signal<Dashboard | null>(null);
  protected readonly loading = signal(false);
  protected readonly failed = signal(false);
  protected readonly prioritySeverity = PRIORITY_SEVERITY;
  protected readonly today = isoDay();
  private readonly tomorrow = isoDay(1);

  protected readonly subtitle = computed(() =>
    [this.auth.user()?.roleNames?.join(', '), this.auth.currentBranch()?.name]
      .filter(Boolean)
      .join(' · '),
  );

  protected readonly empty = computed(() => {
    const d = this.data();
    return !!d && !d.myWork && !d.calls && !d.asc;
  });

  protected readonly myTiles = computed<Tile[]>(() => {
    const w = this.data()?.myWork;
    if (!w) return [];
    const tiles: Tile[] = [
      { label: 'My open calls', value: w.openCalls, icon: 'assignment', link: '/service/calls' },
      {
        label: 'Visits today',
        value: w.visitsToday,
        icon: 'today',
        link: '/service/calls',
        query: { visitDate: this.today },
      },
      {
        label: 'Visits tomorrow',
        value: w.visitsTomorrow,
        icon: 'event',
        link: '/service/calls',
        query: { visitDate: this.tomorrow },
      },
      {
        label: 'Overdue visits',
        value: w.overdueVisits,
        icon: 'event_busy',
        tone: w.overdueVisits ? 'danger' : undefined,
        hint: 'Planned day has passed and the visit has not started',
      },
      {
        label: 'Machine down',
        value: w.machineDown,
        icon: 'warning',
        tone: w.machineDown ? 'warn' : undefined,
      },
    ];
    return tiles;
  });

  protected readonly callTiles = computed<Tile[]>(() => {
    const c = this.data()?.calls;
    if (!c) return [];
    const canAssign = this.auth.hasPermission('svc.call.assign');
    // Unassigned calls: the assign board for a team lead, otherwise the register's new calls.
    const unassignedQuery: Record<string, string> | undefined = canAssign
      ? undefined
      : { status: 'Logged' };
    const tiles: Tile[] = [
      { label: 'Open calls', value: c.openCalls, icon: 'assignment', link: '/service/calls' },
      {
        label: 'Unassigned',
        value: c.unassigned,
        icon: 'person_add',
        tone: c.unassigned ? 'warn' : undefined,
        link: canAssign ? '/service/assign' : '/service/calls',
        query: unassignedQuery,
      },
      {
        label: 'Machine down',
        value: c.machineDown,
        icon: 'warning',
        tone: c.machineDown ? 'warn' : undefined,
      },
      {
        label: 'SLA breached',
        value: c.slaBreached,
        icon: 'timer_off',
        tone: c.slaBreached ? 'danger' : undefined,
        hint: 'Open calls past their SLA due time',
        link: '/service/calls',
        query: { sort: 'slaDueAt' },
      },
      {
        label: 'SLA due in 24 h',
        value: c.slaDueSoon,
        icon: 'timer',
        tone: c.slaDueSoon ? 'warn' : undefined,
        link: '/service/calls',
        query: { sort: 'slaDueAt' },
      },
      {
        label: 'Visits today',
        value: c.visitsToday,
        icon: 'today',
        link: '/service/calls',
        query: { visitDate: this.today },
      },
      {
        label: 'Visits tomorrow',
        value: c.visitsTomorrow,
        icon: 'event',
        link: '/service/calls',
        query: { visitDate: this.tomorrow },
      },
      {
        label: 'Overdue visits',
        value: c.overdueVisits,
        icon: 'event_busy',
        tone: c.overdueVisits ? 'danger' : undefined,
        hint: 'Planned day has passed and the visit has not started',
      },
      {
        label: 'Completed this month',
        value: c.completedThisMonth,
        icon: 'task_alt',
        tone: 'good',
        link: '/service/calls',
        query: { status: 'Completed' },
      },
    ];
    return tiles;
  });

  protected readonly ascTiles = computed<Tile[]>(() => {
    const a = this.data()?.asc;
    if (!a) return [];
    const tiles: Tile[] = [
      { label: 'Active ASCs', value: a.active, icon: 'verified', link: '/service/asc' },
      {
        label: 'Expiring in 30 days',
        value: a.expiringSoon,
        icon: 'event_upcoming',
        tone: a.expiringSoon ? 'warn' : undefined,
        link: '/service/asc',
      },
      {
        label: 'Visits used',
        value: `${a.visitsUsed} / ${a.visitsIncluded}`,
        icon: 'checklist',
        hint: 'Across active ASCs that have a visit limit',
      },
      { label: 'Visits left', value: a.visitsRemaining, icon: 'pending_actions' },
      {
        label: 'Calls to count',
        value: a.callsToCount,
        icon: 'playlist_add_check',
        tone: a.callsToCount ? 'warn' : undefined,
        hint: 'Completed or closed calls on an ASC whose visits are not counted yet',
        link: '/service/asc',
      },
    ];
    return tiles;
  });

  constructor() {
    // Load now, and again when the user switches branch or brand.
    effect(() => {
      this.auth.branchId();
      this.auth.principalId();
      untracked(() => this.load());
    });
  }

  protected load(): void {
    this.loading.set(true);
    this.failed.set(false);
    this.api
      .call(getDashboard)
      .pipe(
        finalize(() => this.loading.set(false)),
        catchError(() => {
          this.failed.set(true);
          return EMPTY;
        }),
      )
      .subscribe((dashboard) => this.data.set(dashboard));
  }

  /** "Today", "Tomorrow", or the date; overdue days are flagged in the template. */
  protected dayLabel(visit: DashboardVisit): string | null {
    if (visit.plannedDate === this.today) return 'Today';
    if (visit.plannedDate === this.tomorrow) return 'Tomorrow';
    return null;
  }

  protected isOverdue(visit: DashboardVisit): boolean {
    return visit.plannedDate < this.today;
  }
}
