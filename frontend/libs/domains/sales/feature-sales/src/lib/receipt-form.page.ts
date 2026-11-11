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
import { toSignal } from '@angular/core/rxjs-interop';
import {
  FormControl,
  FormGroup,
  ReactiveFormsModule,
  Validators,
} from '@angular/forms';
import { MatButton } from '@angular/material/button';
import { provideNativeDateAdapter } from '@angular/material/core';
import {
  MatDatepicker,
  MatDatepickerInput,
  MatDatepickerToggle,
} from '@angular/material/datepicker';
import {
  MatError,
  MatFormField,
  MatHint,
  MatLabel,
  MatSuffix,
} from '@angular/material/form-field';
import { MatIcon } from '@angular/material/icon';
import { MatInput } from '@angular/material/input';
import { MatOption, MatSelect } from '@angular/material/select';
import { Router, RouterLink } from '@angular/router';
import {
  ApiClient,
  OpenSalesInvoice,
  OrderListItem,
  createReceipt,
  getCustomerAccount,
  getCustomerOpenItems,
  listSalesOrders,
} from '@trishul/core-api';
import { AuthStore } from '@trishul/core-auth';
import { isoDate, num } from '@trishul/inventory-data-access';
import {
  CustomerPicker,
  NO_SALES_OPTIONS,
  PickedCustomer,
  SalesLookups,
} from '@trishul/sales-data-access';
import { PageHeader } from '@trishul/shared-ui';
import { EMPTY, catchError, finalize, map, of } from 'rxjs';
import { PAYMENT_MODES, PaymentMode, rupees } from './sales.shared';

type ReceiptType = 'Against invoice' | 'Advance' | 'Order advance';
const OPEN_ORDER = [
  'Pending approval',
  'Approved',
  'Part delivered',
  'Delivered',
  'Part invoiced',
];

