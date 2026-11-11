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
import { MatCheckbox } from '@angular/material/checkbox';
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
import { MatInput } from '@angular/material/input';
import { MatOption, MatSelect } from '@angular/material/select';
import { Router, RouterLink } from '@angular/router';
import {
  ApiClient,
  CustomerBranchOut,
  ItemListItem,
  OrderCreate,
  OrderDetail,
  createSalesOrder,
  getCustomerAccount,
  getItem,
  getSalesOrder,
  listCustomerBranches,
  updateSalesOrder,
  withRowVersion,
} from '@trishul/core-api';
import { AuthStore } from '@trishul/core-auth';
import { fromIso, isoDate, num } from '@trishul/inventory-data-access';
import {
  CustomerPicker,
  NO_SALES_OPTIONS,
  PickedCustomer,
  SalesLookups,
} from '@trishul/sales-data-access';
import { PageHeader } from '@trishul/shared-ui';
import { EMPTY, catchError, finalize, forkJoin, of } from 'rxjs';
import { SaleLines } from './sale-lines';
import {
  SaleLineForm,
  rupees,
  saleLine,
  saleLineBody,
  saleLinesTotals,
  saleLinesValid,
} from './sales.shared';

/** New sales order, or change a draft (/sales/orders/:orderId/edit). Saved as a draft. */
@Component({
  selector: 'trishul-order-form-page',
  imports: [
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
    MatCheckbox,
    MatDatepicker,
    MatDatepickerInput,
    MatDatepickerToggle,
    MatButton,
    CustomerPicker,
    PageHeader,
    SaleLines,
  ],
  providers: [provideNativeDateAdapter()],
  changeDetection: ChangeDetectionStrategy.OnPush,
  styleUrl: '../../../../inventory/data-access/src/lib/inventory.scss',
  template: `
    <trishul-page-header
      [title]="existing() ? 'Edit ' + existing()!.orderNo : 'New sales order'"
      subtitle="Saved as a draft; send it for approval from the order page"
    />
    <form [formGroup]="form" (ngSubmit)="save()">
      <section class="card">
        <h2>Order</h2>
        <div class="form-grid">
          <trishul-customer-picker formControlName="customer" />
          <mat-form-field appearance="outline">
            <mat-label>Customer branch</mat-label>
            <mat-select
              formControlName="customerSiteId"
              (valueChange)="siteChanged($event)"
            >
              <mat-option [value]="null"
                >Head office / billing address</mat-option
              >
              @for (b of sites(); track b.id) {
                <mat-option [value]="b.id"
                  >{{ b.siteName
                  }}{{ b.siteCode ? ' (' + b.siteCode + ')' : '' }}</mat-option
                >
              }
            </mat-select>
          </mat-form-field>
          <mat-form-field appearance="outline">
            <mat-label>Brand</mat-label>
            <mat-select formControlName="principalId">
              @for (b of options().brands; track b.id) {
                <mat-option [value]="b.id">{{ b.name }}</mat-option>
              }
            </mat-select>
            <mat-error>Choose the brand.</mat-error>
          </mat-form-field>
          <mat-form-field appearance="outline">
            <mat-label>Selling branch</mat-label>
            <mat-select formControlName="branchId">
              @for (b of options().branches; track b.id) {
                <mat-option [value]="b.id">{{ b.name }}</mat-option>
              }
            </mat-select>
            <mat-error>Choose the branch.</mat-error>
          </mat-form-field>
          <mat-form-field appearance="outline">
            <mat-label>Order date</mat-label>
            <input
              matInput
              [matDatepicker]="datePicker"
              formControlName="orderDate"
            />
            <mat-datepicker-toggle
              matSuffix
              [for]="datePicker"
            /><mat-datepicker #datePicker />
          </mat-form-field>
          <mat-form-field appearance="outline">
            <mat-label>Expected delivery</mat-label>
            <input
              matInput
              [matDatepicker]="expPicker"
              formControlName="expectedDeliveryDate"
            />
            <mat-datepicker-toggle matSuffix [for]="expPicker" /><mat-datepicker
              #expPicker
            />
          </mat-form-field>
          <mat-form-field appearance="outline">
            <mat-label>Customer's PO no</mat-label>
            <input matInput formControlName="customerPoNo" />
          </mat-form-field>
          <mat-form-field appearance="outline">
            <mat-label>PO date</mat-label>
            <input
              matInput
              [matDatepicker]="poPicker"
              formControlName="customerPoDate"
            />
            <mat-datepicker-toggle matSuffix [for]="poPicker" /><mat-datepicker
              #poPicker
            />
          </mat-form-field>
          <mat-form-field appearance="outline">
            <mat-label>Payment terms</mat-label>
            <mat-select formControlName="paymentTermsId">
              <mat-option [value]="null">Customer's terms</mat-option>
              @for (t of options().paymentTerms; track t.id) {
                <mat-option [value]="t.id">{{ t.name }}</mat-option>
              }
            </mat-select>
          </mat-form-field>
          <mat-form-field appearance="outline">
            <mat-label>Other charges (₹)</mat-label>
            <input
              matInput
              type="number"
              min="0"
              formControlName="otherCharges"
            />
            <mat-hint>Freight, packing, installation</mat-hint>
          </mat-form-field>
          <mat-checkbox formControlName="isPrepaid" style="align-self: center">
            Prepaid: the customer pays in advance
          </mat-checkbox>
          <mat-form-field appearance="outline" class="wide">
            <mat-label>Billing address</mat-label>
            <textarea
              matInput
              rows="2"
              formControlName="billToAddress"
            ></textarea>
            <mat-hint
              >Blank: the branch's or customer's billing address</mat-hint
            >
          </mat-form-field>
          <mat-form-field appearance="outline" class="wide">
            <mat-label>Delivery address</mat-label>
            <textarea
              matInput
              rows="2"
              formControlName="shipToAddress"
            ></textarea>
            <mat-hint>Blank: the customer branch's address</mat-hint>
          </mat-form-field>
          <mat-form-field appearance="outline" class="wide">
            <mat-label>Remarks</mat-label>
            <input matInput formControlName="remarks" />
          </mat-form-field>
        </div>
      </section>

      <section class="card">
        <h2>Items</h2>
        <trishul-sale-lines
          [(lines)]="lines"
          [principalId]="form.controls.principalId.value"
          [watch]="watched"
        />
      </section>

      <div class="form-actions">
        <span class="summary">
          Taxable {{ money(totals().taxable) }} · GST
          {{ money(totals().tax) }} · Other {{ money(totals().other) }} ·
          <strong>Total {{ money(totals().total) }}</strong>
        </span>
        <a
          mat-button
          [routerLink]="
            existing() ? ['/sales/orders', existing()!.id] : ['/sales/orders']
          "
          >Cancel</a
        >
        <button mat-flat-button type="submit" [disabled]="saving()">
          Save draft
        </button>
      </div>
    </form>
  `,
})
export class OrderFormPage {
  private readonly api = inject(ApiClient);
  private readonly router = inject(Router);
  private readonly auth = inject(AuthStore);

