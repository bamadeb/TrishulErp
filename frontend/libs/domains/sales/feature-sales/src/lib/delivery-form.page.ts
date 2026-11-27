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
import { MatSnackBar } from '@angular/material/snack-bar';
import { MatTooltip } from '@angular/material/tooltip';
import { Router, RouterLink } from '@angular/router';
import {
  ApiClient,
  CustomerBranchOut,
  DeliveryLineIn,
  ItemListItem,
  OrderDetail,
  OrderLineOut,
  PickList,
  RackOut,
  createDelivery,
  getSalesOrder,
  getSalesOrderPickList,
  listCustomerBranches,
} from '@trishul/core-api';
import { AuthStore } from '@trishul/core-auth';
import {
  InventoryLookups,
  ItemPicker,
  ScanBox,
  ScanHit,
  isoDate,
  placeScan,
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
    ScanBox,
    PageHeader,
  ],
  providers: [provideNativeDateAdapter()],
  changeDetection: ChangeDetectionStrategy.OnPush,
  styleUrl: '../../../../inventory/data-access/src/lib/inventory.scss',
  styles: `
    .pick-actions {
      display: flex;
      gap: 0.5rem;
      align-items: center;
      flex-wrap: wrap;
      margin-bottom: 0.75rem;
    }
    .pick-list {
      margin-bottom: 1rem;
    }
    .pick-list tr.done td {
      color: var(--mat-sys-on-surface-variant);
      text-decoration: line-through;
    }
    .warn {
      color: var(--mat-sys-error);
    }
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
                  <mat-option [value]="b.id"
                    ><span class="brand-option"
                      ><span class="brand-name">{{ b.name }}</span>
                      @if (b.companyName) {
                        <span class="brand-sep"> – </span
                        ><span class="brand-company">{{ b.companyName }}</span>
                      }
                    </span></mat-option
                  >
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
        <trishul-scan-box
          screen="delivery"
          [label]="order() ? 'Pick by scan' : 'Scan'"
          [locationId]="locationId()"
          (scanned)="onScan($event)"
        />
        @if (order(); as o) {
          <div class="pick-actions">
            <button
              mat-stroked-button
              type="button"
              [disabled]="!locationId()"
              (click)="loadPickList()"
            >
              <mat-icon>checklist</mat-icon>Pick list
            </button>
            @if (pickList()) {
              <button mat-button type="button" (click)="printPickList()">
                <mat-icon>print</mat-icon>Print
              </button>
              <button mat-button type="button" (click)="pickList.set(null)">
                Hide
              </button>
            }
            <span class="muted"
              >Scan the bin, then each item taken from it. The first scan of a
              line replaces its quantity.</span
            >
          </div>
          @if (pickList(); as p) {
            <table class="plain pick-list">
              <thead>
                <tr>
                  <th>Bin</th>
                  <th>Item</th>
                  <th>GRN batch</th>
                  <th class="num">To pick</th>
                  <th class="num">Picked</th>
                </tr>
              </thead>
              <tbody>
                @for (r of p.rows; track $index) {
                  <tr
                    [class.done]="
                      pickedAt(r.orderLineId, r.binId) >= +r.quantity
                    "
                  >
                    <td>
                      <strong>{{ r.binCode ?? 'No bin' }}</strong>
                    </td>
                    <td>
                      {{ r.itemCode }}
                      <div class="muted">{{ r.itemDescription }}</div>
                    </td>
                    <td>{{ r.grnNo }} · {{ r.grnDate }}</td>
                    <td class="num">
                      {{ r.quantity | number: '1.0-3' }} {{ r.uomCode }}
                    </td>
                    <td class="num">
                      {{ pickedAt(r.orderLineId, r.binId) | number: '1.0-3' }}
                    </td>
                  </tr>
                } @empty {
                  <tr>
                    <td colspan="5" class="empty">
                      Nothing of this order is in stock here.
                    </td>
                  </tr>
                }
              </tbody>
            </table>
            @for (s of p.short; track s.orderLineId) {
              <p class="warn">
                Short: {{ s.itemCode }} – {{ s.quantity | number: '1.0-3' }}
                not in stock here (outside blocked bins).
              </p>
            }
          }
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
  private readonly snackBar = inject(MatSnackBar);
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

  protected readonly pickList = signal<PickList | null>(null);
  /** Scanned quantities per order line and bin ("lineId:binId"). */
  private readonly picked = signal<Record<string, number>>({});

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

  protected readonly locationId = toSignal(
    this.form.controls.locationId.valueChanges,
    { initialValue: null },
  );

  constructor() {
    this.form.controls.locationId.valueChanges.subscribe(() => {
      this.pickList.set(null);
      this.picked.set({});
    });
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

  protected loadPickList(): void {
    const o = this.order();
    const locationId = this.locationId();
    if (!o || !locationId) return;
    this.api
      .call(getSalesOrderPickList, { orderId: o.id, locationId })
      .pipe(catchError(() => EMPTY))
      .subscribe((p) => this.pickList.set(p));
  }

  protected pickedAt(lineId: number, binId: number | null): number {
    return this.picked()[`${lineId}:${binId ?? 0}`] ?? 0;
  }

  /** Scanned quantity of an order line, all bins together. */
  private pickedFor(line: OrderLineForm): number {
    return Object.entries(this.picked())
      .filter(([k]) => k.startsWith(`${line.source.id}:`))
      .reduce((sum, [, q]) => sum + q, 0);
  }

  /**
   * A scanned item. Direct: onto its line. Against an order: picks it for the order line of that item; the line's
   * quantity becomes what was scanned, and its rack the bin it was scanned in (any rack when picked from several).
   */
  protected onScan(hit: ScanHit): void {
    if (!this.order()) {
      const added = placeScan(
        this.direct(),
        hit,
        (d) => ({
          item: d.controls.item,
          quantity: d.controls.quantity,
          bin: d.controls.binId,
        }),
        () => directLine(),
      );
      if (added) this.direct.set(added);
      return;
    }
    const candidates = this.orderLines().filter(
      (l) => l.source.itemId === hit.item.id,
    );
    if (!candidates.length) {
      this.snackBar.open(`${hit.item.itemCode} is not on this order.`, 'OK', {
        duration: 4000,
      });
      return;
    }
    const line =
      candidates.find((l) => this.pickedFor(l) < n0(l.source.qtyToDeliver)) ??
      candidates[candidates.length - 1];
    const key = `${line.source.id}:${hit.binId ?? 0}`;
    this.picked.update((p) => ({
      ...p,
      [key]: Math.round(((p[key] ?? 0) + hit.quantity) * 1000) / 1000,
    }));
    const bins = Object.keys(this.picked())
      .filter((k) => k.startsWith(`${line.source.id}:`))
      .map((k) => Number(k.split(':')[1]));
    const picked = this.pickedFor(line);
    line.form.patchValue({
      selected: true,
      quantity: picked,
      binId: bins.length === 1 && bins[0] ? bins[0] : null,
    });
    if (picked > n0(line.source.qtyToDeliver)) {
      this.snackBar.open(
        `${hit.item.itemCode}: ${picked} picked, only ${n0(line.source.qtyToDeliver)} to deliver.`,
        'OK',
        { duration: 5000 },
      );
    }
  }

  protected printPickList(): void {
    const p = this.pickList();
    const o = this.order();
    if (!p || !o) return;
    const esc = (v: unknown) =>
      String(v ?? '').replace(/[&<>"]/g, (c) => `&#${c.charCodeAt(0)};`);
    const rows = p.rows
      .map(
        (r) =>
          `<tr><td><b>${esc(r.binCode ?? 'No bin')}</b></td><td>${esc(r.itemCode)}<br><small>${esc(r.itemDescription)}</small></td><td>${esc(r.grnNo)} · ${esc(r.grnDate)}</td><td style="text-align:right">${esc(Number(r.quantity))} ${esc(r.uomCode)}</td><td style="width:4em"></td></tr>`,
      )
      .join('');
    const short = p.short
      .map(
        (s) =>
          `<p>Short: ${esc(s.itemCode)} – ${esc(Number(s.quantity))} not in stock here</p>`,
      )
      .join('');
    const win = window.open('', '_blank', 'width=900,height=700');
    if (!win) return;
    win.document.write(
      `<html><head><title>Pick list ${esc(o.orderNo)}</title><style>body{font-family:sans-serif;font-size:12px}table{border-collapse:collapse;width:100%}td,th{border:1px solid #999;padding:4px;text-align:left}</style></head><body><h2>Pick list · order ${esc(o.orderNo)} · ${esc(p.locationCode)}</h2><p>${esc(o.customerName)}</p><table><thead><tr><th>Bin</th><th>Item</th><th>GRN batch</th><th>Qty</th><th>Picked</th></tr></thead><tbody>${rows}</tbody></table>${short}</body></html>`,
    );
    win.document.close();
    win.focus();
    win.print();
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
