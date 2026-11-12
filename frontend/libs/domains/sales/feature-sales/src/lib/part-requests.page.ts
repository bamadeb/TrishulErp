import { DatePipe } from '@angular/common';
import {
  ChangeDetectionStrategy,
  Component,
  computed,
  inject,
  signal,
} from '@angular/core';
import { takeUntilDestroyed, toSignal } from '@angular/core/rxjs-interop';
import { MatButton } from '@angular/material/button';
import { MatCheckbox } from '@angular/material/checkbox';
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
  ListPartRequests$Params,
  PartRequestListItem,
  createPartRequestQuotation,
  listPartRequests,
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

type PartStatus = NonNullable<ListPartRequests$Params['status']>;
const STATUSES: PartStatus[] = ['Requested', 'Quoted', 'Rejected'];
const SEVERITY: Record<string, StatusSeverity> = {
  Requested: 'warn',
  Quoted: 'success',
  Rejected: 'danger',
};

/** Parts the engineers asked for on their calls: the office quotes them (a draft quotation) or rejects them. */
@Component({
  selector: 'trishul-part-requests-page',
  imports: [
    DatePipe,
    RouterLink,
    MatButton,
    MatCheckbox,
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
  template: `
    <trishul-page-header
      title="Parts requests"
      subtitle="Parts engineers requested on their service calls: make a quotation or reject them"
    >
      @if (selected().length) {
        <button mat-stroked-button type="button" (click)="reject()">
          <mat-icon>block</mat-icon>Reject ({{ selected().length }})
        </button>
        <button
          mat-flat-button
          type="button"
          *trishulHasPermission="quoteManage"
          [disabled]="!oneCustomer() || busy()"
          (click)="quote()"
        >
          <mat-icon>request_quote</mat-icon>Create quotation ({{
            selected().length
          }})
        </button>
      }
    </trishul-page-header>
    @if (selected().length && !oneCustomer()) {
      <p class="muted" role="status">
        A quotation is for one customer, brand and branch: choose parts of one
        call (or of calls of the same customer).
      </p>
    }
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
        @if (list.loading() || busy()) {
          <mat-progress-bar mode="indeterminate" />
        }
      </div>
      <div class="table-scroll">
        <table class="plain wide">
          <thead>
            <tr>
              <th>
                <mat-checkbox
                  aria-label="Select all waiting parts on this page"
                  [checked]="allChosen()"
                  [indeterminate]="selected().length > 0 && !allChosen()"
                  [disabled]="!waiting().length"
                  (change)="toggleAll($event.checked)"
                />
              </th>
              <th>Requested</th>
              <th>Call</th>
              <th>Customer</th>
              <th>Part</th>
              <th class="num">Qty</th>
              <th>Requested by</th>
              <th>Status</th>
              <th>Quotation / note</th>
            </tr>
          </thead>
          <tbody>
            @for (p of list.items(); track p.id) {
              <tr>
                <td>
                  @if (p.status === 'Requested') {
                    <mat-checkbox
                      [attr.aria-label]="
                        'Select ' + (p.itemCode ?? p.partDescription)
                      "
                      [checked]="chosen().has(p.id)"
                      (change)="toggle(p, $event.checked)"
                    />
                  }
                </td>
                <td class="nowrap">
                  {{ p.createdAt | date: 'dd MMM yyyy, HH:mm' }}
                  @if (p.requiredByDate) {
                    <div class="muted">
                      Needed by {{ p.requiredByDate | date: 'dd MMM' }}
                    </div>
                  }
                </td>
                <td class="nowrap">
                  <a
                    class="name"
                    [routerLink]="['/service/calls', p.serviceCallId]"
                    >{{ p.callNo }}</a
                  >
                  <div class="muted">{{ p.callStatus }}</div>
                </td>
                <td>
                  {{ p.customerName }}
                  <div class="muted">
                    {{ p.principalName }} · {{ p.branchName }}
                  </div>
                </td>
                <td>
                  {{ p.itemCode ?? 'Not in item master' }}
                  <div class="muted">{{ p.partDescription }}</div>
                  @if (!p.isChargeable) {
                    <div class="muted">Not chargeable (warranty / ASC)</div>
                  }
                </td>
                <td class="num nowrap">
                  {{ qty(p.quantity) }} {{ p.uomCode ?? '' }}
                </td>
                <td>{{ p.requestedByName ?? '—' }}</td>
                <td>
                  <trishul-status-badge
                    [status]="p.status"
                    [severities]="severity"
                  />
                </td>
                <td>
                  @if (p.quotationId) {
                    <a
                      class="name"
                      [routerLink]="['/sales/quotations', p.quotationId]"
                      >{{ p.quotationNo }}</a
                    >
                  }
                  @if (p.reviewNote) {
                    <div class="muted">{{ p.reviewNote }}</div>
                  }
                  @if (p.reviewedBy) {
                    <div class="muted">
                      {{ p.reviewedBy }},
                      {{ p.reviewedAt | date: 'dd MMM, HH:mm' }}
                    </div>
                  }
                </td>
              </tr>
            } @empty {
              <tr>
                <td colspan="9" class="empty">
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
        [pageSizeOptions]="[20, 50, 100]"
        aria-label="Pages of parts requests"
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
  protected readonly query = signal<ListPartRequests$Params>({
    page: 1,
    pageSize: 50,
    status: 'Requested',
  });
  protected readonly list = pagedList(this.query, (q) =>
    this.api.call(listPartRequests, q),
  );
  protected readonly search$ = new Subject<string>();
  protected readonly busy = signal(false);

  /** The ticked parts, by id (kept across pages until they are reviewed). */
  protected readonly chosen = signal(new Map<number, PartRequestListItem>());
  protected readonly selected = computed(() => [...this.chosen().values()]);
  protected readonly waiting = computed(() =>
    this.list.items().filter((p) => p.status === 'Requested'),
  );
  protected readonly allChosen = computed(
    () =>
      this.waiting().length > 0 &&
      this.waiting().every((p) => this.chosen().has(p.id)),
  );
  /** One quotation: one customer, brand and branch. */
  protected readonly oneCustomer = computed(() => {
    const keys = new Set(
      this.selected().map(
        (p) => `${p.customerId}:${p.principalId}:${p.branchId}`,
      ),
    );
    return keys.size === 1;
  });

  constructor() {
    this.search$
      .pipe(debounceTime(350), distinctUntilChanged(), takeUntilDestroyed())
      .subscribe((search) => this.update({ search: search.trim() || null }));
  }

  protected qty(value: string | number): string {
    return Number(value).toLocaleString('en-IN', { maximumFractionDigits: 3 });
  }

  protected update(change: Partial<ListPartRequests$Params>): void {
    this.query.update((q) => ({ ...q, ...change, page: change.page ?? 1 }));
  }

  protected onPage(event: PageEvent): void {
    this.update({ page: event.pageIndex + 1, pageSize: event.pageSize });
  }

  protected toggle(part: PartRequestListItem, checked: boolean): void {
    this.chosen.update((map) => {
      const next = new Map(map);
      if (checked) next.set(part.id, part);
      else next.delete(part.id);
      return next;
    });
  }

  protected toggleAll(checked: boolean): void {
    this.chosen.update((map) => {
      const next = new Map(map);
      for (const p of this.waiting()) {
        if (checked) next.set(p.id, p);
        else next.delete(p.id);
      }
      return next;
    });
  }

  /** A draft quotation with the ticked parts; opens it to set prices and send. */
  protected quote(): void {
    const ids = this.selected().map((p) => p.id);
    this.busy.set(true);
    this.api
      .call(createPartRequestQuotation, { body: { partRequestIds: ids } })
      .subscribe({
        next: (result) => {
          this.busy.set(false);
          this.chosen.set(new Map());
          void this.router.navigate(['/sales/quotations', result.quotationId]);
        },
        error: () => {
          this.busy.set(false);
          this.list.reload();
        },
      });
  }

  protected reject(): void {
    const parts = this.selected();
    openFieldsDialog(this.dialog, {
      title: `Reject ${parts.length} part${parts.length === 1 ? '' : 's'}`,
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
      if (!done) return;
      this.chosen.set(new Map());
      this.list.reload();
    });
  }
}