  readonly orderId = input<string>();
  /** ?customerId=… from a customer page. */
  readonly customerId = input<string>();

  protected readonly money = (v: number) => rupees(v);
  protected readonly options = toSignal(inject(SalesLookups).options(), {
    initialValue: NO_SALES_OPTIONS,
  });
  protected readonly existing = signal<OrderDetail | null>(null);
  protected readonly sites = signal<CustomerBranchOut[]>([]);
  protected readonly saving = signal(false);
  private readonly changes = signal(0);

  protected readonly form = new FormGroup({
    customer: new FormControl<PickedCustomer | null>(null, Validators.required),
    customerSiteId: new FormControl<number | null>(null),
    principalId: new FormControl<number | null>(null, Validators.required),
    branchId: new FormControl<number | null>(null, Validators.required),
    orderDate: new FormControl<Date | null>(new Date()),
    expectedDeliveryDate: new FormControl<Date | null>(null),
    customerPoNo: new FormControl<string | null>(
      null,
      Validators.maxLength(40),
    ),
    customerPoDate: new FormControl<Date | null>(null),
    paymentTermsId: new FormControl<number | null>(null),
    otherCharges: new FormControl<number | null>(0, Validators.min(0)),
    isPrepaid: new FormControl(false, { nonNullable: true }),
    billToAddress: new FormControl<string | null>(
      null,
      Validators.maxLength(500),
    ),
    shipToAddress: new FormControl<string | null>(
      null,
      Validators.maxLength(500),
    ),
    remarks: new FormControl<string | null>(null, Validators.maxLength(500)),
  });
  protected readonly watched = (line: SaleLineForm): SaleLineForm => {
    line.valueChanges.subscribe(() => this.changes.update((n) => n + 1));
    return line;
  };
  protected readonly lines = signal<SaleLineForm[]>([this.watched(saleLine())]);
  protected readonly totals = computed(() => {
    this.changes();
    return saleLinesTotals(
      this.lines(),
      this.form.controls.otherCharges.value ?? 0,
    );
  });
  private lastCustomer: number | null = null;

  constructor() {
    this.form.valueChanges.subscribe(() => this.changes.update((n) => n + 1));
    this.form.controls.customer.valueChanges.subscribe(() =>
      this.customerChanged(),
    );
    effect(() => {
      const o = this.options();
      untracked(() => {
        if (this.form.controls.branchId.value === null) {
          this.form.controls.branchId.setValue(
            o.defaultBranchId ?? this.auth.branchId(),
          );
        }
        if (this.form.controls.principalId.value === null) {
          this.form.controls.principalId.setValue(
            o.defaultBrandId ?? this.auth.principalId(),
          );
        }
      });
    });
    effect(() => {
      const id = Number(this.orderId());
      if (id) untracked(() => this.load(id));
    });
    effect(() => {
      const customer = Number(this.customerId());
      if (customer && !this.orderId())
        untracked(() =>
          this.api
            .call(getCustomerAccount, { customerId: customer })
            .pipe(catchError(() => EMPTY))
            .subscribe((c) => this.form.controls.customer.setValue(c)),
        );
    });
  }

