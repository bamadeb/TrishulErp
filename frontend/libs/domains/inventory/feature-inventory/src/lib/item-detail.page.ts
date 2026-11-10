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
import { MatButton, MatIconButton } from '@angular/material/button';
import { MatDialog } from '@angular/material/dialog';
import { MatIcon } from '@angular/material/icon';
import { MatPaginator, PageEvent } from '@angular/material/paginator';
import { MatProgressBar } from '@angular/material/progress-bar';
import { MatTab, MatTabGroup } from '@angular/material/tabs';
import { MatTooltip } from '@angular/material/tooltip';
import { RouterLink } from '@angular/router';
import {
  ApiClient,
  ConversionOut,
  ConversionUpdate,
  ItemDetail,
  ItemPrices,
  MovementRow,
  PurchasePriceCreate,
  PurchasePriceOut,
  PurchasePriceUpdate,
  SalesPriceCreate,
  SalesPriceOut,
  SalesPriceUpdate,
  StockRow,
  createPurchasePrice,
  createSalesPrice,
  createUomConversion,
  getItem,
  getItemPrices,
  listMovements,
  listPriceLists,
  listStock,
  listUomConversions,
  updatePurchasePrice,
  updateSalesPrice,
  updateUomConversion,
  withRowVersion,
} from '@trishul/core-api';
import { AuthStore, HasPermission } from '@trishul/core-auth';
import { PageHeader } from '@trishul/shared-ui';
import {
  EMPTY,
  Observable,
  catchError,
  filter,
  finalize,
  map,
  of,
  switchMap,
} from 'rxjs';
import { openFieldsDialog } from './fields.dialog';
import {
  INV_ITEM_MANAGE,
  INV_ITEM_VIEW_PERMISSIONS,
  INV_STOCK_USER_PERMISSIONS,
  INV_STOCK_VIEW,
} from '@trishul/inventory-data-access';
import { InventoryLookups, ageClass, n0, num } from './inventory.shared';

