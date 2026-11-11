import { DecimalPipe } from '@angular/common';
import {
  ChangeDetectionStrategy,
  Component,
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
import { MatButton, MatIconButton } from '@angular/material/button';
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
import { MatIcon } from '@angular/material/icon';
import { MatInput } from '@angular/material/input';
import { MatOption, MatSelect } from '@angular/material/select';
import { MatTooltip } from '@angular/material/tooltip';
import { Router, RouterLink } from '@angular/router';
import {
  ApiClient,
  CustomerBranchOut,
  DeliveryLineIn,
  ItemListItem,
  OrderDetail,
  OrderLineOut,
  RackOut,
  createDelivery,
  getSalesOrder,
  listCustomerBranches,
} from '@trishul/core-api';
import { AuthStore } from '@trishul/core-auth';
import {
  InventoryLookups,
  ItemPicker,
  isoDate,
  n0,
  num,
} from '@trishul/inventory-data-access';
import {
  CustomerPicker,
  NO_SALES_OPTIONS,
  PickedCustomer,
  SAL_DELIVERY_OVER_ORDER,
  SalesLookups,
} from '@trishul/sales-data-access';
import { PageHeader } from '@trishul/shared-ui';
import { EMPTY, catchError, finalize, of } from 'rxjs';

function orderLine(line: OrderLineOut) {
  const left = n0(line.qtyToDeliver);
  return {
    source: line,
    form: new FormGroup({
      selected: new FormControl(left > 0, { nonNullable: true }),
      quantity: new FormControl<number | null>(left > 0 ? left : null, [
        Validators.required,
        Validators.min(0.001),
      ]),
      binId: new FormControl<number | null>(null),
    }),
  };
}
type OrderLineForm = ReturnType<typeof orderLine>;

function directLine() {
  return new FormGroup({
    item: new FormControl<ItemListItem | null>(null, Validators.required),
    quantity: new FormControl<number | null>(1, [
      Validators.required,
      Validators.min(0.001),
    ]),
    unitPrice: new FormControl<number | null>(null, Validators.min(0)),
    gstPct: new FormControl<number | null>(18, [
      Validators.min(0),
      Validators.max(100),
    ]),
    binId: new FormControl<number | null>(null),
  });
}
type DirectLine = ReturnType<typeof directLine>;

/** Deliver goods: against an approved order (?orderId=) or direct. Stock goes out at once, oldest GRN batch first. */
@Component({
  selector: 'trishul-delivery-form-page',
  imports: [
    DecimalPipe,
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
    MatIconButton,
    MatIcon,
    MatTooltip,
    CustomerPicker,
    ItemPicker,
    PageHeader,
  ],
  providers: [provideNativeDateAdapter()],
  changeDetection: ChangeDetectionStrategy.OnPush,
  styleUrl: '../../../../inventory/data-access/src/lib/inventory.scss',
  styles: `
    input.cell {
      width: 6rem;
      padding: 0.3rem 0.4rem;
      border: 1px solid var(--mat-sys-outline-variant);
      border-radius: 4px;
      background: transparent;
      color: inherit;
      font: inherit;
    }
    select.cell {
      padding: 0.3rem;
      background: transparent;
      color: inherit;
      font: inherit;
      border: 1px solid var(--mat-sys-outline-variant);
      border-radius: 4px;
    }
  `,
  template: `
    <trishul-page-header
      [title]="
        order() ? 'Deliver order ' + order()!.orderNo : 'Direct delivery'
      "
      [subtitle]="
        order()
          ? order()!.customerName +
            ' · stock goes out at once, oldest GRN batch first'
          : 'Goods to a customer without a sales order; invoice it afterwards'
      "
    />
    <form [formGroup]="form" (ngSubmit)="save()">
      <section class="card">
        <h2>Delivery</h2>
        <div class="form-grid">
          @if (!order()) {
            <trishul-customer-picker formControlName="customer" />
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
          }
          <mat-form-field appearance="outline">
            <mat-label>Customer branch</mat-label>
            <mat-select formControlName="customerSiteId">
              <mat-option [value]="null">{{
                order() ? "The order's" : 'Billing address'
              }}</mat-option>
              @for (b of sites(); track b.id) {
                <mat-option [value]="b.id">{{ b.siteName }}</mat-option>
              }
            </mat-select>
          </mat-form-field>
          <mat-form-field appearance="outline">
            <mat-label>Dispatch from</mat-label>
            <mat-select
              formControlName="locationId"
              (valueChange)="loadRacks($event)"
            >
              @for (l of options().locations; track l.id) {
                <mat-option [value]="l.id"
                  >{{ l.branchName }} · {{ l.name }}</mat-option
                >
              }
            </mat-select>
            <mat-error>Choose the stock location.</mat-error>
          </mat-form-field>
          <mat-form-field appearance="outline">
            <mat-label>Delivery date</mat-label>
            <input
              matInput
              [matDatepicker]="datePicker"
              formControlName="deliveryDate"
              [max]="today"
            />
            <mat-datepicker-toggle
              matSuffix
              [for]="datePicker"
            /><mat-datepicker #datePicker />
          </mat-form-field>
          <mat-form-field appearance="outline">
            <mat-label>Delivery reference</mat-label>
            <input matInput formControlName="deliveryReference" />
          </mat-form-field>
          <mat-form-field appearance="outline">
            <mat-label>Vehicle no</mat-label>
            <input matInput formControlName="vehicleNo" />
          </mat-form-field>
          <mat-form-field appearance="outline">
            <mat-label>Transporter</mat-label>
            <input matInput formControlName="transporter" />
          </mat-form-field>
          <mat-form-field appearance="outline">
            <mat-label>LR / docket no</mat-label>
            <input matInput formControlName="lrNo" />
          </mat-form-field>
          <mat-form-field appearance="outline">
            <mat-label>Recipient</mat-label>
            <input matInput formControlName="receivedByName" />
          </mat-form-field>
          <mat-form-field appearance="outline">
            <mat-label>Recipient phone</mat-label>
            <input matInput formControlName="recipientPhone" />
          </mat-form-field>
          <mat-form-field appearance="outline" class="wide">
            <mat-label>Delivery address</mat-label>
            <textarea
              matInput
              rows="2"
              formControlName="shipToAddress"
            ></textarea>
            <mat-hint>Blank: the order's or customer branch's address</mat-hint>
          </mat-form-field>
          <mat-form-field appearance="outline" class="wide">
            <mat-label>Remarks</mat-label>
            <input matInput formControlName="remarks" />
          </mat-form-field>
        </div>
      </section>

      <section class="card">
        <h2>Items</h2>
        @if (order(); as o) {
          <table class="plain">
            <thead>
              <tr>
                <th></th>
                <th>Item</th>
                <th class="num">Ordered</th>
                <th class="num">Delivered</th>
                <th class="num">To deliver</th>
                <th>Qty now</th>
                <th>Rack</th>
              </tr>
            </thead>
            <tbody>
              @for (l of orderLines(); track l.source.id) {
                <tr [formGroup]="l.form">
                  <td><mat-checkbox formControlName="selected" /></td>
                  <td>
                    {{ l.source.itemCode }}
                    <div class="muted">{{ l.source.description }}</div>
                  </td>
                  <td class="num">
                    {{ l.source.quantity | number: '1.0-3' }}
                    {{ l.source.uomCode ?? '' }}
                  </td>
                  <td class="num">
                    {{ l.source.qtyDelivered | number: '1.0-3' }}
                  </td>
                  <td class="num">
                    {{ l.source.qtyToDeliver | number: '1.0-3' }}
                  </td>
                  <td>
                    <input
                      class="cell"
                      type="number"
                      min="0"
                      formControlName="quantity"
                      aria-label="Quantity"
                    />
                  </td>
                  <td>
                    <select
                      class="cell"
                      formControlName="binId"
                      aria-label="Rack"
                    >
                      <option [ngValue]="null">Any rack</option>
                      @for (r of racks(); track r.id) {
                        <option [ngValue]="r.id">{{ r.code }}</option>
                      }
                    </select>
                  </td>
                </tr>
              }
            </tbody>
          </table>
          @if (canOver) {
            <mat-checkbox
              [formControl]="overDeliver"
              style="margin-top: 0.5rem"
            >
              Allow delivering more than is outstanding
            </mat-checkbox>
          }
        } @else {
          <div class="lines">
            @for (line of direct(); track line; let i = $index) {
              <div class="line" [formGroup]="line">
                <span class="index">{{ i + 1 }}</span>
                <trishul-item-picker
                  formControlName="item"
                  [stockOnly]="false"
                />
                <mat-form-field appearance="outline" subscriptSizing="dynamic">
                  <mat-label>Qty</mat-label>
                  <input
                    matInput
                    type="number"
                    min="0"
                    formControlName="quantity"
                  />
                </mat-form-field>
                <mat-form-field appearance="outline" subscriptSizing="dynamic">
                  <mat-label>Price to invoice (₹)</mat-label>
                  <input
                    matInput
                    type="number"
                    min="0"
                    formControlName="unitPrice"
                  />
                </mat-form-field>
                <mat-form-field appearance="outline" subscriptSizing="dynamic">
                  <mat-label>GST %</mat-label>
                  <input
                    matInput
                    type="number"
                    min="0"
                    formControlName="gstPct"
                  />
                </mat-form-field>
                <mat-form-field appearance="outline" subscriptSizing="dynamic">
                  <mat-label>Rack</mat-label>
                  <mat-select formControlName="binId">
                    <mat-option [value]="null">Any rack</mat-option>
                    @for (r of racks(); track r.id) {
                      <mat-option [value]="r.id">{{ r.code }}</mat-option>
                    }
                  </mat-select>
                </mat-form-field>
                <button
                  mat-icon-button
                  type="button"
                  class="remove"
                  matTooltip="Remove line"
                  [disabled]="direct().length === 1"
                  (click)="removeDirect(i)"
                >
                  <mat-icon>delete</mat-icon>
                </button>
              </div>
            }
          </div>
          <button mat-button type="button" (click)="addDirect()">
            <mat-icon>add</mat-icon>Add line
          </button>
        }
      </section>

      <div class="form-actions">
        <span class="summary"
          >Batches are taken oldest GRN date first; the GRN references stay on
          the delivery.</span
        >
        <a
          mat-button
          [routerLink]="
            order() ? ['/sales/orders', order()!.id] : ['/sales/deliveries']
          "
          >Cancel</a
        >
        <button mat-flat-button type="submit" [disabled]="saving()">
          Post delivery
        </button>
      </div>
    </form>
  `,
})
export class DeliveryFormPage {
  private readonly api = inject(ApiClient);
  private readonly router = inject(Router);
  private readonly auth = inject(AuthStore);
  private readonly inventory = inject(InventoryLookups);
  protected readonly canOver = this.auth.hasPermission(SAL_DELIVERY_OVER_ORDER);

  /** ?orderId=… from an order or the outstanding list. */
  readonly orderId = input<string>();

  protected readonly today = new Date();
  protected readonly options = toSignal(inject(SalesLookups).options(), {
    initialValue: NO_SALES_OPTIONS,
  });
  protected readonly order = signal<OrderDetail | null>(null);
  protected readonly orderLines = signal<OrderLineForm[]>([]);
  protected readonly direct = signal<DirectLine[]>([directLine()]);
  protected readonly sites = signal<CustomerBranchOut[]>([]);
  protected readonly racks = signal<RackOut[]>([]);
  protected readonly saving = signal(false);
  protected readonly overDeliver = new FormControl(false, {
    nonNullable: true,
  });

  protected readonly form = new FormGroup({
    customer: new FormControl<PickedCustomer | null>(null),
    principalId: new FormControl<number | null>(null),
    branchId: new FormControl<number | null>(null),
    customerSiteId: new FormControl<number | null>(null),
    locationId: new FormControl<number | null>(null, Validators.required),
    deliveryDate: new FormControl<Date | null>(new Date()),
    deliveryReference: new FormControl<string | null>(
      null,
      Validators.maxLength(40),
    ),
    vehicleNo: new FormControl<string | null>(null, Validators.maxLength(20)),
    transporter: new FormControl<string | null>(
      null,
      Validators.maxLength(100),
    ),
    lrNo: new FormControl<string | null>(null, Validators.maxLength(40)),
    receivedByName: new FormControl<string | null>(
      null,
      Validators.maxLength(100),
    ),
    recipientPhone: new FormControl<string | null>(
      null,
      Validators.maxLength(15),
    ),
    shipToAddress: new FormControl<string | null>(
      null,
      Validators.maxLength(500),
    ),
    remarks: new FormControl<string | null>(null, Validators.maxLength(500)),
  });

  constructor() {
    this.form.controls.customer.valueChanges.subscribe((c) =>
      this.loadSites(c?.id ?? null),
    );
    effect(() => {
      const o = this.options();
      untracked(() => {
        const f = this.form.controls;
        if (f.branchId.value === null)
          f.branchId.setValue(o.defaultBranchId ?? this.auth.branchId());
        if (f.principalId.value === null)
          f.principalId.setValue(o.defaultBrandId ?? this.auth.principalId());
        if (f.locationId.value === null && o.locations.length === 1) {
          f.locationId.setValue(o.locations[0].id);
          this.loadRacks(o.locations[0].id);
        }
      });
    });
    effect(() => {
      const id = Number(this.orderId());
      if (id) untracked(() => this.loadOrder(id));
    });
  }

  private loadOrder(id: number): void {
    this.api
      .call(getSalesOrder, { orderId: id })
      .pipe(catchError(() => EMPTY))
      .subscribe((o) => {
        this.order.set(o);
        this.orderLines.set(
          o.lines.filter((l) => n0(l.qtyToDeliver) > 0).map(orderLine),
        );
        this.loadSites(o.customerId);
      });
  }

  private loadSites(customerId: number | null): void {
    this.sites.set([]);
    this.form.controls.customerSiteId.setValue(null);
    if (!customerId) return;
    this.api
      .call(listCustomerBranches, { customerId })
      .pipe(catchError(() => of([] as CustomerBranchOut[])))
      .subscribe((sites) => this.sites.set(sites));
  }

  protected loadRacks(locationId: number | null): void {
    this.inventory
      .racks(locationId)
      .subscribe((racks) => this.racks.set(racks));
  }

  protected addDirect(): void {
    this.direct.update((lines) => [...lines, directLine()]);
  }

  protected removeDirect(index: number): void {
    this.direct.update((lines) => lines.filter((_, i) => i !== index));
  }

  protected save(): void {
    this.form.markAllAsTouched();
    const o = this.order();
    let lines: DeliveryLineIn[];
    if (o) {
      const chosen = this.orderLines().filter(
        (l) => l.form.controls.selected.value,
      );
      chosen.forEach((l) => l.form.markAllAsTouched());
      if (!chosen.length || chosen.some((l) => l.form.invalid)) return;
      lines = chosen.map((l) => ({
        salesOrderLineId: l.source.id,
        quantity: l.form.controls.quantity.value as number,
        binId: l.form.controls.binId.value,
      }));
    } else {
      this.direct().forEach((d) => d.markAllAsTouched());
      const f = this.form.controls;
      if (!f.customer.value || !f.principalId.value || !f.branchId.value) {
        f.customer.setErrors({ required: true });
        return;
      }
      if (this.direct().some((d) => d.invalid)) return;
      lines = this.direct().map((d) => {
        const v = d.getRawValue();
        return {
          itemId: (v.item as ItemListItem).id,
          quantity: v.quantity as number,
          unitPrice: num(v.unitPrice),
          gstPct: v.gstPct ?? 18,
          binId: v.binId,
        };
      });
    }
    if (this.form.invalid || this.saving()) return;
    const v = this.form.getRawValue();
    this.saving.set(true);
    this.api
      .call(createDelivery, {
        body: {
          salesOrderId: o?.id ?? null,
          customerId: o ? null : (v.customer as PickedCustomer).id,
          principalId: o ? null : v.principalId,
          branchId: o ? null : v.branchId,
          customerSiteId: v.customerSiteId,
          locationId: v.locationId as number,
          deliveryDate: v.deliveryDate ? isoDate(v.deliveryDate) : null,
          deliveryReference: v.deliveryReference?.trim() || null,
          vehicleNo: v.vehicleNo?.trim() || null,
          transporter: v.transporter?.trim() || null,
          lrNo: v.lrNo?.trim() || null,
          receivedByName: v.receivedByName?.trim() || null,
          recipientPhone: v.recipientPhone?.trim() || null,
          shipToAddress: v.shipToAddress?.trim() || null,
          remarks: v.remarks?.trim() || null,
          overDeliver: this.overDeliver.value,
          lines,
        },
      })
      .pipe(
        finalize(() => this.saving.set(false)),
        catchError(() => EMPTY),
      )
      .subscribe(
        (note) => void this.router.navigate(['/sales/deliveries', note.id]),
      );
  }
}
