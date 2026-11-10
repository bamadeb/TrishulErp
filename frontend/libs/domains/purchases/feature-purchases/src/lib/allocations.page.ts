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
import { MatRadioButton, MatRadioGroup } from '@angular/material/radio';
import { MatOption, MatSelect } from '@angular/material/select';
import { RouterLink } from '@angular/router';
import {
  AllocationOut,
  ApiClient,
  ListAllocations$Params,
  OpenCredit,
  SupplierOpenItems,
  createAllocations,
  getSupplierOpenItems,
  listAllocations,
  reverseAllocation,
} from '@trishul/core-api';
import { AuthStore } from '@trishul/core-auth';
import {
  InventoryLookups,
  num,
  openFieldsDialog,
  pagedList,
} from '@trishul/inventory-data-access';
import {
  PUR_ALLOCATION_MANAGE,
  PUR_ALLOCATION_REVERSE,
} from '@trishul/purchases-data-access';
import { PageHeader } from '@trishul/shared-ui';
import {
  EMPTY,
  Subject,
  catchError,
  debounceTime,
  distinctUntilChanged,
  filter,
  finalize,
} from 'rxjs';
import { rupees } from './purchases.shared';

/** Set payments and credit notes against invoices, and the allocation inquiry (with reversals). */
@Component({
  selector: 'trishul-allocations-page',
  imports: [
    DatePipe,
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
    MatRadioGroup,
    MatRadioButton,
    MatPaginator,
    MatProgressBar,
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
      title="Supplier allocations"
      subtitle="Which invoices each payment and credit note settles; reversals stay in the history"
    />
    <div class="filters">
      <mat-form-field
        appearance="outline"
        subscriptSizing="dynamic"
        style="max-width: 24rem"
      >
        <mat-label>Supplier</mat-label>
        <mat-select [value]="supplier()" (valueChange)="chooseSupplier($event)">
          <mat-option [value]="null">All suppliers (history only)</mat-option>
          @for (s of suppliers(); track s.id) {
            <mat-option [value]="s.id">{{ s.name }}</mat-option>
          }
        </mat-select>
      </mat-form-field>
    </div>

    @if (canAllocate && open(); as items) {
      <div class="panes">
        <section class="card">
          <h2>1 · Payment or credit note</h2>
          <mat-radio-group
            [value]="source()"
            (change)="source.set($event.value)"
            aria-label="What to allocate"
          >
            <table class="plain">
              <thead>
                <tr>
                  <th></th>
                  <th>Document</th>
                  <th>Date</th>
                  <th class="num">Unallocated</th>
                </tr>
              </thead>
              <tbody>
                @for (c of items.credits; track c.kind + c.id) {
                  <tr>
                    <td><mat-radio-button [value]="c" /></td>
                    <td>
                      {{ c.kind }} {{ c.documentNo }}
                      <div class="muted">{{ c.reference ?? '' }}</div>
                    </td>
                    <td class="nowrap">{{ c.date | date: 'dd MMM yyyy' }}</td>
                    <td class="num">{{ money(c.unallocated) }}</td>
                  </tr>
                } @empty {
                  <tr>
                    <td colspan="4" class="empty">
                      No unallocated payments or credit notes.
                    </td>
                  </tr>
                }
              </tbody>
            </table>
          </mat-radio-group>
        </section>
        <section class="card">
          <h2>
            2 · Invoices to settle
            <button
              mat-button
              type="button"
              (click)="autoFill()"
              [disabled]="!source()"
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
              @for (i of items.invoices; track i.id) {
                <tr>
                  <td>
                    <a
                      class="name"
                      [routerLink]="['/purchases/invoices', i.id]"
                      >{{ i.invoiceNo }}</a
                    >
                    · {{ i.supplierInvoiceNo }}
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
                          num(i.outstanding) ?? 0,
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
            <span class="summary" [class.negative]="over()">
              Allocating {{ money(totalAmount())
              }}{{ source() ? ' of ' + money(source()!.unallocated) : '' }}
            </span>
            <button
              mat-flat-button
              (click)="allocate()"
              [disabled]="!source() || !totalAmount() || over() || saving()"
            >
              Allocate
            </button>
          </div>
        </section>
      </div>
    }

    <section class="card">
      <h2>Allocation history</h2>
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
            placeholder="Invoice, payment, reference or credit note no"
            aria-label="Search"
            (input)="search$.next($any($event.target).value)"
          />
        </mat-form-field>
        <mat-checkbox
          [checked]="!!query().includeReversed"
          (change)="updateQuery({ includeReversed: $event.checked })"
        >
          Show reversed
        </mat-checkbox>
      </div>
      <div class="progress">
        @if (history.loading()) {
          <mat-progress-bar mode="indeterminate" />
        }
      </div>
      <div class="table-scroll">
        <table class="plain wide">
          <thead>
            <tr>
              <th>Supplier</th>
              <th>Invoice</th>
              <th>Payment / credit note</th>
              <th class="num">Invoice total</th>
              <th class="num">Allocated</th>
              <th class="num">Invoice outstanding</th>
              <th>On</th>
              <th>By</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            @for (a of history.items(); track a.id) {
              <tr [class.muted]="!a.isActive">
                <td>{{ a.supplierName }}</td>
                <td>
                  <a
                    class="name"
                    [routerLink]="['/purchases/invoices', a.supplierInvoiceId]"
                    >{{ a.invoiceNo }}</a
                  >
                  <div class="muted">{{ a.supplierInvoiceNo }}</div>
                </td>
                <td>
                  @if (a.supplierPaymentId) {
                    <a
                      class="name"
                      [routerLink]="[
                        '/purchases/payments',
                        a.supplierPaymentId,
                      ]"
                      >{{ a.paymentNo }}</a
                    >
                    <div class="muted">{{ a.paymentReference ?? '' }}</div>
                  } @else {
                    <a
                      class="name"
                      [routerLink]="['/purchases/credit-notes', a.debitNoteId]"
                      >{{ a.creditNoteNo }}</a
                    >
                  }
                </td>
                <td class="num">{{ money(a.invoiceTotal) }}</td>
                <td class="num">{{ money(a.amount) }}</td>
                <td class="num">{{ money(a.invoiceOutstanding) }}</td>
                <td class="nowrap">
                  {{ a.allocatedOn | date: 'dd MMM yyyy' }}
                </td>
                <td>
                  {{ a.allocatedBy ?? '—' }}
                  @if (!a.isActive) {
                    <div>
                      Reversed {{ a.reversedAt | date: 'dd MMM' }} by
                      {{ a.reversedBy }}: {{ a.reversalReason }}
                    </div>
                  }
                </td>
                <td class="actions">
                  @if (a.isActive && canReverse) {
                    <button mat-button (click)="reverse(a)">Reverse</button>
                  }
                </td>
              </tr>
            } @empty {
              <tr>
                <td colspan="9" class="empty">
                  {{ history.loading() ? 'Loading…' : 'No allocations.' }}
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
    </section>
  `,
})
export class AllocationsPage {
  private readonly api = inject(ApiClient);
  private readonly dialog = inject(MatDialog);
  private readonly lookups = inject(InventoryLookups);
  private readonly auth = inject(AuthStore);

  readonly supplierId = input<string>();

  protected readonly canAllocate = this.auth.hasPermission(
    PUR_ALLOCATION_MANAGE,
  );
  protected readonly canReverse = this.auth.hasPermission(
    PUR_ALLOCATION_REVERSE,
  );
  protected readonly money = (v: number | string) => rupees(v);
  protected readonly num = num;
  protected readonly suppliers = toSignal(this.lookups.suppliers(), {
    initialValue: [],
  });
  protected readonly supplier = signal<number | null>(null);
  protected readonly open = signal<SupplierOpenItems | null>(null);
  protected readonly source = signal<OpenCredit | null>(null);
  protected readonly amounts = signal<Record<number, number>>({});
  protected readonly totalAmount = computed(() =>
    Object.values(this.amounts()).reduce((s, v) => s + v, 0),
  );
  protected readonly over = computed(
    () => this.totalAmount() > (num(this.source()?.unallocated) ?? 0) + 0.001,
  );
  protected readonly saving = signal(false);

  protected readonly query = signal<ListAllocations$Params>({
    page: 1,
    pageSize: 20,
    includeReversed: true,
  });
  protected readonly history = pagedList(this.query, (q) =>
    this.api.call(listAllocations, q),
  );
  protected readonly search$ = new Subject<string>();

  constructor() {
    this.search$
      .pipe(debounceTime(350), distinctUntilChanged(), takeUntilDestroyed())
      .subscribe((search) =>
        this.updateQuery({ search: search.trim() || null }),
      );
    effect(() => {
      const id = Number(this.supplierId()) || null;
      untracked(() => this.chooseSupplier(id));
    });
  }

  protected chooseSupplier(supplierId: number | null): void {
    this.supplier.set(supplierId);
    this.source.set(null);
    this.amounts.set({});
    this.updateQuery({ supplierId });
    this.loadOpen();
  }

  private loadOpen(): void {
    const supplierId = this.supplier();
    this.open.set(null);
    if (!supplierId) return;
    this.api
      .call(getSupplierOpenItems, { supplierId })
      .pipe(catchError(() => EMPTY))
      .subscribe((items) => this.open.set(items));
  }

  protected updateQuery(change: Partial<ListAllocations$Params>): void {
    this.query.update((q) => ({ ...q, ...change, page: change.page ?? 1 }));
  }

  protected onPage(event: PageEvent): void {
    this.updateQuery({ page: event.pageIndex + 1, pageSize: event.pageSize });
  }

  protected setAmount(
    invoiceId: number,
    outstanding: number,
    value: string,
  ): void {
    const amount = Math.min(Math.max(Number(value) || 0, 0), outstanding);
    this.amounts.update((a) => ({ ...a, [invoiceId]: amount }));
  }

  protected autoFill(): void {
    let left = num(this.source()?.unallocated) ?? 0;
    const next: Record<number, number> = {};
    for (const invoice of this.open()?.invoices ?? []) {
      if (left <= 0) break;
      const amount = Math.min(left, num(invoice.outstanding) ?? 0);
      next[invoice.id] = Math.round(amount * 100) / 100;
      left -= amount;
    }
    this.amounts.set(next);
  }

  protected allocate(): void {
    const source = this.source();
    if (!source) return;
    const allocations = Object.entries(this.amounts())
      .filter(([, amount]) => amount > 0)
      .map(([id, amount]) => ({ supplierInvoiceId: Number(id), amount }));
    this.saving.set(true);
    this.api
      .call(createAllocations, {
        body: {
          supplierPaymentId: source.kind === 'Payment' ? source.id : null,
          debitNoteId: source.kind === 'Credit note' ? source.id : null,
          allocations,
        },
      })
      .pipe(
        finalize(() => this.saving.set(false)),
        catchError(() => EMPTY),
      )
      .subscribe(() => {
        this.source.set(null);
        this.amounts.set({});
        this.loadOpen();
        this.history.reload();
      });
  }

  protected reverse(allocation: AllocationOut): void {
    openFieldsDialog(this.dialog, {
      title: `Reverse ${rupees(allocation.amount)} on ${allocation.invoiceNo}`,
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
        this.api.call(reverseAllocation, {
          allocationId: allocation.id,
          body: { reason: v['reason'] as string },
        }),
    })
      .pipe(filter((done) => !!done))
      .subscribe(() => {
        this.loadOpen();
        this.history.reload();
      });
  }
}
