import { DatePipe } from '@angular/common';
import {
  ChangeDetectionStrategy,
  Component,
  computed,
  inject,
  input,
  signal,
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
  OpenInvoice,
  createSupplierPayment,
  getSupplierOpenItems,
} from '@trishul/core-api';
import { AuthStore } from '@trishul/core-auth';
import { InventoryLookups, isoDate, num } from '@trishul/inventory-data-access';
import { PageHeader } from '@trishul/shared-ui';
import { EMPTY, catchError, finalize } from 'rxjs';
import { rupees } from './purchases.shared';

type Mode = 'NEFT' | 'RTGS' | 'Cheque' | 'Cash' | 'UPI';
const MODES: { value: Mode; label: string }[] = [
  { value: 'NEFT', label: 'Bank transfer (NEFT)' },
  { value: 'RTGS', label: 'Bank transfer (RTGS)' },
  { value: 'Cheque', label: 'Cheque' },
  { value: 'UPI', label: 'UPI' },
  { value: 'Cash', label: 'Cash' },
];

/** Record a payment to a supplier and (optionally) set it against invoices; the rest stays an advance. */
@Component({
  selector: 'trishul-payment-form-page',
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
      title="Record payment to supplier"
      subtitle="Set it against invoices now, or keep it as an advance"
    />
    <form [formGroup]="form" (ngSubmit)="save()">
      <section class="card">
        <h2>Payment</h2>
        <div class="form-grid">
          <mat-form-field appearance="outline">
            <mat-label>Supplier</mat-label>
            <mat-select
              formControlName="supplierId"
              (valueChange)="loadInvoices($event)"
            >
              @for (s of suppliers(); track s.id) {
                <mat-option [value]="s.id"
                  >{{ s.name }} · {{ money(s.balance) }}</mat-option
                >
              }
            </mat-select>
            <mat-error>Choose the supplier.</mat-error>
          </mat-form-field>
          <mat-form-field appearance="outline">
            <mat-label>Paid from branch</mat-label>
            <mat-select formControlName="branchId">
              @for (b of branches(); track b.id) {
                <mat-option [value]="b.id">{{ b.name }}</mat-option>
              }
            </mat-select>
            <mat-error>Choose the branch.</mat-error>
          </mat-form-field>
          <mat-form-field appearance="outline">
            <mat-label>Payment date</mat-label>
            <input
              matInput
              [matDatepicker]="datePicker"
              formControlName="paymentDate"
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
              <th>Their no</th>
              <th>Due</th>
              <th class="num">Outstanding</th>
              <th class="num">Pay now</th>
            </tr>
          </thead>
          <tbody>
            @for (i of invoices(); track i.id) {
              <tr>
                <td>{{ i.invoiceNo }}</td>
                <td>{{ i.supplierInvoiceNo }}</td>
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
                    [attr.aria-label]="'Pay now on ' + i.invoiceNo"
                  />
                </td>
              </tr>
            } @empty {
              <tr>
                <td colspan="5" class="empty">
                  {{
                    form.controls.supplierId.value
                      ? 'No outstanding invoices: the payment is an advance.'
                      : 'Choose the supplier.'
                  }}
                </td>
              </tr>
            }
          </tbody>
        </table>
      </section>

      <div class="form-actions">
        <span
          class="summary"
          [class.negative]="allocated() > (form.controls.amount.value ?? 0)"
        >
          Allocated {{ money(allocated()) }} · advance
          {{
            money(Math.max((form.controls.amount.value ?? 0) - allocated(), 0))
          }}
        </span>
        <a mat-button routerLink="/purchases/payments">Cancel</a>
        <button mat-flat-button type="submit" [disabled]="saving()">
          Record payment
        </button>
      </div>
    </form>
  `,
})
export class PaymentFormPage {
  private readonly api = inject(ApiClient);
  private readonly router = inject(Router);
  private readonly lookups = inject(InventoryLookups);
  private readonly auth = inject(AuthStore);

  readonly supplierId = input<string>();

  protected readonly Math = Math;
  protected readonly today = new Date();
  protected readonly modes = MODES;
  protected readonly money = (v: number | string) => rupees(v);
  protected readonly suppliers = toSignal(this.lookups.suppliers(), {
    initialValue: [],
  });
  protected readonly branches = toSignal(this.lookups.branches(), {
    initialValue: [],
  });
  protected readonly invoices = signal<OpenInvoice[]>([]);
  private readonly allocations = signal<Record<number, number>>({});
  protected readonly allocated = computed(() =>
    Object.values(this.allocations()).reduce((s, v) => s + v, 0),
  );
  protected readonly saving = signal(false);

  protected readonly form = new FormGroup({
    supplierId: new FormControl<number | null>(null, Validators.required),
    branchId: new FormControl<number | null>(
      this.auth.branchId(),
      Validators.required,
    ),
    paymentDate: new FormControl<Date | null>(new Date(), Validators.required),
    paymentMode: new FormControl<Mode>('NEFT', { nonNullable: true }),
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
    queueMicrotask(() => {
      const supplier = Number(this.supplierId());
      if (supplier) {
        this.form.controls.supplierId.setValue(supplier);
        this.loadInvoices(supplier);
      }
    });
  }

  protected loadInvoices(supplierId: number): void {
    this.allocations.set({});
    this.invoices.set([]);
    this.api
      .call(getSupplierOpenItems, { supplierId })
      .pipe(catchError(() => EMPTY))
      .subscribe((items) => this.invoices.set(items.invoices));
  }

  protected allocation(invoiceId: number): number {
    return this.allocations()[invoiceId] ?? 0;
  }

  protected setAllocation(invoice: OpenInvoice, value: string): void {
    const amount = Math.min(
      Math.max(Number(value) || 0, 0),
      num(invoice.outstanding) ?? 0,
    );
    this.allocations.update((a) => ({ ...a, [invoice.id]: amount }));
  }

  /** Fill the payment amount against the oldest due invoices first. */
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
    if (
      this.form.invalid ||
      this.saving() ||
      this.allocated() > (v.amount ?? 0)
    )
      return;
    const allocations = Object.entries(this.allocations())
      .filter(([, amount]) => amount > 0)
      .map(([id, amount]) => ({ supplierInvoiceId: Number(id), amount }));
    this.saving.set(true);
    this.api
      .call(createSupplierPayment, {
        body: {
          supplierId: v.supplierId as number,
          branchId: v.branchId as number,
          paymentDate: isoDate(v.paymentDate as Date),
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
        (payment) =>
          void this.router.navigate(['/purchases/payments', payment.id]),
      );
  }
}