/** One item: stock by GRN batch, movements, sales / purchase prices and unit conversions. */
@Component({
  selector: 'trishul-item-detail-page',
  imports: [
    DatePipe,
    DecimalPipe,
    RouterLink,
    MatButton,
    MatIconButton,
    MatIcon,
    MatTooltip,
    MatProgressBar,
    MatPaginator,
    MatTabGroup,
    MatTab,
    HasPermission,
    PageHeader,
  ],
  changeDetection: ChangeDetectionStrategy.OnPush,
  styleUrl: './inventory.scss',
  template: `
    @if (item(); as i) {
      <trishul-page-header
        [title]="i.itemCode + ' · ' + i.description"
        [subtitle]="
          i.categoryName +
          ' · ' +
          i.itemType +
          (i.isActive ? '' : ' · Inactive')
        "
      >
        <a mat-stroked-button routerLink="/inventory/items"
          ><mat-icon>arrow_back</mat-icon>Items</a
        >
        <a mat-flat-button routerLink="edit" *trishulHasPermission="manage"
          ><mat-icon>edit</mat-icon>Edit</a
        >
      </trishul-page-header>

      <div class="tiles">
        <div class="tile">
          <div class="value">{{ i.qtyOnHand | number: '1.0-3' }}</div>
          <div class="label">On hand ({{ i.uomCode }})</div>
        </div>
        <div class="tile">
          <div class="value">₹{{ i.stockValue | number: '1.0-0' }}</div>
          <div class="label">Stock value at GRN cost</div>
        </div>
        <div class="tile">
          <div class="value">{{ money(prices()?.averageCost) }}</div>
          <div class="label">Average cost on hand</div>
        </div>
        <div class="tile">
          <div class="value">{{ money(i.standardCost) }}</div>
          <div class="label">Standard cost</div>
        </div>
        <div class="tile">
          <div class="value">{{ money(i.lastPurchaseCost) }}</div>
          <div class="label">Last purchase cost</div>
        </div>
        <div class="tile">
          <div class="value" [class.negative]="belowReorder()">
            {{
              i.reorderLevel !== null ? (i.reorderLevel | number: '1.0-3') : '—'
            }}
          </div>
          <div class="label">
            Reorder level{{
              i.reorderQty ? ' (order ' + i.reorderQty + ')' : ''
            }}
          </div>
        </div>
      </div>

      <section class="card">
        <dl class="facts">
          <div>
            <dt>Category</dt>
            <dd>{{ i.categoryName }}</dd>
          </div>
          <div>
            <dt>Stock unit</dt>
            <dd>{{ i.uomCode }}</dd>
          </div>
          <div>
            <dt>Brand</dt>
            <dd>{{ i.principalCode ?? 'Common item' }}</dd>
          </div>
          <div>
            <dt>OEM part no</dt>
            <dd>{{ i.oemPartNumber ?? '—' }}</dd>
          </div>
          <div>
            <dt>HSN / SAC</dt>
            <dd>{{ i.hsnCode ?? '—' }}</dd>
          </div>
          <div>
            <dt>MRP</dt>
            <dd>{{ money(i.mrp) }}</dd>
          </div>
          <div>
            <dt>Lead time</dt>
            <dd>
              {{ i.leadTimeDays !== null ? i.leadTimeDays + ' days' : '—' }}
            </dd>
          </div>
          <div>
            <dt>Tracking</dt>
            <dd>{{ tracking(i) }}</dd>
          </div>
          @if (i.longDescription) {
            <div style="grid-column: 1 / -1">
              <dt>Details</dt>
              <dd>{{ i.longDescription }}</dd>
            </div>
          }
        </dl>
      </section>

      <mat-tab-group mat-stretch-tabs="false" animationDuration="0ms">
        @if (canSeeStock) {
          <mat-tab label="Stock by GRN batch">
            <div class="table-card">
              <div class="table-scroll">
                <table class="plain wide">
                  <thead>
                    <tr>
                      <th>GRN / batch</th>
                      <th>GRN date</th>
                      <th>Age</th>
                      <th>Branch</th>
                      <th>Location</th>
                      <th>Rack</th>
                      <th class="num">Qty</th>
                      <th class="num">Unit cost</th>
                      <th class="num">Value</th>
                    </tr>
                  </thead>
                  <tbody>
                    @for (s of stock(); track s.lotBalanceId) {
                      <tr>
                        <td>
                          {{ s.grnNo }}
                          <div class="muted">
                            {{ s.lotNo }} · {{ s.sourceType }}
                          </div>
                        </td>
                        <td class="nowrap">
                          {{ s.grnDate | date: 'dd MMM yyyy' }}
                        </td>
                        <td>
                          <span
                            class="age"
                            [class]="'age ' + ageClass(s.ageDays)"
                            >{{ s.ageDays }} days</span
                          >
                        </td>
                        <td>{{ s.branchName }}</td>
                        <td>{{ s.locationName }}</td>
                        <td>{{ s.binCode ?? '—' }}</td>
                        <td class="num">{{ s.qtyOnHand | number: '1.0-3' }}</td>
                        <td class="num">{{ s.unitCost | number: '1.2-2' }}</td>
                        <td class="num">{{ s.value | number: '1.2-2' }}</td>
                      </tr>
                    } @empty {
                      <tr>
                        <td colspan="9" class="empty">
                          No stock of this item at your locations.
                        </td>
                      </tr>
                    }
                  </tbody>
                </table>
              </div>
            </div>
          </mat-tab>
        }
        @if (canSeeMovements) {
          <mat-tab label="Movements">
            <div class="table-card">
              <div class="progress">
                @if (movementsLoading()) {
                  <mat-progress-bar mode="indeterminate" />
                }
              </div>
              <div class="table-scroll">
                <table class="plain wide">
                  <thead>
                    <tr>
                      <th>When</th>
                      <th>Movement</th>
                      <th>Document</th>
                      <th>Where</th>
                      <th>GRN batch</th>
                      <th class="num">Qty</th>
                      <th class="num">Value</th>
                      <th>By</th>
                    </tr>
                  </thead>
                  <tbody>
                    @for (m of movements(); track m.id) {
                      <tr>
                        <td class="nowrap">
                          {{ m.moveAt | date: 'dd MMM yyyy, HH:mm' }}
                        </td>
                        <td>{{ m.movementName }}</td>
                        <td>{{ m.reference ?? '—' }}</td>
                        <td>
                          {{ m.branchName }} · {{ m.locationCode
                          }}{{ m.binCode ? ' · ' + m.binCode : '' }}
                        </td>
                        <td>
                          {{ m.grnNo ?? '—' }}
                          @if (m.grnDate) {
                            <div class="muted">
                              {{ m.grnDate | date: 'dd MMM yyyy' }}
                            </div>
                          }
                        </td>
                        <td
                          class="num"
                          [class.negative]="n0(m.quantity) < 0"
                          [class.positive]="n0(m.quantity) > 0"
                        >
                          {{ n0(m.quantity) > 0 ? '+' : ''
                          }}{{ m.quantity | number: '1.0-3' }}
                        </td>
                        <td class="num">
                          {{
                            m.value !== null ? (m.value | number: '1.2-2') : '—'
                          }}
                        </td>
                        <td>{{ m.performedBy ?? '—' }}</td>
                      </tr>
                    } @empty {
                      <tr>
                        <td colspan="8" class="empty">No movements yet.</td>
                      </tr>
                    }
                  </tbody>
                </table>
              </div>
              <mat-paginator
                [length]="movementTotal()"
                [pageIndex]="movementPage() - 1"
                [pageSize]="50"
                [hidePageSize]="true"
                aria-label="Pages of movements"
                (page)="onMovementPage($event)"
              />
            </div>
          </mat-tab>
        }
        @if (canSeePrices) {
          <mat-tab label="Prices">
            <section class="card">
              <h2>
                Sales prices
                @if (canManage) {
                  <button mat-button (click)="addSalesPrice()">
                    <mat-icon>add</mat-icon>Add
                  </button>
                }
              </h2>
              <table class="plain">
                <thead>
                  <tr>
                    <th>Price list</th>
                    <th>Type</th>
                    <th class="num">From qty</th>
                    <th class="num">Price (₹)</th>
                    <th>Valid</th>
                    <th>Status</th>
                    <th></th>
                  </tr>
                </thead>
                <tbody>
                  @for (p of prices()?.salesPrices ?? []; track p.id) {
                    <tr>
                      <td>{{ p.priceListCode }} · {{ p.priceListName }}</td>
                      <td>
                        {{ p.priceListType
                        }}{{ p.includesTax ? ' (incl. GST)' : '' }}
                      </td>
                      <td class="num">{{ p.minQty | number: '1.0-3' }}</td>
                      <td class="num">{{ p.unitPrice | number: '1.2-2' }}</td>
                      <td class="nowrap">
                        {{ validity(p.validFrom, p.validTo) }}
                      </td>
                      <td>{{ p.isActive ? 'Active' : 'Inactive' }}</td>
                      <td class="actions">
                        @if (canManage) {
                          <button
                            mat-icon-button
                            matTooltip="Change"
                            (click)="editSalesPrice(p)"
                          >
                            <mat-icon>edit</mat-icon>
                          </button>
                        }
                      </td>
                    </tr>
                  } @empty {
                    <tr>
                      <td colspan="7" class="empty">
                        Not on any price list yet.
                      </td>
                    </tr>
                  }
                </tbody>
              </table>
            </section>
            <section class="card">
              <h2>
                Purchase prices
                @if (canManage) {
                  <button mat-button (click)="addPurchasePrice()">
                    <mat-icon>add</mat-icon>Add
                  </button>
                }
              </h2>
              <table class="plain">
                <thead>
                  <tr>
                    <th>Supplier</th>
                    <th>Supplier part no</th>
                    <th class="num">Price (₹)</th>
                    <th>Per</th>
                    <th>Valid</th>
                    <th class="num">Lead time</th>
                    <th>Status</th>
                    <th></th>
                  </tr>
                </thead>
                <tbody>
                  @for (p of prices()?.purchasePrices ?? []; track p.id) {
                    <tr>
                      <td>{{ p.supplierName }}</td>
                      <td>{{ p.supplierPartNo ?? '—' }}</td>
                      <td class="num">{{ p.price | number: '1.2-2' }}</td>
                      <td>
                        {{ p.supplierUom ?? i.uomCode
                        }}{{
                          n0(p.conversionFactor) !== 1
                            ? ' of ' +
                              (p.conversionFactor | number: '1.0-4') +
                              ' ' +
                              i.uomCode
                            : ''
                        }}
                      </td>
                      <td class="nowrap">
                        {{ validity(p.validFrom, p.validTo) }}
                      </td>
                      <td class="num">
                        {{
                          p.leadTimeDays !== null
                            ? p.leadTimeDays + ' days'
                            : '—'
                        }}
                      </td>
                      <td>{{ p.isActive ? 'Active' : 'Inactive' }}</td>
                      <td class="actions">
                        @if (canManage) {
                          <button
                            mat-icon-button
                            matTooltip="Change"
                            (click)="editPurchasePrice(p)"
                          >
                            <mat-icon>edit</mat-icon>
                          </button>
                        }
                      </td>
                    </tr>
                  } @empty {
                    <tr>
                      <td colspan="8" class="empty">No supplier prices yet.</td>
                    </tr>
                  }
                </tbody>
              </table>
            </section>
          </mat-tab>
          <mat-tab label="Unit conversions">
            <section class="card">
              <h2>
                Units this item is bought or counted in
                @if (canManage) {
                  <button mat-button (click)="addConversion()">
                    <mat-icon>add</mat-icon>Add
                  </button>
                }
              </h2>
              <table class="plain">
                <thead>
                  <tr>
                    <th>Conversion</th>
                    <th>Applies to</th>
                    <th>Status</th>
                    <th></th>
                  </tr>
                </thead>
                <tbody>
                  @for (c of conversions(); track c.id) {
                    <tr>
                      <td>
                        1 {{ c.fromUomCode }} = {{ c.factor | number: '1.0-6' }}
                        {{ c.toUomCode }}
                      </td>
                      <td>{{ c.itemId ? 'This item' : 'Every item' }}</td>
                      <td>{{ c.isActive ? 'Active' : 'Inactive' }}</td>
                      <td class="actions">
                        @if (canManage && c.itemId) {
                          <button
                            mat-icon-button
                            matTooltip="Change"
                            (click)="editConversion(c)"
                          >
                            <mat-icon>edit</mat-icon>
                          </button>
                        }
                      </td>
                    </tr>
                  } @empty {
                    <tr>
                      <td colspan="4" class="empty">
                        Only the stock unit ({{ i.uomCode }}).
                      </td>
                    </tr>
                  }
                </tbody>
              </table>
            </section>
          </mat-tab>
        }
      </mat-tab-group>
    } @else {
      <div class="progress"><mat-progress-bar mode="indeterminate" /></div>
    }
  `,
})
export class ItemDetailPage {
  private readonly api = inject(ApiClient);
  private readonly dialog = inject(MatDialog);
  private readonly lookups = inject(InventoryLookups);
  private readonly auth = inject(AuthStore);

