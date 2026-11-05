import { DatePipe } from '@angular/common';
import {
  ChangeDetectionStrategy,
  Component,
  computed,
  effect,
  inject,
  input,
  output,
  signal,
  untracked,
} from '@angular/core';
import { MatButton } from '@angular/material/button';
import { MatDialog } from '@angular/material/dialog';
import { MatProgressBar } from '@angular/material/progress-bar';
import { MatSnackBar } from '@angular/material/snack-bar';
import { MatTableModule } from '@angular/material/table';
import { MatTooltip } from '@angular/material/tooltip';
import { RouterLink } from '@angular/router';
import { EMPTY, catchError, filter, finalize } from 'rxjs';
import { AuthStore } from '@trishul/core-auth';
import {
  ASC_VISIT_PERMISSION,
  AscApi,
  AscCallVisit,
  ServiceContractDetail,
} from '@trishul/service-data-access';
import { AscVisitDialog, AscVisitDialogData } from './asc-visit.dialog';

/** Why a call's visits can't be changed right now, or null when they can. */
export function countBlocked(
  contract: ServiceContractDetail,
  call: AscCallVisit,
): string | null {
  if (contract.state === 'Cancelled') return 'This ASC is cancelled.';
  if (!call.countable) return 'Finish the call to change its visits.';
  if (call.visits === 0 && contract.visitsRemaining === 0) {
    return 'No visits are left on this ASC.';
  }
  return null;
}

/** The ASC page's list of finished service calls: the ASC Manager counts each one's visits here. */
@Component({
  selector: 'trishul-asc-call-visits',
  imports: [DatePipe, MatButton, MatProgressBar, MatTableModule, MatTooltip, RouterLink],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <h2>Visits from service calls</h2>
    <p class="muted">
      One completed call counts as one visit unless more were needed.
      @if (fromRegister() > 0) {
        {{ fromRegister() }} of the {{ contract().visitsUsed }} visits used
        came from the register or the form above.
      }
    </p>

    <div class="progress">
      @if (loading()) {
        <mat-progress-bar mode="indeterminate" />
      }
    </div>

    <div class="table-scroll">
      <table mat-table [dataSource]="calls()">
        <ng-container matColumnDef="call">
          <th mat-header-cell *matHeaderCellDef>Call</th>
          <td mat-cell *matCellDef="let c">
            <a [routerLink]="['/service/calls', c.serviceCallId]">{{ c.callNo }}</a>
            <div class="muted">{{ c.currentStatus }}</div>
          </td>
        </ng-container>

        <ng-container matColumnDef="complaint">
          <th mat-header-cell *matHeaderCellDef>Complaint</th>
          <td mat-cell *matCellDef="let c">
            <div class="complaint">{{ c.complaintDescription }}</div>
            @if (c.engineerName) {
              <div class="muted">{{ c.engineerName }}</div>
            }
          </td>
        </ng-container>

        <ng-container matColumnDef="finished">
          <th mat-header-cell *matHeaderCellDef>Finished</th>
          <td mat-cell *matCellDef="let c">
            {{ c.finishedAt ? (c.finishedAt | date: 'dd MMM yyyy') : '—' }}
          </td>
        </ng-container>

        <ng-container matColumnDef="visits">
          <th mat-header-cell *matHeaderCellDef class="num">Visits</th>
          <td mat-cell *matCellDef="let c" class="num">
            @if (c.visits) {
              <b>{{ c.visits }}</b>
            } @else {
              <span class="muted">Not counted</span>
            }
          </td>
        </ng-container>

        <ng-container matColumnDef="remarks">
          <th mat-header-cell *matHeaderCellDef>Remarks</th>
          <td mat-cell *matCellDef="let c">{{ c.remarks ?? '—' }}</td>
        </ng-container>

        <ng-container matColumnDef="action">
          <th mat-header-cell *matHeaderCellDef></th>
          <td mat-cell *matCellDef="let c" class="num">
            @let blocked = blockedReason(c);
            <span [matTooltip]="blocked ?? ''" [matTooltipDisabled]="!blocked">
              <button
                mat-stroked-button
                type="button"
                [disabled]="!!blocked"
                (click)="count(c)"
              >
                {{ c.visits ? 'Change' : 'Count' }}
              </button>
            </span>
          </td>
        </ng-container>

        <tr mat-header-row *matHeaderRowDef="columns()"></tr>
        <tr mat-row *matRowDef="let row; columns: columns()"></tr>
        <tr class="mat-mdc-row" *matNoDataRow>
          <td class="empty" [attr.colspan]="columns().length">
            {{ loading() ? 'Loading…' : 'No completed service calls under this ASC yet.' }}
          </td>
        </tr>
      </table>
    </div>
  `,
  styles: `
    h2 {
      margin: 0 0 0.25rem;
      font: var(--mat-sys-title-medium);
    }
    .muted {
      margin: 0;
      font: var(--mat-sys-body-small);
      color: var(--mat-sys-on-surface-variant);
    }
    .progress {
      height: 4px;
      margin: 0.5rem 0 0.25rem;
    }
    .table-scroll {
      overflow-x: auto;
    }
    table {
      width: 100%;
      min-width: 640px;
      background: transparent;
    }
    .num {
      text-align: right;
      white-space: nowrap;
    }
    .complaint {
      display: -webkit-box;
      -webkit-box-orient: vertical;
      -webkit-line-clamp: 2;
      line-clamp: 2;
      overflow: hidden;
    }
    .empty {
      padding: 1.5rem;
      text-align: center;
      color: var(--mat-sys-on-surface-variant);
    }
  `,
})
export class AscCallVisits {
  private readonly api = inject(AscApi);
  private readonly dialog = inject(MatDialog);
  private readonly snackBar = inject(MatSnackBar);
  private readonly canCount = inject(AuthStore).hasPermission(
    ASC_VISIT_PERMISSION,
  );

  readonly contract = input.required<ServiceContractDetail>();
  /** The ASC after a count; the parent passes it back in, which reloads the list. */
  readonly updated = output<ServiceContractDetail>();

  protected readonly calls = signal<AscCallVisit[]>([]);
  protected readonly loading = signal(false);
  protected readonly columns = computed(() => [
    'call',
    'complaint',
    'finished',
    'visits',
    'remarks',
    ...(this.canCount ? ['action'] : []),
  ]);
  /** Visits in the total that didn't come from these calls. */
  protected readonly fromRegister = computed(
    () =>
      this.contract().visitsUsed -
      this.calls().reduce((sum, call) => sum + call.visits, 0),
  );

  constructor() {
    effect(() => {
      const id = this.contract().id;
      untracked(() => this.load(id));
    });
  }

  protected blockedReason(call: AscCallVisit): string | null {
    return countBlocked(this.contract(), call);
  }

  protected count(call: AscCallVisit): void {
    const data: AscVisitDialogData = { contract: this.contract(), call };
    this.dialog
      .open<AscVisitDialog, AscVisitDialogData, ServiceContractDetail>(
        AscVisitDialog,
        { data },
      )
      .afterClosed()
      .pipe(filter((saved) => !!saved))
      .subscribe((saved) => {
        this.snackBar.open(
          `${call.callNo} saved: ${saved.visitsUsed} visits used`,
          'OK',
          { duration: 5000 },
        );
        this.updated.emit(saved);
      });
  }

  private load(contractId: number): void {
    this.loading.set(true);
    this.api
      .callVisits(contractId)
      .pipe(
        finalize(() => this.loading.set(false)),
        catchError(() => EMPTY), // the error toast has been shown
      )
      .subscribe((calls) => this.calls.set(calls));
  }
}
