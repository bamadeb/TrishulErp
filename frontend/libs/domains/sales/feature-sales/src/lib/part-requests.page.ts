import { DatePipe } from '@angular/common';
import {
  ChangeDetectionStrategy,
  Component,
  inject,
  signal,
} from '@angular/core';
import { takeUntilDestroyed, toSignal } from '@angular/core/rxjs-interop';
import { MatButton } from '@angular/material/button';
import { MatDialog } from '@angular/material/dialog';
import {
  MatFormField,
  MatLabel,
  MatPrefix,
} from '@angular/material/form-field';
import { MatIcon } from '@angular/material/icon';
import { MatInput } from '@angular/material/input';
import { MatPaginator, PageEvent } from '@angular/material/paginator';
import { MatProgressBar } from '@angular/material/progress-bar';
import { MatOption, MatSelect } from '@angular/material/select';
import { Router, RouterLink } from '@angular/router';
import {
  ApiClient,
  ListPartRequestCalls$Params,
  PartRequestCall,
  PartRequestListItem,
  listPartRequestCalls,
  rejectPartRequest,
} from '@trishul/core-api';
import { HasPermission } from '@trishul/core-auth';
import { openFieldsDialog, pagedList } from '@trishul/inventory-data-access';
import {
  NO_SALES_OPTIONS,
  SAL_QUOTATION_MANAGE,
  SalesLookups,
} from '@trishul/sales-data-access';
import { PageHeader, StatusBadge, StatusSeverity } from '@trishul/shared-ui';
import { Subject, debounceTime, distinctUntilChanged, forkJoin } from 'rxjs';

type PartStatus = NonNullable<ListPartRequestCalls$Params['status']>;
const STATUSES: PartStatus[] = ['Requested', 'Quoted', 'Rejected'];
const SEVERITY: Record<string, StatusSeverity> = {
  Requested: 'warn',
  Quoted: 'success',
  Rejected: 'danger',
};

/**
 * Parts the engineers asked for, call by call (several engineers may ask on one call).
 * One line per call. "Create quotation" opens a new quotation filled with the call's waiting parts; it is
 * saved only when the user has checked it there (a part line removed there stays waiting).
 */
@Component({
  selector: 'trishul-part-requests-page',
  imports: [
    DatePipe,
    RouterLink,
    MatButton,
    MatIcon,
    MatFormField,
    MatLabel,
    MatPrefix,
    MatInput,
    MatSelect,
    MatOption,
    MatPaginator,
    MatProgressBar,
    HasPermission,
    PageHeader,
    StatusBadge,
  ],
  changeDetection: ChangeDetectionStrategy.OnPush,
  styleUrl: '../../../../inventory/data-access/src/lib/inventory.scss',
  styles: `
    td {
      vertical-align: top;
    }
    .part {
      white-space: nowrap;
    }
    .part .done {
      text-decoration: line-through;
      color: var(--mat-sys-on-surface-variant);
    }
    .actions {
      text-align: end;
      white-space: nowrap;
    }
    .actions button {
      display: flex;
      margin-inline-start: auto;
    }
    .actions button + button {
      margin-top: 4px;
    }
  `,
  template: `
    <trishul-page-header
      title="Parts requests"
      subtitle="Parts engineers requested, call by call: make a quotation or reject them"
    />
    <div class="filters">
      <mat-form-field
        class="search"
        appearance="outline"
        subscriptSizing="dynamic"
      >
        <mat-icon matPrefix>search</mat-icon>
        <input
          matInput
          type="search"
          placeholder="Call no, customer, part code or description"
          aria-label="Search parts requests"
          (input)="search$.next($any($event.target).value)"
        />
      </mat-form-field>
      <mat-form-field appearance="outline" subscriptSizing="dynamic">
        <mat-label>Status</mat-label>
        <mat-select
          [value]="query().status ?? null"
          (valueChange)="update({ status: $event })"
        >
          <mat-option [value]="null">All</mat-option>
          @for (s of statuses; track s) {
            <mat-option [value]="s">{{ s }}</mat-option>
          }
        </mat-select>
      </mat-form-field>
      <mat-form-field appearance="outline" subscriptSizing="dynamic">
        <mat-label>Branch</mat-label>
        <mat-select
          [value]="query().branchId ?? null"
          (valueChange)="update({ branchId: $event })"
        >
          <mat-option [value]="null">All</mat-option>
          @for (b of options().branches; track b.id) {
            <mat-option [value]="b.id">{{ b.name }}</mat-option>
          }
        </mat-select>
      </mat-form-field>
    </div>

    <div class="table-card">
      <div class="progress">
        @if (list.loading()) {
          <mat-progress-bar mode="indeterminate" />
        }
      </div>
      <div class="table-scroll">
        <table class="plain wide">
          <thead>
            <tr>
              <th>Requested</th>
              <th>Call</th>
              <th>Customer</th>
              <th>Parts</th>
              <th>Requested by</th>
              <th>Status</th>
              <th>Quotation / note</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            @for (c of list.items(); track c.serviceCallId) {
              <tr>
                <td class="nowrap">
                  {{ c.lastRequestedAt | date: 'dd MMM yyyy, HH:mm' }}
                  @if (c.requiredByDate) {
                    <div class="muted">
                      Needed by {{ c.requiredByDate | date: 'dd MMM' }}
                    </div>
                  }
                </td>
                <td class="nowrap">
                  <a
                    class="name"
                    [routerLink]="['/service/calls', c.serviceCallId]"
                    >{{ c.callNo }}</a
                  >
                  <div class="muted">{{ c.callStatus }}</div>
                </td>
                <td>
                  {{ c.customerName }}
                  <div class="muted">
                    {{ c.principalName }} · {{ c.branchName }}
                  </div>
                </td>
                <td>
                  @for (p of c.parts; track p.id) {
                    <div class="part">
                      <span [class.done]="p.status !== 'Requested'">{{
                        p.itemCode ?? p.partDescription
                      }}</span>
                      × {{ qty(p.quantity) }} {{ p.uomCode ?? '' }}
                      @if (p.status !== 'Requested') {
                        <span class="muted">({{ p.status }})</span>
                      }
                    </div>
                  }
                </td>
                <td>{{ c.requestedBy.join(', ') || '—' }}</td>
                <td>
                  <trishul-status-badge
                    [status]="status(c)"
                    [severities]="severity"
                  />
                  @if (c.waiting && c.waiting < c.parts.length) {
                    <div class="muted">{{ c.waiting }} waiting</div>
                  }
                </td>
                <td>
                  @for (q of quotations(c); track q.id) {
                    <div>
                      <a
                        class="name"
                        [routerLink]="['/sales/quotations', q.id]"
                        >{{ q.no }}</a
                      >
                    </div>
                  }
                  @for (n of notes(c); track n) {
                    <div class="muted">{{ n }}</div>
                  }
                </td>
                <td class="actions">
                  @if (c.waiting) {
                    <button
                      mat-flat-button
                      type="button"
                      *trishulHasPermission="quoteManage"
                      (click)="quote(c)"
                    >
                      <mat-icon>request_quote</mat-icon>Create quotation
                    </button>
                    <button mat-button type="button" (click)="reject(c)">
                      <mat-icon>block</mat-icon>Reject
                    </button>
                  }
                </td>
              </tr>
            } @empty {
              <tr>
                <td colspan="8" class="empty">
                  {{ list.loading() ? 'Loading…' : 'No parts requests match.' }}
                </td>
              </tr>
            }
          </tbody>
        </table>
      </div>
      <mat-paginator
        [length]="list.total()"
        [pageIndex]="(query().page ?? 1) - 1"
        [pageSize]="query().pageSize"
        [pageSizeOptions]="[10, 20, 50]"
        aria-label="Pages of calls with parts requests"
        (page)="onPage($event)"
      />
    </div>
  `,
})
export class PartRequestsPage {
  private readonly api = inject(ApiClient);
  private readonly dialog = inject(MatDialog);
  private readonly router = inject(Router);