  readonly itemId = input.required<string>();

  protected readonly manage = INV_ITEM_MANAGE;
  protected readonly canManage = this.auth.hasPermission(INV_ITEM_MANAGE);
  protected readonly canSeeStock = this.auth.hasAnyPermission(
    INV_STOCK_USER_PERMISSIONS,
  );
  protected readonly canSeeMovements = this.auth.hasPermission(INV_STOCK_VIEW);
  protected readonly canSeePrices = this.auth.hasAnyPermission(
    INV_ITEM_VIEW_PERMISSIONS,
  );
  protected readonly ageClass = ageClass;
  protected readonly n0 = n0;

  protected readonly item = signal<ItemDetail | null>(null);
  protected readonly stock = signal<StockRow[]>([]);
  protected readonly prices = signal<ItemPrices | null>(null);
  protected readonly conversions = signal<ConversionOut[]>([]);
  protected readonly movements = signal<MovementRow[]>([]);
  protected readonly movementTotal = signal(0);
  protected readonly movementPage = signal(1);
  protected readonly movementsLoading = signal(false);

  protected readonly belowReorder = computed(() => {
    const i = this.item();
    return (
      !!i && i.reorderLevel !== null && n0(i.qtyOnHand) <= n0(i.reorderLevel)
    );
  });

