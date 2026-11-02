import { DatePipe } from '@angular/common';
import {
  ChangeDetectionStrategy,
  Component,
  computed,
  inject,
  signal,
} from '@angular/core';
import { MatButton } from '@angular/material/button';
import {
  MatButtonToggle,
  MatButtonToggleGroup,
} from '@angular/material/button-toggle';
import { MatCheckbox } from '@angular/material/checkbox';
import { MatIcon } from '@angular/material/icon';
import { MatPaginator, PageEvent } from '@angular/material/paginator';
import { MatProgressBar } from '@angular/material/progress-bar';
import { RouterLink } from '@angular/router';
import { EMPTY, catchError, finalize, forkJoin, switchMap } from 'rxjs';
import {
  AlertInbox,
  MyAlertItem,
  SEVERITY_ICON,
  alertLink,
} from './alert-inbox';

type StatusFilter = 'open' | 'all';

/** The signed-in user's alerts (/alerts): newest first, with read and acknowledge. */
@Component({
  selector: 'trishul-alerts-page',
  imports: [
    DatePipe,
    RouterLink,
    MatButton,
    MatButtonToggleGroup,
    MatButtonToggle,
    MatCheckbox,
    MatIcon,
    MatPaginator,
    MatProgressBar,
  ],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './alerts.page.html',
  styleUrl: './alerts.page.scss',
})
export class AlertsPage {
  private readonly inbox = inject(AlertInbox);

  protected readonly status = signal<StatusFilter>('open');
  protected readonly unreadOnly = signal(false);
  protected readonly page = signal(1);
  protected readonly pageSize = signal(20);
  protected readonly items = signal<MyAlertItem[]>([]);
  protected readonly total = signal(0);
  protected readonly loading = signal(false);
  protected readonly busyId = signal<number | null>(null);
  protected readonly severityIcon = SEVERITY_ICON;
  protected readonly link = alertLink;
  protected readonly unreadOnPage = computed(() =>
    this.items().filter((a) => !a.readAt),
  );
  protected readonly emptyText = computed(() =>
    this.status() === 'open'
      ? 'No open alerts. You are all caught up.'
      : 'No alerts yet.',
  );

  constructor() {
    this.load();
  }

  protected setStatus(status: StatusFilter): void {
    this.status.set(status);
    this.page.set(1);
    this.load();
  }

  protected setUnreadOnly(value: boolean): void {
    this.unreadOnly.set(value);
    this.page.set(1);
    this.load();
  }

  protected onPage(event: PageEvent): void {
    this.page.set(event.pageIndex + 1);
    this.pageSize.set(event.pageSize);
    this.load();
  }

  protected markRead(alert: MyAlertItem): void {
    if (alert.readAt) return;
    this.act(alert, this.inbox.read(alert.id));
  }

  protected acknowledge(alert: MyAlertItem): void {
    this.act(alert, this.inbox.acknowledge(alert.id));
  }

  /** Marks the unread alerts on this page as read. */
  protected markPageRead(): void {
    const unread = this.unreadOnPage();
    if (!unread.length) return;
    this.loading.set(true);
    forkJoin(unread.map((a) => this.inbox.read(a.id)))
      .pipe(
        switchMap(() => this.inbox.refreshSummary()),
        finalize(() => this.loading.set(false)),
        catchError(() => EMPTY),
      )
      .subscribe(() => this.load());
  }

  private act(
    alert: MyAlertItem,
    request: ReturnType<AlertInbox['read']>,
  ): void {
    this.busyId.set(alert.id);
    request
      .pipe(
        finalize(() => this.busyId.set(null)),
        catchError(() => EMPTY),
      )
      .subscribe((updated) => {
        this.items.update((list) =>
          list.map((a) => (a.id === updated.id ? updated : a)),
        );
        this.inbox.refreshSummary().subscribe();
      });
  }

  private load(): void {
    this.loading.set(true);
    this.inbox
      .list({
        status: this.status(),
        unreadOnly: this.unreadOnly(),
        page: this.page(),
        pageSize: this.pageSize(),
      })
      .pipe(
        finalize(() => this.loading.set(false)),
        catchError(() => EMPTY),
      )
      .subscribe((page) => {
        this.items.set(page.items);
        this.total.set(page.total);
      });
  }
}
