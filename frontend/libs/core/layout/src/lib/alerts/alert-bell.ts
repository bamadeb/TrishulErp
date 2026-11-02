import { DatePipe } from '@angular/common';
import {
  ChangeDetectionStrategy,
  Component,
  computed,
  inject,
  signal,
} from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { MatBadge } from '@angular/material/badge';
import { MatButton, MatIconButton } from '@angular/material/button';
import { MatIcon } from '@angular/material/icon';
import { MatMenu, MatMenuTrigger } from '@angular/material/menu';
import { MatProgressBar } from '@angular/material/progress-bar';
import { MatTooltip } from '@angular/material/tooltip';
import { Router, RouterLink } from '@angular/router';
import { EMPTY, catchError, finalize, switchMap, timer } from 'rxjs';
import { AuthStore } from '@trishul/core-auth';
import {
  ALERT_POLL_MS,
  AlertInbox,
  MyAlertItem,
  SEVERITY_ICON,
  alertLink,
} from './alert-inbox';

/** Toolbar bell: unread count (checked every minute) and the latest open alerts. */
@Component({
  selector: 'trishul-alert-bell',
  imports: [
    DatePipe,
    RouterLink,
    MatBadge,
    MatButton,
    MatIconButton,
    MatIcon,
    MatMenu,
    MatMenuTrigger,
    MatProgressBar,
    MatTooltip,
  ],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    @if (canSee) {
      <button
        mat-icon-button
        [matMenuTriggerFor]="menu"
        (menuOpened)="loadLatest()"
        [matTooltip]="tooltip()"
        [attr.aria-label]="tooltip()"
      >
        <mat-icon
          [matBadge]="unread() || null"
          matBadgeColor="warn"
          matBadgeSize="small"
          [matBadgeHidden]="!unread()"
          aria-hidden="false"
          >{{ unread() ? 'notifications_active' : 'notifications' }}</mat-icon
        >
      </button>
      <mat-menu #menu="matMenu" class="alert-menu" xPosition="before">
        <div class="head">
          <span>Alerts</span>
          <span class="muted">{{ inbox.summary()?.open ?? 0 }} open</span>
        </div>
        <div class="progress">
          @if (loading()) {
            <mat-progress-bar mode="indeterminate" />
          }
        </div>
        @for (a of latest(); track a.id) {
          <button
            type="button"
            class="item"
            [class.unread]="!a.readAt"
            [class]="'sev-' + a.severity.toLowerCase()"
            (click)="open(a)"
          >
            <mat-icon class="sev">{{ severityIcon[a.severity] }}</mat-icon>
            <span class="text">
              <span class="title">{{ a.title }}</span>
              <span class="message">{{ a.message }}</span>
              <span class="time">{{ a.raisedAt | date: 'dd MMM, HH:mm' }}</span>
            </span>
          </button>
        } @empty {
          @if (!loading()) {
            <p class="empty">No open alerts.</p>
          }
        }
        <div class="foot">
          <a mat-button routerLink="/alerts">See all alerts</a>
        </div>
      </mat-menu>
    }
  `,
  styles: `
    :host {
      display: contents;
    }
    .head {
      display: flex;
      justify-content: space-between;
      align-items: baseline;
      padding: 0.6rem 1rem 0.4rem;
      font: var(--mat-sys-title-small);
    }
    .muted {
      font: var(--mat-sys-body-small);
      color: var(--mat-sys-on-surface-variant);
    }
    .progress {
      height: 4px;
    }
    .item {
      display: flex;
      gap: 0.6rem;
      width: 100%;
      padding: 0.6rem 1rem;
      border: 0;
      border-top: 1px solid var(--mat-sys-outline-variant);
      background: none;
      color: inherit;
      font: inherit;
      text-align: left;
      cursor: pointer;
      &:hover,
      &:focus-visible {
        background: var(--mat-sys-surface-container-high);
      }
      &.unread .title {
        font-weight: 700;
      }
    }
    .sev {
      flex: none;
      font-size: 1.25rem;
      width: 1.25rem;
      height: 1.25rem;
      margin-top: 0.1rem;
    }
    .sev-critical .sev {
      color: var(--mat-sys-error);
    }
    .sev-warning .sev {
      color: #b26a00;
    }
    .sev-info .sev {
      color: var(--mat-sys-primary);
    }
    .text {
      display: grid;
      gap: 0.1rem;
      min-width: 0;
    }
    .title {
      font: var(--mat-sys-body-medium);
    }
    .message {
      font: var(--mat-sys-body-small);
      color: var(--mat-sys-on-surface-variant);
      display: -webkit-box;
      -webkit-line-clamp: 2;
      -webkit-box-orient: vertical;
      overflow: hidden;
    }
    .time {
      font: var(--mat-sys-label-small);
      color: var(--mat-sys-on-surface-variant);
    }
    .empty {
      margin: 0;
      padding: 1rem;
      color: var(--mat-sys-on-surface-variant);
    }
    .foot {
      display: flex;
      justify-content: flex-end;
      padding: 0.25rem 0.5rem;
      border-top: 1px solid var(--mat-sys-outline-variant);
    }
  `,
})
export class AlertBell {
  protected readonly inbox = inject(AlertInbox);
  private readonly router = inject(Router);
  protected readonly canSee =
    inject(AuthStore).hasPermission('core.alert.view');

  protected readonly latest = signal<MyAlertItem[]>([]);
  protected readonly loading = signal(false);
  protected readonly severityIcon = SEVERITY_ICON;
  protected readonly unread = computed(() => this.inbox.summary()?.unread ?? 0);
  protected readonly tooltip = computed(() =>
    this.unread() ? `${this.unread()} unread alerts` : 'Alerts',
  );

  constructor() {
    if (this.canSee) {
      timer(0, ALERT_POLL_MS)
        .pipe(
          switchMap(() => this.inbox.refreshSummary()),
          takeUntilDestroyed(),
        )
        .subscribe();
    }
  }

  protected loadLatest(): void {
    this.loading.set(true);
    this.inbox
      .list({ status: 'open', page: 1, pageSize: 8 })
      .pipe(
        finalize(() => this.loading.set(false)),
        catchError(() => EMPTY),
      )
      .subscribe((page) => this.latest.set(page.items));
  }

  /** Opening an alert marks it read and goes to its record (or the inbox). */
  protected open(alert: MyAlertItem): void {
    if (!alert.readAt) {
      this.inbox
        .read(alert.id)
        .pipe(
          switchMap(() => this.inbox.refreshSummary()),
          catchError(() => EMPTY),
        )
        .subscribe();
    }
    void this.router.navigate(alertLink(alert) ?? ['/alerts']);
  }
}