  constructor() {
    effect(() => {
      const id = Number(this.itemId());
      untracked(() => this.load(id));
    });
  }

  private get id(): number {
    return Number(this.itemId());
  }

  private load(id: number): void {
    this.api
      .call(getItem, { itemId: id })
      .pipe(catchError(() => EMPTY))
      .subscribe((i) => this.item.set(i));
    if (this.canSeeStock) {
      this.api
        .call(listStock, { itemId: id, pageSize: 200 })
        .pipe(catchError(() => EMPTY))
        .subscribe((page) => this.stock.set(page.items));
    }
    if (this.canSeePrices) {
      this.loadPrices();
      this.loadConversions();
    }
    if (this.canSeeMovements) this.loadMovements();
  }

  private loadPrices(): void {
    this.api
      .call(getItemPrices, { itemId: this.id })
      .pipe(catchError(() => EMPTY))
      .subscribe((p) => this.prices.set(p));
  }

  private loadConversions(): void {
    this.api
      .call(listUomConversions, { itemId: this.id, status: 'all' })
      .pipe(catchError(() => EMPTY))
      .subscribe((rows) => this.conversions.set(rows));
  }

  private loadMovements(): void {
    this.movementsLoading.set(true);
    this.api
      .call(listMovements, {
        itemId: this.id,
        page: this.movementPage(),
        pageSize: 50,
      })
      .pipe(
        finalize(() => this.movementsLoading.set(false)),
        catchError(() => EMPTY),
      )
      .subscribe((page) => {
        this.movements.set(page.items);
        this.movementTotal.set(page.total);
      });
  }

