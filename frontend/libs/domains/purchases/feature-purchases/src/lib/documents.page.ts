import { DatePipe, DecimalPipe } from '@angular/common';
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
import { takeUntilDestroyed, toSignal } from '@angular/core/rxjs-interop';
import { MatButton } from '@angular/material/button';
import { provideNativeDateAdapter } from '@angular/material/core';
import {
  MatDatepicker,
  MatDatepickerInput,
  MatDatepickerToggle,
} from '@angular/material/datepicker';
import {
  MatFormField,
  MatLabel,
  MatPrefix,
  MatSuffix,
} from '@angular/material/form-field';
import { MatIcon } from '@angular/material/icon';
import { MatInput } from '@angular/material/input';
import { MatPaginator, PageEvent } from '@angular/material/paginator';
import { MatProgressBar } from '@angular/material/progress-bar';
import { MatOption, MatSelect } from '@angular/material/select';
import { RouterLink } from '@angular/router';
import {
  ApiClient,
  CreditNoteListItem,
  GrnListItem,
  InvoiceListItem,
  PaymentListItem,
  listCreditNotes,
  listGrns,
  listSupplierInvoices,
  listSupplierPayments,
} from '@trishul/core-api';
import { AuthStore } from '@trishul/core-auth';
import { InventoryLookups, isoDate, n0 } from '@trishul/inventory-data-access';
import {
  PUR_CREDIT_NOTE_MANAGE,
  PUR_GRN_MANAGE,
  PUR_INVOICE_CREATE_PERMISSIONS,
  PUR_PAYMENT_MANAGE,
} from '@trishul/purchases-data-access';
import { PageHeader, StatusBadge } from '@trishul/shared-ui';
import {
  Observable,
  Subject,
  catchError,
  debounceTime,
  distinctUntilChanged,
  of,
} from 'rxjs';
import { INVOICE_STATE, rupees } from './purchases.shared';

export type PurchaseDocKind = 'grn' | 'invoice' | 'payment' | 'credit';
type Row = GrnListItem | InvoiceListItem | PaymentListItem | CreditNoteListItem;
interface Query {
  page: number;
  pageSize: number;
  search?: string | null;
  supplierId?: number | null;
  branchId?: number | null;
  fromDate?: string | null;
  toDate?: string | null;
  state?: InvoiceListItem['state'] | null;
}

const TEXT: Record<PurchaseDocKind, { title: string; subtitle: string; add: string; search: string; permissions: readonly string[] }> = {
  grn: { title: 'Goods receipts (GRN)', subtitle: 'Goods received, direct or against purchase orders',
    add: 'Receive goods', search: 'GRN no, PO no, supplier or invoice no', permissions: [PUR_GRN_MANAGE] },
  invoice: { title: 'Supplier invoices', subtitle: 'Bills from suppliers, what is outstanding and when it is due',
    add: 'Record invoice', search: 'Invoice no, supplier\'s no or supplier', permissions: PUR_INVOICE_CREATE_PERMISSIONS },
  payment: { title: 'Payments to suppliers', subtitle: 'Payments and how much of each is still unallocated',
    add: 'Record payment', search: 'Payment no, reference or supplier', permissions: [PUR_PAYMENT_MANAGE] },
  credit: { title: 'Supplier credit notes', subtitle: 'Purchase returns, damaged goods, price differences',
    add: 'Record credit note', search: 'Note no, supplier\'s no or supplier', permissions: [PUR_CREDIT_NOTE_MANAGE] },
}; // prettier-ignore

