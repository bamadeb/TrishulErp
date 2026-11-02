import { Injectable, inject, signal } from '@angular/core';
import { Observable, catchError, of, tap } from 'rxjs';
import {
  ApiClient,
  ListMyAlerts$Params,
  MyAlertItem,
  MyAlertSummary,
  PageMyAlertItem,
  acknowledgeMyAlert,
  getMyAlertSummary,
  listMyAlerts,
  readMyAlert,
} from '@trishul/core-api';

export type { MyAlertItem } from '@trishul/core-api';
export type AlertSeverity = MyAlertItem['severity'];

/** Seconds between unread-count checks while the app is open (phase 1: polling, no push). */
export const ALERT_POLL_MS = 60_000;

/** The signed-in user's in-app alerts (/core/my-alerts): the bell's counts and the inbox actions. */
@Injectable({ providedIn: 'root' })
export class AlertInbox {
  private readonly api = inject(ApiClient);

  /** Unread / open counts for the bell; null until first loaded. */
  readonly summary = signal<MyAlertSummary | null>(null);

  refreshSummary(): Observable<MyAlertSummary | null> {
    return this.api.call(getMyAlertSummary).pipe(
      tap((s) => this.summary.set(s)),
      catchError(() => of(null)), // the bell just keeps its last count
    );
  }

  list(query: ListMyAlerts$Params): Observable<PageMyAlertItem> {
    return this.api.call(listMyAlerts, query);
  }

  read(alertId: number): Observable<MyAlertItem> {
    return this.api.call(readMyAlert, { alertId });
  }

  acknowledge(alertId: number): Observable<MyAlertItem> {
    return this.api.call(acknowledgeMyAlert, { alertId });
  }
}

/** Where an alert's record opens in the app, or null if it has no page yet. */
export function alertLink(
  alert: Pick<MyAlertItem, 'entityType' | 'entityId'>,
): string[] | null {
  switch (alert.entityType) {
    case 'svc.service_call':
      return ['/service/calls', String(alert.entityId)];
    case 'core.machine_unit':
      return ['/service/machines', String(alert.entityId)];
    default:
      return null;
  }
}

export const SEVERITY_ICON: Record<AlertSeverity, string> = {
  Critical: 'error',
  Warning: 'warning',
  Info: 'info',
};