  protected onMovementPage(event: PageEvent): void {
    this.movementPage.set(event.pageIndex + 1);
    this.loadMovements();
  }

  protected money(value: string | null | undefined): string {
    const amount = num(value);
    return amount === null
      ? '—'
      : `₹${amount.toLocaleString('en-IN', { maximumFractionDigits: 2 })}`;
  }

  protected tracking(i: ItemDetail): string {
    const ways = [
      i.isSerialized && 'Serial number',
      i.isBatchTracked && 'Batch',
    ].filter(Boolean);
    return ways.length ? ways.join(', ') : 'Quantity only';
  }

  protected validity(from: string | null, to: string | null): string {
    if (!from && !to) return 'Always';
    return `${from ?? '…'} to ${to ?? '…'}`;
  }

  // ---------------------------------------------------------------- prices

  private priceListOptions(): Observable<{ value: number; label: string }[]> {
    return this.api.call(listPriceLists, { status: 'active' }).pipe(
      map((lists) =>
        lists.map((l) => ({ value: l.id, label: `${l.code} · ${l.name}` })),
      ),
      catchError(() => of([])),
    );
  }

  protected addSalesPrice(): void {
    this.priceListOptions()
      .pipe(
        switchMap((options) =>
          openFieldsDialog(this.dialog, {
            title: 'Add sales price',
            submitText: 'Add',
            fields: [
              {
                key: 'priceListId',
                label: 'Price list',
                type: 'select',
                required: true,
                options,
                wide: true,
                hint: options.length
                  ? undefined
                  : 'Add a price list on the setup screen first.',
              },
              {
                key: 'minQty',
                label: 'From quantity',
                type: 'number',
                required: true,
                min: 0.001,
                hint: 'Price applies from this quantity',
              },
              {
                key: 'unitPrice',
                label: 'Unit price (₹)',
                type: 'number',
                required: true,
                min: 0,
              },
            ],
            value: { minQty: 1 },
            save: (v) =>
              this.api.call(createSalesPrice, {
                itemId: this.id,
                body: v as unknown as SalesPriceCreate,
              }),
          }),
        ),
        filter((saved): saved is ItemPrices => !!saved),
      )
      .subscribe((saved) => this.prices.set(saved));
  }

  protected editSalesPrice(price: SalesPriceOut): void {
    openFieldsDialog(this.dialog, {
      title: `Price on ${price.priceListCode}`,
      submitText: 'Save',
      fields: [
        {
          key: 'minQty',
          label: 'From quantity',
          type: 'number',
          required: true,
          min: 0.001,
        },
        {
          key: 'unitPrice',
          label: 'Unit price (₹)',
          type: 'number',
          required: true,
          min: 0,
        },
        { key: 'isActive', label: 'Active', type: 'checkbox' },
      ],
      value: {
        minQty: num(price.minQty),
        unitPrice: num(price.unitPrice),
        isActive: price.isActive,
      },
      save: (v) =>
        this.api.call(
          updateSalesPrice,
          { priceId: price.id, body: v as SalesPriceUpdate },
          withRowVersion(price.rowVersion),
        ),
    })
      .pipe(filter((saved): saved is ItemPrices => !!saved))
      .subscribe((saved) => this.prices.set(saved));
  }

  private purchaseFields(
    supplierOptions: { value: number; label: string }[] | null,
  ) {
    return [
      ...(supplierOptions
        ? [
            {
              key: 'supplierId',
              label: 'Supplier',
              type: 'select' as const,
              required: true,
              options: supplierOptions,
              wide: true,
            },
          ]
        : []),
      {
        key: 'price',
        label: 'Price (₹)',
        type: 'number' as const,
        required: true,
        min: 0,
        hint: 'Per supplier unit',
      },
      { key: 'supplierPartNo', label: 'Supplier part no', maxLength: 40 },
      {
        key: 'supplierUom',
        label: 'Supplier unit',
        maxLength: 10,
        hint: 'e.g. BOX; blank = stock unit',
      },
      {
        key: 'conversionFactor',
        label: 'Stock units per supplier unit',
        type: 'number' as const,
        required: true,
        min: 0.0001,
      },
      { key: 'validFrom', label: 'Valid from', type: 'date' as const },
      { key: 'validTo', label: 'Valid to', type: 'date' as const },
      {
        key: 'leadTimeDays',
        label: 'Lead time (days)',
        type: 'number' as const,
        min: 0,
        max: 999,
      },
    ];
  }

