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
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { FormControl, ReactiveFormsModule } from '@angular/forms';
import { MatButton } from '@angular/material/button';
import { MatCheckbox } from '@angular/material/checkbox';
import { MatDialog } from '@angular/material/dialog';
import { MatIcon } from '@angular/material/icon';
import { MatPaginator, PageEvent } from '@angular/material/paginator';
import { MatProgressBar } from '@angular/material/progress-bar';
import { MatRadioButton, MatRadioGroup } from '@angular/material/radio';
import { RouterLink } from '@angular/router';
import {
  ApiClient,
  CustomerAllocationOut,
  CustomerOpenItems,
  ListCustomerAllocations$Params,
  OpenReceipt,
  createCustomerAllocations,
  getCustomerAccount,
  getCustomerOpenItems,
  getReceipt,
  listCustomerAllocations,
  reverseCustomerAllocation,
} from '@trishul/core-api';
import { AuthStore } from '@trishul/core-auth';
import {
  num,
  openFieldsDialog,
  pagedList,
} from '@trishul/inventory-data-access';
import {
  CustomerPicker,
  PickedCustomer,
  SAL_ALLOCATION_MANAGE,
  SAL_ALLOCATION_REVERSE,
} from '@trishul/sales-data-access';
import { PageHeader } from '@trishul/shared-ui';
import { EMPTY, catchError, filter, finalize, switchMap } from 'rxjs';
import { rupees } from './sales.shared';