/** GRN / invoice / payment / credit note lists (the route's data.kind). */
@Component({
  selector: 'trishul-purchase-documents-page',
  imports: [
    DatePipe,
    DecimalPipe,
    RouterLink,
    MatButton,
    MatIcon,
    MatFormField,
    MatLabel,
    MatPrefix,
    MatSuffix,
    MatInput,
    MatSelect,
    MatOption,
    MatDatepicker,
    MatDatepickerInput,
    MatDatepickerToggle,
    MatPaginator,
    MatProgressBar,
    PageHeader,
    StatusBadge,
  ],
  providers: [provideNativeDateAdapter()],
  changeDetection: ChangeDetectionStrategy.OnPush,
  styleUrl: '../../../../inventory/data-access/src/lib/inventory.scss',
  template: `
    <trishul-page-header [title]="text().title" [subtitle]="text().subtitle">
      @if (canAdd()) {
        <a mat-flat-button routerLink="new"
          ><mat-icon>add</mat-icon>{{ text().add }}</a
        >
      }
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
          [placeholder]="text().search"
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
      @if (kind() === 'invoice') {
        <mat-form-field appearance="outline" subscriptSizing="dynamic">
          <mat-label>State</mat-label>
          <mat-select
            [value]="query().state ?? null"
            (valueChange)="update({ state: $event })"
          >
            <mat-option [value]="null">All</mat-option>
            <mat-option value="Unpaid">Not fully paid</mat-option>
            <mat-option value="Overdue">Overdue</mat-option>
            <mat-option value="Partially paid">Partially paid</mat-option>
            <mat-option value="Paid">Paid</mat-option>
          </mat-select>
        </mat-form-field>
      }
      <mat-form-field appearance="outline" subscriptSizing="dynamic">
        <mat-label>From</mat-label>
        <input
          matInput
          [matDatepicker]="fromPicker"
          (dateChange)="
            update({ fromDate: $event.value ? iso($event.value) : null })
          "
        />
        <mat-datepicker-toggle matSuffix [for]="fromPicker" /><mat-datepicker
          #fromPicker
        />
      </mat-form-field>
      <mat-form-field appearance="outline" subscriptSizing="dynamic">
        <mat-label>To</mat-label>
        <input
          matInput
          [matDatepicker]="toPicker"
          (dateChange)="
            update({ toDate: $event.value ? iso($event.value) : null })
          "
        />
        <mat-datepicker-toggle matSuffix [for]="toPicker" /><mat-datepicker
          #toPicker
        />
      </mat-form-field>
    </div>

    <div class="table-card">
      <div class="progress">
        @if (loading()) {
          <mat-progress-bar mode="indeterminate" />
        }
      </div>
      <div class="table-scroll">
        <table class="plain wide">
          @switch (kind()) {
            @case ('grn') {
              <thead>
                <tr>
                  <th>GRN no</th>
                  <th>Date</th>
                  <th>Supplier</th>
                  <th>Order</th>
                  <th>Received at</th>
                  <th>Their invoice</th>
                  <th class="num">Qty</th>
                  <th class="num">Value</th>
                </tr>
              </thead>
              <tbody>
                @for (g of grns(); track g.id) {
                  <tr>
                    <td>
                      <a class="name" [routerLink]="[g.id]">{{ g.grnNo }}</a>
                    </td>
                    <td class="nowrap">
                      {{ g.grnDate | date: 'dd MMM yyyy' }}
                    </td>
                    <td>{{ g.supplierName }}</td>
                    <td>{{ g.poNo ?? 'Direct' }}</td>
                    <td>
                      {{ g.branchName }}
                      <div class="muted">{{ g.locationName }}</div>
                    </td>
                    <td>{{ g.supplierInvoiceNo ?? '—' }}</td>
                    <td class="num">{{ g.totalQty | number: '1.0-3' }}</td>
                    <td class="num">{{ money(g.totalValue) }}</td>
                  </tr>
                } @empty {
                  <tr>
                    <td colspan="8" class="empty">
                      {{ loading() ? 'Loading…' : 'Nothing matches.' }}
                    </td>
                  </tr>
                }
              </tbody>
            }
            @case ('invoice') {
              <thead>
                <tr>
                  <th>Invoice</th>
                  <th>Supplier</th>
                  <th>Date</th>
                  <th>Due</th>
                  <th>Against</th>
                  <th>State</th>
                  <th class="num">Total</th>
                  <th class="num">Outstanding</th>
                </tr>
              </thead>
              <tbody>
                @for (i of invoices(); track i.id) {
                  <tr>
                    <td>
                      <a class="name" [routerLink]="[i.id]">{{
                        i.invoiceNo
                      }}</a>
                      <div class="muted">{{ i.supplierInvoiceNo }}</div>
                    </td>
                    <td>{{ i.supplierName }}</td>
                    <td class="nowrap">
                      {{ i.supplierInvoiceDate | date: 'dd MMM yyyy' }}
                    </td>
                    <td class="nowrap" [class.negative]="i.overdueDays > 0">
                      {{ i.dueDate ? (i.dueDate | date: 'dd MMM yyyy') : '—' }}
                      @if (i.overdueDays > 0) {
                        <div class="muted">{{ i.overdueDays }} days late</div>
                      }
                    </td>
                    <td>
                      {{ i.grnNo ?? i.poNo ?? (i.isDirect ? 'Direct' : '—') }}
                    </td>
                    <td>
                      <trishul-status-badge
                        [status]="i.state"
                        [severities]="invoiceState"
                      />
                    </td>
                    <td class="num">{{ money(i.total) }}</td>
                    <td class="num">{{ money(i.outstanding) }}</td>
                  </tr>
                } @empty {
                  <tr>
                    <td colspan="8" class="empty">
                      {{ loading() ? 'Loading…' : 'Nothing matches.' }}
                    </td>
                  </tr>
                }
              </tbody>
            }
            @case ('payment') {
              <thead>
                <tr>
                  <th>Payment</th>
                  <th>Date</th>
                  <th>Supplier</th>
                  <th>Mode</th>
                  <th>Reference</th>
                  <th class="num">Amount</th>
                  <th class="num">Unallocated</th>
                </tr>
              </thead>
              <tbody>
                @for (p of payments(); track p.id) {
                  <tr>
                    <td>
                      <a class="name" [routerLink]="[p.id]">{{
                        p.paymentNo
                      }}</a>
                    </td>
                    <td class="nowrap">
                      {{ p.paymentDate | date: 'dd MMM yyyy' }}
                    </td>
                    <td>
                      {{ p.supplierName }}
                      <div class="muted">{{ p.branchName }}</div>
                    </td>
                    <td>{{ p.paymentMode }}</td>
                    <td>{{ p.referenceNo ?? '—' }}</td>
                    <td class="num">{{ money(p.amount) }}</td>
                    <td class="num" [class.positive]="n0(p.unallocated) > 0">
                      {{ n0(p.unallocated) ? money(p.unallocated) : '—' }}
                    </td>
                  </tr>
                } @empty {
                  <tr>
                    <td colspan="7" class="empty">
                      {{ loading() ? 'Loading…' : 'Nothing matches.' }}
                    </td>
                  </tr>
                }
              </tbody>
            }
            @case ('credit') {
              <thead>
                <tr>
                  <th>Credit note</th>
                  <th>Date</th>
                  <th>Supplier</th>
                  <th>Type</th>
                  <th>Against invoice</th>
                  <th class="num">Amount</th>
                  <th class="num">Unallocated</th>
                </tr>
              </thead>
              <tbody>
                @for (c of credits(); track c.id) {
                  <tr>
                    <td>
                      <a class="name" [routerLink]="[c.id]">{{
                        c.debitNoteNo
                      }}</a>
                      <div class="muted">{{ c.supplierNoteNo ?? '' }}</div>
                    </td>
                    <td class="nowrap">
                      {{ c.noteDate | date: 'dd MMM yyyy' }}
                    </td>
                    <td>{{ c.supplierName }}</td>
                    <td>{{ c.noteType }}</td>
                    <td>{{ c.invoiceNo ?? '—' }}</td>
                    <td class="num">{{ money(c.total) }}</td>
                    <td class="num">
                      {{ n0(c.unallocated) ? money(c.unallocated) : '—' }}
                    </td>
                  </tr>
                } @empty {
                  <tr>
                    <td colspan="7" class="empty">
                      {{ loading() ? 'Loading…' : 'Nothing matches.' }}
                    </td>
                  </tr>
                }
              </tbody>
            }
          }
        </table>
      </div>
      <mat-paginator
        [length]="total()"
        [pageIndex]="query().page - 1"
        [pageSize]="query().pageSize"
        [pageSizeOptions]="[20, 50, 100]"
        aria-label="Pages"
        (page)="onPage($event)"
      />
    </div>
  `,
})
export class DocumentsPage {
  private readonly api = inject(ApiClient);
  private readonly auth = inject(AuthStore);
  private readonly lookups = inject(InventoryLookups);

