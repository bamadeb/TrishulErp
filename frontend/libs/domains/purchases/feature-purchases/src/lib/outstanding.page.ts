import { DatePipe, DecimalPipe } from '@angular/common';
import {
  ChangeDetectionStrategy,
  Component,
  inject,
  signal,
} from '@angular/core';
import { takeUntilDestroyed, toSignal } from '@angular/core/rxjs-interop';
import { MatButton } from '@angular/material/button';
import { MatCheckbox } from '@angular/material/checkbox';
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
import { RouterLink } from '@angular/router';
import {
  ApiClient,
  ListOutstandingPoLines$Params,
  listOutstandingPoLines,
} from '@trishul/core-api';
import { AuthStore } from '@trishul/core-auth';
import {
  InventoryLookups,
  downloadCsv,
  n0,
  pagedList,
} from '@trishul/inventory-data-access';
import { PUR_GRN_MANAGE } from '@trishul/purchases-data-access';
import { PageHeader, StatusBadge } from '@trishul/shared-ui';
import { Subject, debounceTime, distinctUntilChanged } from 'rxjs';
import { PO_STATUS, rupees } from './purchases.shared';

/** Order lines still to be received: ordered, received, pending, by order and item. */
@Component({
  selector: 'trishul-outstanding-page',
  imports: [
    DatePipe,
    DecimalPipe,
    RouterLink,
    MatButton,
    MatIcon,
    MatCheckbox,
    MatFormField,
    MatLabel,
    MatPrefix,
    MatInput,
    MatSelect,
    MatOption,
    MatPaginator,
    MatProgressBar,
    PageHeader,
    StatusBadge,
  ],
  changeDetection: ChangeDetectionStrategy.OnPush,
  styleUrl: '../../../../inventory/data-access/src/lib/inventory.scss',
  template: `
    <trishul-page-header
      title="Outstanding purchase orders"
      subtitle="Approved orders with goods still to come; each GRN reduces what is pending"
    >
      <button mat-stroked-button (click)="export()">
        <mat-icon>download</mat-icon>Export page
      </button>
    </trishul-page-header>
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
          placeholder="PO no, item or supplier"
          aria-label="Search"
          (input)="search$.next($any($event.target).value)"
        />
      </mat-form-field>
      <mat-form-field appearance="outline" subscriptSizing="dynamic">
        <mat-label>Supplier</mat-label>
        <mat-select
          [value]="query().supplierId ?? null"
          (valueChange)="update({ supplierId: $event })"
        >
          <mat-option [value]="null">All</mat-option>
          @for (s of suppliers(); track s.id) {
            <mat-option [value]="s.id">{{ s.name }}</mat-option>
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
          @for (b of branches(); track b.id) {
            <mat-option [value]="b.id">{{ b.name }}</mat-option>
          }
        </mat-select>
      </mat-form-field>
      <mat-checkbox
        [checked]="!!query().overdueOnly"
        (change)="update({ overdueOnly: $event.checked })"
      >
        Past the expected date
      </mat-checkbox>
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
              <th>Order</th>
              <th>Supplier</th>
              <th>Item</th>
              <th class="num">Ordered</th>
              <th class="num">Received</th>
              <th class="num">Pending</th>
              <th class="num">Pending value</th>
              <th>Expected</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            @for (o of list.items(); track o.lineId) {
              <tr>
                <td>
                  <a
                    class="name"
                    [routerLink]="['/purchases/orders', o.purchaseOrderId]"
                    >{{ o.poNo }}</a
                  >
                  <div class="muted">
                    {{ o.poDate | date: 'dd MMM yyyy' }} · {{ o.daysOpen }} days
                  </div>
                  <trishul-status-badge
                    [status]="o.status"
                    [severities]="statusSeverity"
                  />
                </td>
                <td>
                  {{ o.supplierName }}
                  <div class="muted">{{ o.branchName }}</div>
                </td>
                <td>
                  {{ o.itemCode }}
                  <div class="muted">{{ o.itemDescription }}</div>
                </td>
                <td class="num">
                  {{ o.qtyOrdered | number: '1.0-3' }} {{ o.uomCode }}
                </td>
                <td class="num">{{ o.qtyReceived | number: '1.0-3' }}</td>
                <td class="num negative">
                  {{ o.qtyPending | number: '1.0-3' }}
                </td>
                <td class="num">{{ money(o.pendingValue) }}</td>
                <td class="nowrap" [class.negative]="late(o.expectedDate)">
                  {{
                    o.expectedDate
                      ? (o.expectedDate | date: 'dd MMM yyyy')
                      : '—'
                  }}
                </td>
                <td class="actions">
                  @if (canReceive) {
                    <a
                      mat-button
                      routerLink="/purchases/grns/new"
                      [queryParams]="{ poId: o.purchaseOrderId }"
                      >Receive</a
                    >
                  }
                </td>
              </tr>
            } @empty {
              <tr>
                <td colspan="9" class="empty">
                  {{ list.loading() ? 'Loading…' : 'Nothing outstanding.' }}
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
        [pageSizeOptions]="[50, 100, 200]"
        aria-label="Pages"
        (page)="onPage($event)"
      />
    </div>
  `,
})
export class OutstandingPage {
  private readonly api = inject(ApiClient);
  private readonly lookups = inject(InventoryLookups);
  protected readonly canReceive =
    inject(AuthStore).hasPermission(PUR_GRN_MANAGE);
  protected readonly statusSeverity = PO_STATUS;
  protected readonly money = rupees;

  protected readonly suppliers = toSignal(this.lookups.suppliers(), {
    initialValue: [],
  });
  protected readonly branches = toSignal(this.lookups.branches(), {
    initialValue: [],
  });
  protected readonly query = signal<ListOutstandingPoLines$Params>({
    page: 1,
    pageSize: 50,
  });
  protected readonly list = pagedList(this.query, (q) =>
    this.api.call(listOutstandingPoLines, q),
  );
  protected readonly search$ = new Subject<string>();
  private readonly today = new Date().toLocaleDateString('en-CA');

  constructor() {
    this.search$
      .pipe(debounceTime(350), distinctUntilChanged(), takeUntilDestroyed())
      .subscribe((search) => this.update({ search: search.trim() || null }));
  }

  protected update(change: Partial<ListOutstandingPoLines$Params>): void {
    this.query.update((q) => ({ ...q, ...change, page: change.page ?? 1 }));
  }

  protected onPage(event: PageEvent): void {
    this.update({ page: event.pageIndex + 1, pageSize: event.pageSize });
  }

  protected late(expected: string | null): boolean {
    return !!expected && expected < this.today;
  }

  protected export(): void {
    downloadCsv(
      'outstanding-purchase-orders.csv',
      [
        'PO no',
        'PO date',
        'Supplier',
        'Branch',
        'Item',
        'Description',
        'Ordered',
        'Received',
        'Pending',
        'Pending value',
        'Expected',
      ],
      this.list
        .items()
        .map((o) => [
          o.poNo,
          o.poDate,
          o.supplierName,
          o.branchName,
          o.itemCode,
          o.itemDescription,
          n0(o.qtyOrdered),
          n0(o.qtyReceived),
          n0(o.qtyPending),
          n0(o.pendingValue),
          o.expectedDate,
        ]),
    );
  }
}