  protected readonly quoteManage = SAL_QUOTATION_MANAGE;
  protected readonly statuses = STATUSES;
  protected readonly severity = SEVERITY;
  protected readonly options = toSignal(inject(SalesLookups).options(), {
    initialValue: NO_SALES_OPTIONS,
  });
  protected readonly query = signal<ListPartRequestCalls$Params>({
    page: 1,
    pageSize: 20,
    status: 'Requested',
  });
  protected readonly list = pagedList(this.query, (q) =>
    this.api.call(listPartRequestCalls, q),
  );
  protected readonly search$ = new Subject<string>();

  constructor() {
    this.search$
      .pipe(debounceTime(350), distinctUntilChanged(), takeUntilDestroyed())
      .subscribe((search) => this.update({ search: search.trim() || null }));
  }

  protected qty(value: string | number): string {
    return Number(value).toLocaleString('en-IN', { maximumFractionDigits: 3 });
  }

  protected update(change: Partial<ListPartRequestCalls$Params>): void {
    this.query.update((q) => ({ ...q, ...change, page: change.page ?? 1 }));
  }

  protected onPage(event: PageEvent): void {
    this.update({ page: event.pageIndex + 1, pageSize: event.pageSize });
  }

  /** The call's parts still waiting for the office. */
  private waitingParts(call: PartRequestCall): PartRequestListItem[] {
    return call.parts.filter((p) => p.status === 'Requested');
  }

  /** Requested while any part waits; otherwise Quoted if any part was quoted, else Rejected. */
  protected status(call: PartRequestCall): string {
    if (call.waiting) return 'Requested';
    return call.parts.some((p) => p.status === 'Quoted')
      ? 'Quoted'
      : 'Rejected';
  }

  protected quotations(call: PartRequestCall): { id: number; no: string }[] {
    const seen = new Map<number, string>();
    for (const p of call.parts)
      if (p.quotationId) seen.set(p.quotationId, p.quotationNo ?? '');
    return [...seen].map(([id, no]) => ({ id, no }));
  }

  protected notes(call: PartRequestCall): string[] {
    return [
      ...new Set(
        call.parts
          .filter((p) => p.reviewNote)
          .map((p) => `${p.itemCode ?? p.partDescription}: ${p.reviewNote}`),
      ),
    ];
  }

  /** Opens a new quotation filled with the call's waiting parts; nothing is saved until the user saves it there. */
  protected quote(call: PartRequestCall): void {
    const ids = this.waitingParts(call).map((p) => p.id);
    void this.router.navigate(['/sales/quotations/new'], {
      queryParams: { partRequests: ids.join(',') },
    });
  }

  protected reject(call: PartRequestCall): void {
    const parts = this.waitingParts(call);
    openFieldsDialog(this.dialog, {
      title: `Reject ${parts.length} part${parts.length === 1 ? '' : 's'} of ${call.callNo}`,
      submitText: 'Reject',
      fields: [
        {
          key: 'note',
          label: 'Why (the engineer sees this)',
          type: 'textarea',
          required: true,
          maxLength: 300,
        },
      ],
      save: (v) =>
        forkJoin(
          parts.map((p) =>
            this.api.call(rejectPartRequest, {
              partRequestId: p.id,
              body: { note: v['note'] as string },
            }),
          ),
        ),
    }).subscribe((done) => {
      if (done) this.list.reload();
    });
  }
}
