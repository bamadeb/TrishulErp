import { DatePipe } from '@angular/common';
import { ChangeDetectionStrategy, Component, effect, inject, input, output, signal } from '@angular/core';
import { MatButton, MatIconButton } from '@angular/material/button';
import { MatIcon } from '@angular/material/icon';
import { MatProgressBar } from '@angular/material/progress-bar';
import { LeaveApi, MineApprovalStep } from '@trishul/hr-data-access';
import { StatusBadge, StatusSeverity } from '@trishul/shared-ui';
import { MineLeaveRequest } from './leave-mine.models';

export interface LeaveDrawerBalance {
  leaveTypeId: number;
  available: number;
}

@Component({
  selector: 'trishul-leave-request-drawer',
  imports: [DatePipe, MatButton, MatIcon, MatIconButton, MatProgressBar, StatusBadge],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './leave-mine.drawer.html',
  styleUrl: './leave-mine.drawer.scss',
})
export class LeaveRequestDrawer {
  private readonly api = inject(LeaveApi);

  readonly request = input.required<MineLeaveRequest>();
  readonly employeeName = input('');
  readonly balance = input<LeaveDrawerBalance | null>(null);
  readonly closed = output<void>();
  readonly withdraw = output<MineLeaveRequest>();

  protected readonly severities: Partial<Record<string, StatusSeverity>> = {
    Pending: 'warn',
    Approved: 'success',
    Rejected: 'danger',
    Cancelled: 'neutral',
  };
  protected readonly steps = signal<MineApprovalStep[]>([]);
  protected readonly stepsError = signal('');
  protected readonly loading = signal(false);

  constructor() {
    effect((onCleanup) => {
      const id = this.request().requestId;
      this.loading.set(true);
      this.stepsError.set('');
      const subscription = this.api.mineRequest(id).subscribe({
        next: (detail) => {
          this.steps.set(detail.approvalSteps ?? []);
          this.loading.set(false);
        },
        error: () => {
          this.stepsError.set('Approval details could not be loaded.');
          this.loading.set(false);
        },
      });
      onCleanup(() => subscription.unsubscribe());
    });
  }

  protected amount(value: number): string {
    return Number.isInteger(value) ? String(value) : value.toFixed(1);
  }

  protected availableLabel(): string {
    const card = this.balance();
    return card ? `${this.amount(card.available)} Days` : '—';
  }

  protected afterLabel(): string {
    const card = this.balance();
    if (!card) return '—';
    const value = this.request().status === 'Pending' ? card.available - this.request().days : card.available;
    return `${this.amount(value)} Days`;
  }

  protected heading(step: MineApprovalStep): string {
    if (step.status === 'Submitted' || step.title === 'Request Submitted') return 'Request Submitted';
    if (step.title === 'Reporting Manager' || step.level === 'Reporting Manager' || step.level === 'Level 1') {
      return 'Reporting Manager';
    }
    if (step.title === 'Approved' || (step.status === 'Approved' && !step.approverRole)) return 'Approved';
    if (step.title === 'Rejected' || (step.status === 'Rejected' && !step.approverRole)) return 'Rejected';
    if (step.title === 'Approved / Rejected' || step.status === 'Upcoming') return 'Approved / Rejected';
    return step.title || 'Reporting Manager';
  }

  protected stateLabel(step: MineApprovalStep): string {
    if (step.status === 'Submitted') return 'Completed';
    if (step.status === 'Upcoming') return 'Upcoming';
    return step.status;
  }

  protected person(step: MineApprovalStep): string {
    if (step.approverName) return step.approverName;
    if (step.status === 'Submitted' || step.title === 'Request Submitted') return this.employeeName();
    if (step.title === 'Approved' || step.title === 'Rejected' || step.title === 'Approved / Rejected') {
      return step.title;
    }
    return 'Awaiting Reporting Manager';
  }
}