/** Set unallocated receipts (and advances) against a customer's invoices; the history with reversals. */
@Component({
  selector: 'trishul-sales-allocations-page',
  imports: [
    DatePipe,
    ReactiveFormsModule,
    RouterLink,
    MatButton,
    MatIcon,
    MatCheckbox,
    MatRadioGroup,
    MatRadioButton,
    MatPaginator,
    MatProgressBar,
    CustomerPicker,
    PageHeader,
  ],
  changeDetection: ChangeDetectionStrategy.OnPush,
  styleUrl: '../../../../inventory/data-access/src/lib/inventory.scss',
  styles: `
    input.cell {
      width: 8rem;
      padding: 0.3rem 0.4rem;
      border: 1px solid var(--mat-sys-outline-variant);
      border-radius: 4px;
      background: transparent;
      color: inherit;
      font: inherit;
      text-align: right;
    }
    .panes {
      display: grid;
      grid-template-columns: minmax(0, 2fr) minmax(0, 3fr);
      gap: 1rem;
    }
    @media (max-width: 900px) {
      .panes {
        grid-template-columns: 1fr;
      }
    }
  `,
  template: `
    <trishul-page-header
      title="Customer allocations"
      subtitle="Which invoices each receipt settles; reversals stay in the history"
    />
    <div class="filters">
      <trishul-customer-picker
        [formControl]="customer"
        style="flex: 1 1 22rem; max-width: 28rem"
      />
      <mat-checkbox
        [checked]="includeReversed()"
        (change)="toggleReversed($event.checked)"
        >Show reversed</mat-checkbox
      >
    </div>

    @if (items(); as open) {
      @if (canAllocate) {
        <div class="panes">
          <section class="card">
            <h2>Unallocated receipts</h2>
            <mat-radio-group
              [value]="chosen()"
              (change)="chosen.set($event.value)"
            >
              @for (r of open.receipts; track r.id) {
                <div>
                  <mat-radio-button [value]="r.id">
                    {{ r.receiptNo }} · {{ r.receiptDate | date: 'dd MMM' }} ·
                    {{ money(r.unallocated) }} left
                    <span class="muted"
                      >{{ r.receiptType
                      }}{{ r.orderNo ? ' ' + r.orderNo : '' }}</span
                    >
                  </mat-radio-button>
                </div>
              } @empty {
                <p class="muted">
                  No receipt of this customer has an amount left.
                </p>
              }
            </mat-radio-group>
          </section>
          <section class="card">
            <h2>
              Outstanding invoices
              <button
                mat-button
                type="button"
                (click)="autoAllocate()"
                [disabled]="!selected()"
              >
                <mat-icon>auto_fix_high</mat-icon>Oldest first
              </button>
            </h2>
            <table class="plain">
              <thead>
                <tr>
                  <th>Invoice</th>
                  <th>Due</th>
                  <th class="num">Outstanding</th>
                  <th class="num">Allocate</th>
                </tr>
              </thead>
              <tbody>
                @for (i of open.invoices; track i.id) {
                  <tr>
                    <td>
                      <a
                        class="name"
                        [routerLink]="['/sales/invoices', i.id]"
                        >{{ i.invoiceNo }}</a
                      >
                      <div class="muted">
                        {{ i.invoiceDate | date: 'dd MMM yyyy' }}
                      </div>
                    </td>
                    <td class="nowrap" [class.negative]="i.overdueDays > 0">
                      {{ i.dueDate ? (i.dueDate | date: 'dd MMM yyyy') : '—' }}
                    </td>
                    <td class="num">{{ money(i.outstanding) }}</td>
                    <td class="num">
                      <input
                        class="cell"
                        type="number"
                        min="0"
                        [value]="amounts()[i.id] || ''"
                        (input)="
                          setAmount(
                            i.id,
                            i.outstanding,
                            $any($event.target).value
                          )
                        "
                        [attr.aria-label]="'Allocate to ' + i.invoiceNo"
                      />
                    </td>
                  </tr>
                } @empty {
                  <tr>
                    <td colspan="4" class="empty">No outstanding invoices.</td>
                  </tr>
                }
              </tbody>
            </table>
            <div class="form-actions">
              <span
                class="summary"
                [class.negative]="allocating() > n(selected()?.unallocated)"
              >
                Allocating {{ money(allocating()) }} of
                {{ money(selected()?.unallocated ?? 0) }}
              </span>
              <button
                mat-flat-button
                type="button"
                (click)="save()"
                [disabled]="
                  saving() ||
                  !selected() ||
                  !allocating() ||
                  allocating() > n(selected()?.unallocated)
                "
              >
                Allocate
              </button>
            </div>
          </section>
        </div>
      }
    }

    <div class="table-card" style="margin-top: 1rem">
      <div class="progress">
        @if (history.loading()) {
          <mat-progress-bar mode="indeterminate" />
        }
      </div>
      <div class="table-scroll">
        <table class="plain wide">
          <thead>
            <tr>
              <th>On</th>
              <th>Customer</th>
              <th>Invoice</th>
              <th>Receipt</th>
              <th class="num">Amount</th>
              <th>By</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            @for (a of history.items(); track a.id) {
              <tr [class.muted]="!a.isActive">
                <td class="nowrap">
                  {{ a.allocatedOn | date: 'dd MMM yyyy' }}
                </td>
                <td>{{ a.customerName }}</td>
                <td>
                  <a
                    class="name"
                    [routerLink]="['/sales/invoices', a.salesInvoiceId]"
                    >{{ a.invoiceNo }}</a
                  >
                </td>
                <td>
                  @if (a.receiptId) {
                    <a
                      class="name"
                      [routerLink]="['/sales/receipts', a.receiptId]"
                      >{{ a.receiptNo }}</a
                    >
                    <div class="muted">
                      {{ a.receiptType
                      }}{{
                        a.receiptReference ? ' · ' + a.receiptReference : ''
                      }}
                    </div>
                  }
                </td>
                <td class="num">{{ money(a.amount) }}</td>
                <td>{{ a.allocatedBy ?? '—' }}</td>
                <td>
                  @if (a.isActive && canReverse) {
                    <button mat-button (click)="reverse(a)">Reverse</button>
                  } @else if (!a.isActive) {
                    <span
                      >Reversed by {{ a.reversedBy }}:
                      {{ a.reversalReason }}</span
                    >
                  }
                </td>
              </tr>
            } @empty {
              <tr>
                <td colspan="7" class="empty">
                  {{ history.loading() ? 'Loading…' : 'No allocations yet.' }}
                </td>
              </tr>
            }
          </tbody>
        </table>
      </div>
      <mat-paginator
        [length]="history.total()"
        [pageIndex]="(query().page ?? 1) - 1"
        [pageSize]="query().pageSize"
        [pageSizeOptions]="[20, 50, 100]"
        aria-label="Pages"
        (page)="onPage($event)"
      />
    </div>
  `,
})
export class SalesAllocationsPage {
  private readonly api = inject(ApiClient);
  private readonly dialog = inject(MatDialog);
  private readonly auth = inject(AuthStore);
  protected readonly canAllocate = this.auth.hasPermission(
    SAL_ALLOCATION_MANAGE,
  );
  protected readonly canReverse = this.auth.hasPermission(
    SAL_ALLOCATION_REVERSE,
  );

  /** ?receiptId=… from a receipt page. */
  readonly receiptId = input<string>();

