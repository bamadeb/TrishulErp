import { DatePipe } from '@angular/common';
import {
  ChangeDetectionStrategy,
  Component,
  effect,
  inject,
  input,
  signal,
  untracked,
} from '@angular/core';
import { MatButton } from '@angular/material/button';
import { MatIcon } from '@angular/material/icon';
import { MatProgressBar } from '@angular/material/progress-bar';
import { Router, RouterLink } from '@angular/router';
import { EMPTY, catchError, finalize } from 'rxjs';
import {
  CallPriority,
  CallStatus,
  ServiceCallApi,
  ServiceCallDetail,
} from '@trishul/service-data-access';
import { PageHeader, StatusBadge, StatusSeverity } from '@trishul/shared-ui';

const STATUS_SEVERITY: Record<CallStatus, StatusSeverity> = {
  Logged: 'info',
  Assigned: 'info',
  'Call ID linked': 'info',
  'Customer contacted': 'info',
  'Trip started': 'warn',
  'Reached site': 'warn',
  'In progress': 'warn',
  'Report submitted': 'warn',
  'Awaiting parts': 'danger',
  'Parts ready': 'warn',
  'Revisit scheduled': 'warn',
  Closed: 'success',
  'Pending OEM closure': 'neutral',
  Completed: 'success',
  Reopened: 'danger',
  Cancelled: 'contrast',
};

const PRIORITY_SEVERITY: Record<CallPriority, StatusSeverity> = {
  Critical: 'danger',
  High: 'warn',
  Normal: 'info',
  Low: 'neutral',
};

/** Read-only detail of one service call (/service/calls/:callId). */
@Component({
  selector: 'trishul-call-detail-page',
  imports: [
    DatePipe,
    RouterLink,
    MatButton,
    MatIcon,
    MatProgressBar,
    PageHeader,
    StatusBadge,
  ],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './call-detail.page.html',
  styleUrl: './call-detail.page.scss',
})
export class CallDetailPage {
  private readonly api = inject(ServiceCallApi);
  private readonly router = inject(Router);

  readonly callId = input<string>();

  protected readonly loading = signal(true);
  protected readonly call = signal<ServiceCallDetail | null>(null);
  protected readonly statusSeverity = STATUS_SEVERITY;
  protected readonly prioritySeverity = PRIORITY_SEVERITY;

  constructor() {
    effect(() => {
      const id = this.callId();
      untracked(() => {
        if (id) this.load(Number(id));
      });
    });
  }

  private load(id: number): void {
    this.loading.set(true);
    this.api
      .get(id)
      .pipe(
        finalize(() => this.loading.set(false)),
        catchError(() => {
          void this.router.navigate(['/service/calls']);
          return EMPTY;
        }),
      )
      .subscribe((call) => this.call.set(call));
  }
}
