import { DatePipe } from '@angular/common';
import {
  ChangeDetectionStrategy,
  Component,
  computed,
  effect,
  inject,
  input,
  signal,
  untracked,
} from '@angular/core';
import { MatProgressBar } from '@angular/material/progress-bar';
import { MatTableModule } from '@angular/material/table';
import { RouterLink } from '@angular/router';
import { EMPTY, catchError, finalize } from 'rxjs';
import {
  AscApi,
  AscVisitDay,
  ServiceContractDetail,
} from '@trishul/service-data-access';

/**
 * The ASC page's visit history: every day one or more engineers were on site for one of its service calls.
 * Each day used one visit of the ASC, however many engineers went.
 */
@Component({
  selector: 'trishul-asc-visit-days',
  imports: [DatePipe, MatProgressBar, MatTableModule, RouterLink],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <h2>ASC visit history</h2>
    <p class="muted">
      Each day one or more engineers reach the site of a service call uses one
      visit, counted automatically when the engineer ends the trip to the site.
      @if (days().length) {
        {{ days().length }} {{ days().length === 1 ? 'day' : 'days' }} on
        {{ callCount() }} {{ callCount() === 1 ? 'call' : 'calls' }}.
      }
    </p>

    <div class="progress">
      @if (loading()) {
        <mat-progress-bar mode="indeterminate" />
      }
    </div>

    <div class="table-scroll">
      <table mat-table [dataSource]="days()">
        <ng-container matColumnDef="date">
          <th mat-header-cell *matHeaderCellDef>Date</th>
          <td mat-cell *matCellDef="let d">
            <b>{{ d.visitDate | date: 'dd MMM yyyy' }}</b>
            <div class="muted">{{ d.visitDate | date: 'EEEE' }}</div>
          </td>
        </ng-container>

        <ng-container matColumnDef="call">
          <th mat-header-cell *matHeaderCellDef>Service call</th>
          <td mat-cell *matCellDef="let d">
            <a [routerLink]="['/service/calls', d.serviceCallId]">{{ d.callNo }}</a>
            <div class="muted">{{ d.callStatus }}</div>
            <div class="complaint muted">{{ d.complaintDescription }}</div>
          </td>
        </ng-container>

        <ng-container matColumnDef="engineers">
          <th mat-header-cell *matHeaderCellDef>Engineers on site</th>
          <td mat-cell *matCellDef="let d">
            @for (e of d.engineers; track e.employeeId) {
              <div class="engineer">
                <span>
                  {{ e.name }}
                  @if (e.employeeCode) {
                    <span class="muted">· {{ e.employeeCode }}</span>
                  }
                </span>
                <span class="muted">
                  reached {{ e.reachedAt | date: 'HH:mm' }}
                  @if (e.leftAt) {
                    · left {{ e.leftAt | date: 'HH:mm' }}
                  }
                </span>
              </div>
            } @empty {
              <span class="muted">—</span>
            }
          </td>
        </ng-container>

        <ng-container matColumnDef="visits">
          <th mat-header-cell *matHeaderCellDef class="num">Visit used</th>
          <td mat-cell *matCellDef="let d" class="num">1</td>
        </ng-container>

        <tr mat-header-row *matHeaderRowDef="columns"></tr>
        <tr mat-row *matRowDef="let row; columns: columns"></tr>
        <tr class="mat-mdc-row" *matNoDataRow>
          <td class="empty" [attr.colspan]="columns.length">
            {{ loading() ? 'Loading…' : 'No engineer has been on site for this ASC yet.' }}
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
    td {
      vertical-align: top;
      padding-top: 0.5rem;
      padding-bottom: 0.5rem;
    }
    .num {
      text-align: right;
      white-space: nowrap;
    }
    .complaint {
      display: -webkit-box;
      -webkit-box-orient: vertical;
      -webkit-line-clamp: 1;
      line-clamp: 1;
      overflow: hidden;
      max-width: 22rem;
    }
    .engineer {
      display: flex;
      flex-direction: column;
      & + .engineer {
        margin-top: 0.35rem;
      }
    }
    .empty {
      padding: 1.5rem;
      text-align: center;
      color: var(--mat-sys-on-surface-variant);
    }
  `,
})
export class AscVisitDays {
  private readonly api = inject(AscApi);

  readonly contract = input.required<ServiceContractDetail>();

  protected readonly days = signal<AscVisitDay[]>([]);
  protected readonly loading = signal(false);
  protected readonly columns = ['date', 'call', 'engineers', 'visits'];
  protected readonly callCount = computed(
    () => new Set(this.days().map((d) => d.serviceCallId)).size,
  );

  constructor() {
    // Reloads whenever the contract changes (also after a count is corrected above).
    effect(() => {
      const contract = this.contract();
      untracked(() => this.load(contract.id));
    });
  }

  private load(contractId: number): void {
    this.loading.set(true);
    this.api
      .visitDays(contractId)
      .pipe(
        finalize(() => this.loading.set(false)),
        catchError(() => EMPTY), // the error toast has been shown
      )
      .subscribe((days) => this.days.set(days));
  }
}