  private load(id: number): void {
    this.api
      .call(getSalesOrder, { orderId: id })
      .pipe(catchError(() => EMPTY))
      .subscribe((o) => {
        this.existing.set(o);
        this.api
          .call(getCustomerAccount, { customerId: o.customerId })
          .pipe(catchError(() => EMPTY))
          .subscribe((c) => {
            this.lastCustomer = c.id;
            this.form.controls.customer.setValue(c);
            this.loadSites(c.id, o.customerSiteId);
          });
        this.form.patchValue({
          principalId: o.principalId,
          branchId: o.branchId,
          orderDate: fromIso(o.orderDate),
          expectedDeliveryDate: fromIso(o.expectedDeliveryDate),
          customerPoNo: o.customerPoNo,
          customerPoDate: fromIso(o.customerPoDate),
          paymentTermsId: o.paymentTermsId,
          otherCharges: num(o.otherCharges),
          isPrepaid: o.isPrepaid,
          billToAddress: o.billToAddress,
          shipToAddress: o.shipToAddress,
          remarks: o.remarks,
        });
        this.form.controls.branchId.disable();
        forkJoin(
          o.lines.map((l) =>
            this.api.call(getItem, { itemId: l.itemId as number }),
          ),
        ).subscribe((items) => {
          this.lines.set(
            o.lines.map((l, i) => {
              const line = this.watched(saleLine());
              line.patchValue({
                item: items[i] as unknown as ItemListItem,
                description: l.description,
                quantity: num(l.quantity),
                unitPrice: num(l.unitPrice),
                discountPct: num(l.discountPct),
                gstPct: num(l.gstPct),
              });
              return line;
            }),
          );
        });
      });
  }

  private customerChanged(): void {
    const customer = this.form.controls.customer.value;
    if ((customer?.id ?? null) === this.lastCustomer) return;
    this.lastCustomer = customer?.id ?? null;
    this.form.patchValue({
      customerSiteId: null,
      billToAddress: null,
      shipToAddress: null,
    });
    this.sites.set([]);
    if (customer) this.loadSites(customer.id, null);
  }

  private loadSites(customerId: number, selected: number | null): void {
    this.api
      .call(listCustomerBranches, { customerId })
      .pipe(catchError(() => of([] as CustomerBranchOut[])))
      .subscribe((sites) => {
        this.sites.set(sites);
        const chosen = selected ?? sites.find((s) => s.isDefault)?.id ?? null;
        this.form.controls.customerSiteId.setValue(chosen);
      });
  }

  /** A different customer branch: its addresses replace what was filled in by default. */
  protected siteChanged(siteId: number | null): void {
    const site = this.sites().find((s) => s.id === siteId);
    this.form.patchValue({
      billToAddress: site?.billingAddress ?? null,
      shipToAddress: site?.address ?? null,
    });
  }

  protected save(): void {
    this.form.markAllAsTouched();
    for (const line of this.lines()) line.markAllAsTouched();
    if (
      this.form.invalid ||
      !saleLinesValid(this.lines(), false) ||
      this.saving()
    )
      return;
    const v = this.form.getRawValue();
    const body: OrderCreate = {
      customerId: (v.customer as PickedCustomer).id,
      customerSiteId: v.customerSiteId,
      principalId: v.principalId as number,
      branchId: v.branchId as number,
      orderDate: v.orderDate ? isoDate(v.orderDate) : null,
      expectedDeliveryDate: v.expectedDeliveryDate
        ? isoDate(v.expectedDeliveryDate)
        : null,
      customerPoNo: v.customerPoNo?.trim() || null,
      customerPoDate: v.customerPoDate ? isoDate(v.customerPoDate) : null,
      paymentTermsId: v.paymentTermsId,
      otherCharges: v.otherCharges ?? 0,
      isPrepaid: v.isPrepaid,
      billToAddress: v.billToAddress?.trim() || null,
      shipToAddress: v.shipToAddress?.trim() || null,
      remarks: v.remarks?.trim() || null,
      lines: this.lines().map((l) => ({
        ...saleLineBody(l),
        itemId: l.controls.item.value?.id as number,
      })),
    };
    const existing = this.existing();
    this.saving.set(true);
    const request = existing
      ? this.api.call(
          updateSalesOrder,
          { orderId: existing.id, body },
          withRowVersion(existing.rowVersion),
        )
      : this.api.call(createSalesOrder, { body });
    request
      .pipe(
        finalize(() => this.saving.set(false)),
        catchError(() => EMPTY),
      )
      .subscribe((o) => void this.router.navigate(['/sales/orders', o.id]));
  }
}