  protected addPurchasePrice(): void {
    this.lookups
      .suppliers()
      .pipe(
        switchMap((suppliers) =>
          openFieldsDialog(this.dialog, {
            title: 'Add supplier price',
            submitText: 'Add',
            fields: this.purchaseFields(
              suppliers.map((s) => ({
                value: s.id,
                label: `${s.code} · ${s.name}`,
              })),
            ),
            value: { conversionFactor: 1 },
            save: (v) =>
              this.api.call(createPurchasePrice, {
                itemId: this.id,
                body: v as unknown as PurchasePriceCreate,
              }),
          }),
        ),
        filter((saved): saved is ItemPrices => !!saved),
      )
      .subscribe((saved) => this.prices.set(saved));
  }

  protected editPurchasePrice(price: PurchasePriceOut): void {
    openFieldsDialog(this.dialog, {
      title: `Price from ${price.supplierName}`,
      submitText: 'Save',
      fields: [
        ...this.purchaseFields(null),
        { key: 'isActive', label: 'Active', type: 'checkbox' },
      ],
      value: {
        price: num(price.price),
        supplierPartNo: price.supplierPartNo,
        supplierUom: price.supplierUom,
        conversionFactor: num(price.conversionFactor),
        validFrom: price.validFrom,
        validTo: price.validTo,
        leadTimeDays: price.leadTimeDays,
        isActive: price.isActive,
      },
      save: (v) =>
        this.api.call(
          updatePurchasePrice,
          { priceId: price.id, body: v as PurchasePriceUpdate },
          withRowVersion(price.rowVersion),
        ),
    })
      .pipe(filter((saved): saved is ItemPrices => !!saved))
      .subscribe((saved) => this.prices.set(saved));
  }

  // ---------------------------------------------------------------- unit conversions

  protected addConversion(): void {
    const item = this.item();
    if (!item) return;
    this.lookups
      .uoms()
      .pipe(
        switchMap((uoms) =>
          openFieldsDialog(this.dialog, {
            title: `Add a unit for ${item.itemCode}`,
            submitText: 'Add',
            fields: [
              {
                key: 'fromUomId',
                label: 'Unit',
                type: 'select',
                required: true,
                options: uoms
                  .filter((u) => u.id !== item.uomId)
                  .map((u) => ({
                    value: u.id,
                    label: `${u.code} · ${u.name}`,
                  })),
              },
              {
                key: 'factor',
                label: `${item.uomCode} in one unit`,
                type: 'number',
                required: true,
                min: 0.000001,
                hint: `e.g. 10 if a box holds 10 ${item.uomCode}`,
              },
            ],
            save: (v) =>
              this.api.call(createUomConversion, {
                body: {
                  itemId: item.id,
                  fromUomId: v['fromUomId'] as number,
                  toUomId: item.uomId,
                  factor: v['factor'] as number,
                },
              }),
          }),
        ),
        filter((saved) => !!saved),
      )
      .subscribe(() => this.loadConversions());
  }

  protected editConversion(conversion: ConversionOut): void {
    openFieldsDialog(this.dialog, {
      title: `1 ${conversion.fromUomCode} = ? ${conversion.toUomCode}`,
      submitText: 'Save',
      fields: [
        {
          key: 'factor',
          label: `${conversion.toUomCode} in one ${conversion.fromUomCode}`,
          type: 'number',
          required: true,
          min: 0.000001,
        },
        { key: 'isActive', label: 'Active', type: 'checkbox' },
      ],
      value: { factor: num(conversion.factor), isActive: conversion.isActive },
      save: (v) =>
        this.api.call(
          updateUomConversion,
          { conversionId: conversion.id, body: v as ConversionUpdate },
          withRowVersion(conversion.rowVersion),
        ),
    })
      .pipe(filter((saved) => !!saved))
      .subscribe(() => this.loadConversions());
  }
}