  protected readonly money = (v: number | string | null | undefined) =>
    rupees(v);
  protected readonly n = (v: string | number | null | undefined) => num(v) ?? 0;
  protected readonly customer = new FormControl<PickedCustomer | null>(null);
  protected readonly items = signal<CustomerOpenItems | null>(null);
  /** The receipt being allocated. */
  protected readonly chosen = signal<number | null>(null);
  protected readonly amounts = signal<Record<number, number>>({});
  protected readonly saving = signal(false);
  protected readonly includeReversed = signal(true);
  protected readonly selected = computed<OpenReceipt | null>(
    () => this.items()?.receipts.find((r) => r.id === this.chosen()) ?? null,
  );
  protected readonly allocating = computed(() =>
    Object.values(this.amounts()).reduce((s, v) => s + v, 0),
  );
  protected readonly query = signal<ListCustomerAllocations$Params>({
    page: 1,
    pageSize: 20,
  });
  protected readonly history = pagedList(this.query, (q) =>
    this.api.call(listCustomerAllocations, q),
  );

  constructor() {
    this.customer.valueChanges.pipe(takeUntilDestroyed()).subscribe((c) => {
      this.query.update((q) => ({ ...q, customerId: c?.id ?? null, page: 1 }));
      this.loadOpen(c?.id ?? null);
    });
    effect(() => {
      const receipt = Number(this.receiptId());
      if (receipt)
        untracked(() =>
          this.api
            .call(getReceipt, { receiptId: receipt })
            .pipe(
              switchMap((r) => {
                this.chosen.set(r.id);
                return this.api.call(getCustomerAccount, {
                  customerId: r.customerId,
                });
              }),
              catchError(() => EMPTY),
            )
            .subscribe((c) => this.customer.setValue(c)),
        );
    });
  }

  private loadOpen(customerId: number | null): void {
    this.items.set(null);
    this.amounts.set({});
    if (!customerId) return;
    this.api
      .call(getCustomerOpenItems, { customerId })
      .pipe(catchError(() => EMPTY))
      .subscribe((items) => {
        this.items.set(items);
        if (!items.receipts.some((r) => r.id === this.chosen()))
          this.chosen.set(items.receipts[0]?.id ?? null);
      });
  }

  protected toggleReversed(include: boolean): void {
    this.includeReversed.set(include);
    this.query.update((q) => ({ ...q, includeReversed: include, page: 1 }));
  }

  protected setAmount(
    invoiceId: number,
    outstanding: string,
    value: string,
  ): void {
    const amount = Math.min(
      Math.max(Number(value) || 0, 0),
      num(outstanding) ?? 0,
    );
    this.amounts.update((a) => ({ ...a, [invoiceId]: amount }));
  }

  protected autoAllocate(): void {
    let left = num(this.selected()?.unallocated) ?? 0;
    const next: Record<number, number> = {};
    for (const invoice of this.items()?.invoices ?? []) {
      if (left <= 0) break;
      const amount = Math.min(left, num(invoice.outstanding) ?? 0);
      next[invoice.id] = Math.round(amount * 100) / 100;
      left -= amount;
    }
    this.amounts.set(next);
  }

  protected save(): void {
    const receipt = this.selected();
    if (!receipt || this.saving()) return;
    const allocations = Object.entries(this.amounts())
      .filter(([, amount]) => amount > 0)
      .map(([id, amount]) => ({ salesInvoiceId: Number(id), amount }));
    if (!allocations.length) return;
    this.saving.set(true);
    this.api
      .call(createCustomerAllocations, {
        body: { receiptId: receipt.id, allocations },
      })
      .pipe(
        finalize(() => this.saving.set(false)),
        catchError(() => EMPTY),
      )
      .subscribe(() => {
        this.loadOpen(this.customer.value?.id ?? null);
        this.history.reload();
      });
  }

  protected reverse(a: CustomerAllocationOut): void {
    openFieldsDialog<CustomerAllocationOut>(this.dialog, {
      title: `Reverse ${this.money(a.amount)} on ${a.invoiceNo}`,
      submitText: 'Reverse',
      fields: [
        {
          key: 'reason',
          label: 'Why',
          type: 'textarea',
          required: true,
          maxLength: 300,
        },
      ],
      save: (v) =>
        this.api.call(reverseCustomerAllocation, {
          allocationId: a.id,
          body: { reason: v['reason'] as string },
        }),
    })
      .pipe(filter((x): x is CustomerAllocationOut => !!x))
      .subscribe(() => {
        this.history.reload();
        this.loadOpen(this.customer.value?.id ?? null);
      });
  }

  protected onPage(event: PageEvent): void {
    this.query.update((q) => ({
      ...q,
      page: event.pageIndex + 1,
      pageSize: event.pageSize,
    }));
  }
}