/** Money from a customer: against invoices, on account, or an advance for a sales order (prepaid). */
@Component({
  selector: 'trishul-receipt-form-page',
  imports: [
    DatePipe,
    ReactiveFormsModule,
    RouterLink,
    MatFormField,
    MatLabel,
    MatHint,
    MatError,
    MatSuffix,
    MatInput,
    MatSelect,
    MatOption,
    MatDatepicker,
    MatDatepickerInput,
    MatDatepickerToggle,
    MatButton,
    MatIcon,
    CustomerPicker,
    PageHeader,
  ],
  providers: [provideNativeDateAdapter()],
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
  `,
  template: `
    <trishul-page-header
      title="Record customer receipt"
      subtitle="Set it against invoices, keep it on account, or take it as an advance for an order"
    />
    <form [formGroup]="form" (ngSubmit)="save()">
      <section class="card">
        <h2>Receipt</h2>
        <div class="form-grid">
          <trishul-customer-picker formControlName="customer" />
          <mat-form-field appearance="outline">
            <mat-label>Type</mat-label>
            <mat-select formControlName="receiptType">
              <mat-option value="Against invoice">Against invoices</mat-option>
              <mat-option value="Advance">On account (advance)</mat-option>
              <mat-option value="Order advance"
                >Advance for a sales order</mat-option
              >
            </mat-select>
          </mat-form-field>
          @if (form.controls.receiptType.value === 'Order advance') {
            <mat-form-field appearance="outline">
              <mat-label>Sales order</mat-label>
              <mat-select formControlName="salesOrderId">
                @for (o of orders(); track o.id) {
                  <mat-option [value]="o.id"
                    >{{ o.orderNo }} · {{ money(o.total)
                    }}{{ o.isPrepaid ? ' · prepaid' : '' }}</mat-option
                  >
                }
              </mat-select>
              <mat-error>Choose the order.</mat-error>
            </mat-form-field>
          }
          <mat-form-field appearance="outline">
            <mat-label>Received at branch</mat-label>
            <mat-select formControlName="branchId">
              @for (b of options().branches; track b.id) {
                <mat-option [value]="b.id">{{ b.name }}</mat-option>
              }
            </mat-select>
            <mat-error>Choose the branch.</mat-error>
          </mat-form-field>
          <mat-form-field appearance="outline">
            <mat-label>Receipt date</mat-label>
            <input
              matInput
              [matDatepicker]="datePicker"
              formControlName="receiptDate"
              [max]="today"
            />
            <mat-datepicker-toggle
              matSuffix
              [for]="datePicker"
            /><mat-datepicker #datePicker />
          </mat-form-field>
          <mat-form-field appearance="outline">
            <mat-label>Mode</mat-label>
            <mat-select formControlName="paymentMode">
              @for (m of modes; track m.value) {
                <mat-option [value]="m.value">{{ m.label }}</mat-option>
              }
            </mat-select>
          </mat-form-field>
          <mat-form-field appearance="outline">
            <mat-label>Amount (₹)</mat-label>
            <input matInput type="number" min="0" formControlName="amount" />
            <mat-error>More than zero.</mat-error>
          </mat-form-field>
          <mat-form-field appearance="outline">
            <mat-label>{{
              form.controls.paymentMode.value === 'Cheque'
                ? 'Cheque no'
                : 'UTR / UPI reference'
            }}</mat-label>
            <input matInput formControlName="referenceNo" />
            @if (form.controls.paymentMode.value !== 'Cash') {
              <mat-hint>Required</mat-hint>
            }
          </mat-form-field>
          <mat-form-field appearance="outline">
            <mat-label>Bank</mat-label>
            <input matInput formControlName="bankName" />
          </mat-form-field>
          @if (form.controls.paymentMode.value === 'Cheque') {
            <mat-form-field appearance="outline">
              <mat-label>Cheque date</mat-label>
              <input
                matInput
                [matDatepicker]="chequePicker"
                formControlName="chequeDate"
              />
              <mat-datepicker-toggle
                matSuffix
                [for]="chequePicker"
              /><mat-datepicker #chequePicker />
            </mat-form-field>
          }
          <mat-form-field appearance="outline" class="wide">
            <mat-label>Remarks</mat-label>
            <input matInput formControlName="remarks" />
          </mat-form-field>
        </div>
      </section>

      @if (form.controls.receiptType.value !== 'Order advance') {
        <section class="card">
          <h2>
            Set against invoices
            <button
              mat-button
              type="button"
              (click)="autoAllocate()"
              [disabled]="!invoices().length"
            >
              <mat-icon>auto_fix_high</mat-icon>Oldest first
            </button>
          </h2>
          <table class="plain">
            <thead>
              <tr>
                <th>Invoice</th>
                <th>Date</th>
                <th>Due</th>
                <th class="num">Outstanding</th>
                <th class="num">Receive now</th>
              </tr>
            </thead>
            <tbody>
              @for (i of invoices(); track i.id) {
                <tr>
                  <td>{{ i.invoiceNo }}</td>
                  <td class="nowrap">
                    {{ i.invoiceDate | date: 'dd MMM yyyy' }}
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
                      [max]="i.outstanding"
                      [value]="allocation(i.id) || ''"
                      (input)="setAllocation(i, $any($event.target).value)"
                      [attr.aria-label]="'Receive now on ' + i.invoiceNo"
                    />
                  </td>
                </tr>
              } @empty {
                <tr>
                  <td colspan="5" class="empty">
                    {{
                      form.controls.customer.value
                        ? 'No outstanding invoices: the receipt stays on account.'
                        : 'Choose the customer.'
                    }}
                  </td>
                </tr>
              }
            </tbody>
          </table>
        </section>
      }

      <div class="form-actions">
        <span
          class="summary"
          [class.negative]="allocated() > (form.controls.amount.value ?? 0)"
        >
          Allocated {{ money(allocated()) }} · unallocated
          {{
            money(Math.max((form.controls.amount.value ?? 0) - allocated(), 0))
          }}
        </span>
        <a mat-button routerLink="/sales/receipts">Cancel</a>
        <button mat-flat-button type="submit" [disabled]="saving()">
          Record receipt
        </button>
      </div>
    </form>
  `,
})
export class ReceiptFormPage {
  private readonly api = inject(ApiClient);
  private readonly router = inject(Router);
  private readonly auth = inject(AuthStore);

  /** ?customerId=…&orderId=… from a customer or order page. */
  readonly customerId = input<string>();
  readonly orderId = input<string>();

  protected readonly Math = Math;
  protected readonly today = new Date();
  protected readonly modes = PAYMENT_MODES;
  protected readonly money = (v: number | string) => rupees(v);
  protected readonly options = toSignal(inject(SalesLookups).options(), {
    initialValue: NO_SALES_OPTIONS,
  });
  protected readonly invoices = signal<OpenSalesInvoice[]>([]);
  protected readonly orders = signal<OrderListItem[]>([]);
  private readonly allocations = signal<Record<number, number>>({});
  protected readonly allocated = computed(() =>
    this.form.controls.receiptType.value === 'Order advance'
      ? 0
      : Object.values(this.allocations()).reduce((s, v) => s + v, 0),
  );
  protected readonly saving = signal(false);

  protected readonly form = new FormGroup({
    customer: new FormControl<PickedCustomer | null>(null, Validators.required),
    receiptType: new FormControl<ReceiptType>('Against invoice', {
      nonNullable: true,
    }),
    salesOrderId: new FormControl<number | null>(null),
    branchId: new FormControl<number | null>(
      this.auth.branchId(),
      Validators.required,
    ),
    receiptDate: new FormControl<Date | null>(new Date(), Validators.required),
    paymentMode: new FormControl<PaymentMode>('NEFT', { nonNullable: true }),
    amount: new FormControl<number | null>(null, [
      Validators.required,
      Validators.min(0.01),
    ]),
    referenceNo: new FormControl<string | null>(null, Validators.maxLength(40)),
    bankName: new FormControl<string | null>(null, Validators.maxLength(100)),
    chequeDate: new FormControl<Date | null>(null),
    remarks: new FormControl<string | null>(null, Validators.maxLength(300)),
  });

  constructor() {
    this.form.controls.customer.valueChanges.subscribe((c) =>
      this.loadCustomer(c?.id ?? null),
    );
    effect(() => {
      const customer = Number(this.customerId());
      const order = Number(this.orderId());
      untracked(() => {
        if (order) {
          this.form.patchValue({ receiptType: 'Order advance' });
        }
        if (customer)
          this.api
            .call(getCustomerAccount, { customerId: customer })
            .pipe(catchError(() => EMPTY))
            .subscribe((c) => this.form.controls.customer.setValue(c));
      });
    });
  }

  private loadCustomer(customerId: number | null): void {
    this.allocations.set({});
    this.invoices.set([]);
    this.orders.set([]);
    if (!customerId) return;
    this.api
      .call(getCustomerOpenItems, { customerId })
      .pipe(catchError(() => EMPTY))
      .subscribe((items) => this.invoices.set(items.invoices));
    this.api
      .call(listSalesOrders, { customerId, pageSize: 100 })
      .pipe(
        map((page) => page.items.filter((o) => OPEN_ORDER.includes(o.status))),
        catchError(() => of([] as OrderListItem[])),
      )
      .subscribe((orders) => {
        this.orders.set(orders);
        const wanted = Number(this.orderId());
        if (wanted && orders.some((o) => o.id === wanted))
          this.form.controls.salesOrderId.setValue(wanted);
      });
  }

  protected allocation(invoiceId: number): number {
    return this.allocations()[invoiceId] ?? 0;
  }

  protected setAllocation(invoice: OpenSalesInvoice, value: string): void {
    const amount = Math.min(
      Math.max(Number(value) || 0, 0),
      num(invoice.outstanding) ?? 0,
    );
    this.allocations.update((a) => ({ ...a, [invoice.id]: amount }));
  }

  protected autoAllocate(): void {
    let left = this.form.controls.amount.value ?? 0;
    const next: Record<number, number> = {};
    for (const invoice of this.invoices()) {
      if (left <= 0) break;
      const amount = Math.min(left, num(invoice.outstanding) ?? 0);
      next[invoice.id] = Math.round(amount * 100) / 100;
      left -= amount;
    }
    this.allocations.set(next);
  }

  protected save(): void {
    this.form.markAllAsTouched();
    const v = this.form.getRawValue();
    const isOrderAdvance = v.receiptType === 'Order advance';
    if (isOrderAdvance && !v.salesOrderId) {
      this.form.controls.salesOrderId.setErrors({ required: true });
      return;
    }
    if (
      this.form.invalid ||
      this.saving() ||
      this.allocated() > (v.amount ?? 0)
    )
      return;
    const allocations = isOrderAdvance
      ? []
      : Object.entries(this.allocations())
          .filter(([, amount]) => amount > 0)
          .map(([id, amount]) => ({ salesInvoiceId: Number(id), amount }));
    this.saving.set(true);
    this.api
      .call(createReceipt, {
        body: {
          customerId: (v.customer as PickedCustomer).id,
          branchId: v.branchId as number,
          receiptDate: isoDate(v.receiptDate as Date),
          receiptType: v.receiptType,
          salesOrderId: isOrderAdvance ? v.salesOrderId : null,
          paymentMode: v.paymentMode,
          amount: v.amount as number,
          referenceNo: v.referenceNo?.trim() || null,
          bankName: v.bankName?.trim() || null,
          chequeDate: v.chequeDate ? isoDate(v.chequeDate) : null,
          remarks: v.remarks?.trim() || null,
          allocations,
        },
      })
      .pipe(
        finalize(() => this.saving.set(false)),
        catchError(() => EMPTY),
      )
      .subscribe(
        (receipt) => void this.router.navigate(['/sales/receipts', receipt.id]),
      );
  }
}
