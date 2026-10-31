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
import {
  FormControl,
  ReactiveFormsModule,
  Validators,
} from '@angular/forms';
import { MatButton } from '@angular/material/button';
import { MatFormField, MatLabel } from '@angular/material/form-field';
import { MatIcon } from '@angular/material/icon';
import { MatInput } from '@angular/material/input';
import { MatProgressBar } from '@angular/material/progress-bar';
import { MatOption, MatSelect } from '@angular/material/select';
import { MatSnackBar } from '@angular/material/snack-bar';
import { Router, RouterLink } from '@angular/router';
import { EMPTY, catchError, finalize } from 'rxjs';
import {
  CallPriority,
  CallStatus,
  CallStatusLogItem,
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

/** One service call (/service/calls/:callId): details, status change and the status history. */
@Component({
  selector: 'trishul-call-detail-page',
  imports: [
    DatePipe,
    RouterLink,
    ReactiveFormsModule,
    MatButton,
    MatFormField,
    MatLabel,
    MatIcon,
    MatInput,
    MatProgressBar,
    MatSelect,
    MatOption,
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
  private readonly snackBar = inject(MatSnackBar);

  readonly callId = input<string>();

  protected readonly loading = signal(true);
  protected readonly saving = signal(false);
  protected readonly call = signal<ServiceCallDetail | null>(null);
  protected readonly history = signal<CallStatusLogItem[]>([]);
  protected readonly statusSeverity = STATUS_SEVERITY;
  protected readonly prioritySeverity = PRIORITY_SEVERITY;

  protected readonly newStatus = new FormControl<CallStatus | null>(null, {
    validators: Validators.required,
  });
  protected readonly remarks = new FormControl('', {
    nonNullable: true,
    validators: Validators.maxLength(500),
  });

  constructor() {
    effect(() => {
      const id = this.callId();
      untracked(() => {
        if (id) this.load(Number(id));
      });
    });
  }

  protected changeStatus(): void {
    const call = this.call();
    const status = this.newStatus.value;
    if (!call || !status || this.remarks.invalid || this.saving()) return;
    this.saving.set(true);
    this.api
      .changeStatus(call.id, call.rowVersion, {
        status,
        remarks: this.remarks.value.trim() || null,
      })
      .pipe(
        finalize(() => this.saving.set(false)),
        catchError(() => {
          this.load(call.id); // e.g. 409: someone else changed it, so show the current state
          return EMPTY;
        }),
      )
      .subscribe((updated) => {
        this.call.set(updated);
        this.newStatus.reset();
        this.remarks.reset('');
        this.loadHistory(call.id);
        this.snackBar.open(`Status changed to ${updated.currentStatus}`, 'OK', {
          duration: 4000,
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
      .subscribe((call) => {
        this.call.set(call);
        this.loadHistory(id);
      });
  }

  private loadHistory(id: number): void {
    this.api
      .statusHistory(id)
      .pipe(catchError(() => EMPTY))
      .subscribe((rows) => this.history.set(rows));
  }
}