  readonly kind = input.required<PurchaseDocKind>();
  /** ?supplierId=… from a supplier page. */
  readonly supplierId = input<string>();

  protected readonly text = computed(() => TEXT[this.kind()]);
  protected readonly canAdd = computed(() =>
    this.auth.hasAnyPermission(TEXT[this.kind()].permissions),
  );
  protected readonly suppliers = toSignal(this.lookups.suppliers(), {
    initialValue: [],
  });
  protected readonly invoiceState = INVOICE_STATE;
  protected readonly money = rupees;
  protected readonly n0 = n0;
  protected readonly iso = isoDate;
  protected readonly query = signal<Query>({ page: 1, pageSize: 20 });
  protected readonly search$ = new Subject<string>();

  private readonly rows = signal<Row[]>([]);
  protected readonly total = signal(0);
  protected readonly loading = signal(false);
  protected readonly grns = computed(() => this.rows() as GrnListItem[]);
  protected readonly invoices = computed(
    () => this.rows() as InvoiceListItem[],
  );
  protected readonly payments = computed(
    () => this.rows() as PaymentListItem[],
  );
  protected readonly credits = computed(
    () => this.rows() as CreditNoteListItem[],
  );

  constructor() {
    this.search$
      .pipe(debounceTime(350), distinctUntilChanged(), takeUntilDestroyed())
      .subscribe((search) => this.update({ search: search.trim() || null }));
    effect(() => {
      const supplier = Number(this.supplierId());
      untracked(() => this.update({ supplierId: supplier || null }));
    });
  }

  protected update(change: Partial<Query>): void {
    this.query.update((q) => ({ ...q, ...change, page: change.page ?? 1 }));
    this.load();
  }

  protected onPage(event: PageEvent): void {
    this.update({ page: event.pageIndex + 1, pageSize: event.pageSize });
  }

  private load(): void {
    const q = this.query();
    const base = {
      page: q.page,
      pageSize: q.pageSize,
      search: q.search ?? null,
      supplierId: q.supplierId ?? null,
      fromDate: q.fromDate ?? null,
      toDate: q.toDate ?? null,
    };
    const requests: Record<
      PurchaseDocKind,
      () => Observable<{ items: Row[]; total: number }>
    > = {
      grn: () => this.api.call(listGrns, base),
      invoice: () =>
        this.api.call(listSupplierInvoices, {
          ...base,
          state: q.state ?? null,
        }),
      payment: () => this.api.call(listSupplierPayments, base),
      credit: () => this.api.call(listCreditNotes, base),
    };
    this.loading.set(true);
    requests[this.kind()]()
      .pipe(catchError(() => of({ items: [] as Row[], total: 0 })))
      .subscribe((page) => {
        this.rows.set(page.items);
        this.total.set(page.total);
        this.loading.set(false);
      });
  }
}
