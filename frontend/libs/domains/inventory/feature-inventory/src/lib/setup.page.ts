import { DatePipe, DecimalPipe } from '@angular/common';
import {
  ChangeDetectionStrategy,
  Component,
  inject,
  signal,
} from '@angular/core';
import { MatButton, MatIconButton } from '@angular/material/button';
import { MatDialog } from '@angular/material/dialog';
import { MatIcon } from '@angular/material/icon';
import { MatTab, MatTabGroup } from '@angular/material/tabs';
import { MatTooltip } from '@angular/material/tooltip';
import { RouterLink } from '@angular/router';
import {
  ApiClient,
  CategoryCreate,
  CategoryOut,
  CategoryUpdate,
  ConversionCreate,
  ConversionOut,
  ConversionUpdate,
  HsnCreate,
  HsnOut,
  HsnUpdate,
  PriceListCreate,
  PriceListOut,
  PriceListUpdate,
  UomCreate,
  UomOut,
  UomUpdate,
  createHsnCode,
  createItemCategory,
  createPriceList,
  createUom,
  createUomConversion,
  listHsnCodes,
  listItemCategories,
  listPriceLists,
  listUomConversions,
  listUoms,
  updateHsnCode,
  updateItemCategory,
  updatePriceList,
  updateUom,
  updateUomConversion,
  withRowVersion,
} from '@trishul/core-api';
import { AuthStore } from '@trishul/core-auth';
import { PageHeader } from '@trishul/shared-ui';
import { EMPTY, catchError, filter } from 'rxjs';
import { FieldOption, openFieldsDialog } from '@trishul/inventory-data-access';
import { INV_ITEM_MANAGE } from '@trishul/inventory-data-access';
import { InventoryLookups, num } from '@trishul/inventory-data-access';

type ItemCategoryItemNature = NonNullable<CategoryCreate['itemNature']>;
type PriceListPriceListType = NonNullable<PriceListCreate['priceListType']>;

const NATURES: ItemCategoryItemNature[] = [
  'Spare part',
  'Lubricant',
  'Consumable',
  'Attachment',
  'Machine',
  'Service',
];
const PRICE_LIST_TYPES: PriceListPriceListType[] = [
  'Retail',
  'Dealer',
  'Government',
  'Service labour',
];
const CODE = '^[A-Za-z0-9][A-Za-z0-9_./-]*$';

/** Item categories and subcategories, units of measure and conversions, sales price lists. */
@Component({
  selector: 'trishul-inventory-setup-page',
  imports: [
    DatePipe,
    DecimalPipe,
    RouterLink,
    MatButton,
    MatIconButton,
    MatIcon,
    MatTooltip,
    MatTabGroup,
    MatTab,
    PageHeader,
  ],
  changeDetection: ChangeDetectionStrategy.OnPush,
  styleUrl: '../../../data-access/src/lib/inventory.scss',
  styles: `
    .indent {
      display: inline-block;
    }
    h2 {
      display: flex;
      align-items: center;
      justify-content: space-between;
    }
  `,
  template: `
    <trishul-page-header
      title="Item setup"
      subtitle="Categories, units of measure, HSN / SAC codes and sales price lists"
    >
      <a mat-stroked-button routerLink="../items"
        ><mat-icon>inventory_2</mat-icon>Items</a
      >
    </trishul-page-header>

    <mat-tab-group mat-stretch-tabs="false" animationDuration="0ms">
      <mat-tab label="Categories">
        <section class="card">
          <h2>
            Categories and subcategories
            @if (canManage) {
              <button mat-flat-button (click)="editCategory(null)">
                <mat-icon>add</mat-icon>Add category
              </button>
            }
          </h2>
          <table class="plain">
            <thead>
              <tr>
                <th>Category</th>
                <th>Code</th>
                <th>Nature</th>
                <th>Default unit</th>
                <th class="num">Items</th>
                <th>Status</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              @for (c of categories(); track c.id) {
                <tr>
                  <td>
                    <span
                      class="indent"
                      [style.width.rem]="c.level * 1.5"
                    ></span>
                    @if (c.level) {
                      <mat-icon class="muted" inline
                        >subdirectory_arrow_right</mat-icon
                      >
                    }
                    <a
                      class="name"
                      [routerLink]="['../items']"
                      [queryParams]="{ categoryId: c.id }"
                      >{{ c.name }}</a
                    >
                  </td>
                  <td>{{ c.code }}</td>
                  <td>{{ c.itemNature }}</td>
                  <td>{{ c.defaultUomCode ?? '—' }}</td>
                  <td class="num">{{ c.itemCount }}</td>
                  <td>{{ c.isActive ? 'Active' : 'Inactive' }}</td>
                  <td class="actions">
                    @if (canManage) {
                      <button
                        mat-icon-button
                        matTooltip="Add subcategory"
                        (click)="editCategory(null, c)"
                      >
                        <mat-icon>add</mat-icon>
                      </button>
                      <button
                        mat-icon-button
                        matTooltip="Change"
                        (click)="editCategory(c)"
                      >
                        <mat-icon>edit</mat-icon>
                      </button>
                    }
                  </td>
                </tr>
              } @empty {
                <tr>
                  <td colspan="7" class="empty">
                    No categories yet. Add one to start creating items.
                  </td>
                </tr>
              }
            </tbody>
          </table>
        </section>
      </mat-tab>

      <mat-tab label="Units of measure">
        <section class="card">
          <h2>
            Units of measure
            @if (canManage) {
              <button mat-flat-button (click)="editUom(null)">
                <mat-icon>add</mat-icon>Add unit
              </button>
            }
          </h2>
          <table class="plain">
            <thead>
              <tr>
                <th>Code</th>
                <th>Name</th>
                <th class="num">Decimals</th>
                <th>Status</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              @for (u of uoms(); track u.id) {
                <tr>
                  <td>{{ u.code }}</td>
                  <td>{{ u.name }}</td>
                  <td class="num">{{ u.decimals }}</td>
                  <td>{{ u.isActive ? 'Active' : 'Inactive' }}</td>
                  <td class="actions">
                    @if (canManage) {
                      <button
                        mat-icon-button
                        matTooltip="Change"
                        (click)="editUom(u)"
                      >
                        <mat-icon>edit</mat-icon>
                      </button>
                    }
                  </td>
                </tr>
              } @empty {
                <tr>
                  <td colspan="5" class="empty">
                    No units yet (e.g. NOS, KG, LTR, BOX, MTR).
                  </td>
                </tr>
              }
            </tbody>
          </table>
        </section>
        <section class="card">
          <h2>
            Conversions for every item
            @if (canManage) {
              <button mat-button (click)="addConversion()">
                <mat-icon>add</mat-icon>Add conversion
              </button>
            }
          </h2>
          <p class="muted">
            For one item only (e.g. a box of 10), add the conversion on the
            item's page.
          </p>
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
                  <td>
                    {{
                      c.itemCode
                        ? c.itemCode + ' · ' + c.itemDescription
                        : 'Every item'
                    }}
                  </td>
                  <td>{{ c.isActive ? 'Active' : 'Inactive' }}</td>
                  <td class="actions">
                    @if (canManage) {
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
                    No conversions (e.g. 1 KG = 1000 GM).
                  </td>
                </tr>
              }
            </tbody>
          </table>
        </section>
      </mat-tab>

      <mat-tab label="HSN / SAC">
        <section class="card">
          <h2>
            HSN / SAC codes
            @if (canManage) {
              <button mat-flat-button (click)="editHsn(null)">
                <mat-icon>add</mat-icon>Add code
              </button>
            }
          </h2>
          <p class="muted">
            Pick the code on each item (Items → Edit). Quotations, orders and
            invoices print it, and new lines take its GST %.
          </p>
          <table class="plain">
            <thead>
              <tr>
                <th>Code</th>
                <th>Type</th>
                <th>Description</th>
                <th class="num">GST %</th>
                <th class="num">Items</th>
                <th>Status</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              @for (h of hsnCodes(); track h.id) {
                <tr>
                  <td>{{ h.code }}</td>
                  <td>
                    {{ h.codeType === 'SAC' ? 'SAC (service)' : 'HSN (goods)' }}
                  </td>
                  <td>{{ h.description ?? '' }}</td>
                  <td class="num">{{ h.gstPct | number: '1.0-2' }}%</td>
                  <td class="num">{{ h.itemCount }}</td>
                  <td>{{ h.isActive ? 'Active' : 'Inactive' }}</td>
                  <td class="actions">
                    @if (canManage) {
                      <button
                        mat-icon-button
                        matTooltip="Change"
                        (click)="editHsn(h)"
                      >
                        <mat-icon>edit</mat-icon>
                      </button>
                    }
                  </td>
                </tr>
              } @empty {
                <tr>
                  <td colspan="7" class="empty">
                    No HSN / SAC codes yet (e.g. 84212900 filters, 27101980
                    lubricants).
                  </td>
                </tr>
              }
            </tbody>
          </table>
        </section>
      </mat-tab>

      <mat-tab label="Sales price lists">
        <section class="card">
          <h2>
            Price lists
            @if (canManage) {
              <button mat-flat-button (click)="editPriceList(null)">
                <mat-icon>add</mat-icon>Add price list
              </button>
            }
          </h2>
          <p class="muted">
            Item prices are added on each item's Prices tab, with a minimum
            quantity for quantity breaks.
          </p>
          <table class="plain">
            <thead>
              <tr>
                <th>Code</th>
                <th>Name</th>
                <th>Type</th>
                <th>Brand</th>
                <th>GST</th>
                <th>Valid</th>
                <th class="num">Items</th>
                <th>Status</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              @for (p of priceLists(); track p.id) {
                <tr>
                  <td>{{ p.code }}</td>
                  <td>{{ p.name }}</td>
                  <td>{{ p.priceListType }}</td>
                  <td>{{ p.principalCode ?? 'Common' }}</td>
                  <td>{{ p.includesTax ? 'Included' : 'Extra' }}</td>
                  <td class="nowrap">
                    {{
                      p.validFrom ? (p.validFrom | date: 'dd MMM yyyy') : '…'
                    }}
                    – {{ p.validTo ? (p.validTo | date: 'dd MMM yyyy') : '…' }}
                  </td>
                  <td class="num">{{ p.itemCount }}</td>
                  <td>{{ p.isActive ? 'Active' : 'Inactive' }}</td>
                  <td class="actions">
                    @if (canManage) {
                      <button
                        mat-icon-button
                        matTooltip="Change"
                        (click)="editPriceList(p)"
                      >
                        <mat-icon>edit</mat-icon>
                      </button>
                    }
                  </td>
                </tr>
              } @empty {
                <tr>
                  <td colspan="9" class="empty">No price lists yet.</td>
                </tr>
              }
            </tbody>
          </table>
        </section>
      </mat-tab>
    </mat-tab-group>
  `,
})
export class SetupPage {
  private readonly api = inject(ApiClient);
  private readonly dialog = inject(MatDialog);
  private readonly lookups = inject(InventoryLookups);
  protected readonly canManage =
    inject(AuthStore).hasPermission(INV_ITEM_MANAGE);

  protected readonly categories = signal<CategoryOut[]>([]);
  protected readonly uoms = signal<UomOut[]>([]);
  protected readonly conversions = signal<ConversionOut[]>([]);
  protected readonly priceLists = signal<PriceListOut[]>([]);
  protected readonly hsnCodes = signal<HsnOut[]>([]);

  constructor() {
    this.loadCategories();
    this.loadUoms();
    this.loadHsnCodes();
    this.loadConversions();
    this.loadPriceLists();
  }

  private loadCategories(): void {
    this.api
      .call(listItemCategories, { status: 'all' })
      .pipe(catchError(() => EMPTY))
      .subscribe((r) => this.categories.set(r));
  }

  private loadUoms(): void {
    this.api
      .call(listUoms, { status: 'all' })
      .pipe(catchError(() => EMPTY))
      .subscribe((r) => this.uoms.set(r));
  }

  private loadHsnCodes(): void {
    this.api
      .call(listHsnCodes, { status: 'all' })
      .pipe(catchError(() => EMPTY))
      .subscribe((r) => this.hsnCodes.set(r));
  }

  protected editHsn(hsn: HsnOut | null): void {
    openFieldsDialog(this.dialog, {
      title: hsn ? `Change ${hsn.code}` : 'Add HSN / SAC code',
      submitText: hsn ? 'Save' : 'Add',
      fields: [
        ...(hsn
          ? []
          : [
              {
                key: 'code',
                label: 'Code',
                required: true,
                pattern: '^\\d{4,8}$',
                hint: '4, 6 or 8 digits, e.g. 84212900',
              },
            ]),
        {
          key: 'codeType',
          label: 'Type',
          type: 'select' as const,
          required: true,
          options: [
            { value: 'HSN', label: 'HSN (goods)' },
            { value: 'SAC', label: 'SAC (services)' },
          ],
        },
        {
          key: 'gstPct',
          label: 'GST %',
          type: 'number' as const,
          required: true,
          min: 0,
          max: 100,
          hint: 'e.g. 18 (CGST 9 + SGST 9, or IGST 18)',
        },
        {
          key: 'description',
          label: 'Description',
          maxLength: 300,
          wide: true,
        },
        ...(hsn
          ? [{ key: 'isActive', label: 'Active', type: 'checkbox' as const }]
          : []),
      ],
      value: hsn
        ? { ...hsn, gstPct: num(hsn.gstPct) }
        : { codeType: 'HSN', gstPct: 18 },
      save: (v) =>
        hsn
          ? this.api.call(
              updateHsnCode,
              { hsnId: hsn.id, body: v as HsnUpdate },
              withRowVersion(hsn.rowVersion),
            )
          : this.api.call(createHsnCode, { body: v as unknown as HsnCreate }),
    })
      .pipe(filter((saved) => !!saved))
      .subscribe(() => this.loadHsnCodes());
  }

  private loadConversions(): void {
    this.api
      .call(listUomConversions, { status: 'all' })
      .pipe(catchError(() => EMPTY))
      .subscribe((r) => this.conversions.set(r));
  }

  private loadPriceLists(): void {
    this.api
      .call(listPriceLists, { status: 'all' })
      .pipe(catchError(() => EMPTY))
      .subscribe((r) => this.priceLists.set(r));
  }

  private uomOptions(withNone = false): FieldOption[] {
    const options: FieldOption[] = this.uoms()
      .filter((u) => u.isActive)
      .map((u) => ({ value: u.id, label: `${u.code} · ${u.name}` }));
    return withNone ? [{ value: null, label: '—' }, ...options] : options;
  }

  protected editCategory(
    category: CategoryOut | null,
    parent?: CategoryOut,
  ): void {
    const parents: FieldOption[] = [
      { value: null, label: 'None (top category)' },
      ...this.categories()
        .filter((c) => c.isActive && c.id !== category?.id)
        .map((c) => ({ value: c.id, label: c.path })),
    ];
    const fields = [
      ...(category
        ? []
        : [
            {
              key: 'code',
              label: 'Code',
              required: true,
              maxLength: 20,
              pattern: CODE,
            },
          ]),
      { key: 'name', label: 'Name', required: true, maxLength: 100 },
      {
        key: 'parentCategoryId',
        label: 'Under category',
        type: 'select' as const,
        options: parents,
        wide: true,
      },
      {
        key: 'itemNature',
        label: 'Nature',
        type: 'select' as const,
        required: true,
        options: NATURES.map((n) => ({ value: n, label: n })),
      },
      {
        key: 'defaultUomId',
        label: 'Default unit',
        type: 'select' as const,
        options: this.uomOptions(true),
      },
      ...(category
        ? [{ key: 'isActive', label: 'Active', type: 'checkbox' as const }]
        : []),
    ];
    openFieldsDialog(this.dialog, {
      title: category
        ? `Change ${category.name}`
        : parent
          ? `Add subcategory of ${parent.name}`
          : 'Add category',
      submitText: category ? 'Save' : 'Add',
      fields,
      value: category
        ? { ...category }
        : {
            parentCategoryId: parent?.id ?? null,
            itemNature: parent?.itemNature ?? 'Spare part',
            defaultUomId: parent?.defaultUomId ?? null,
          },
      save: (v) =>
        category
          ? this.api.call(
              updateItemCategory,
              { categoryId: category.id, body: v as CategoryUpdate },
              withRowVersion(category.rowVersion),
            )
          : this.api.call(createItemCategory, {
              body: v as unknown as CategoryCreate,
            }),
    })
      .pipe(filter((saved) => !!saved))
      .subscribe(() => this.loadCategories());
  }

  protected editUom(uom: UomOut | null): void {
    openFieldsDialog(this.dialog, {
      title: uom ? `Change ${uom.code}` : 'Add unit',
      submitText: uom ? 'Save' : 'Add',
      fields: [
        ...(uom
          ? []
          : [
              {
                key: 'code',
                label: 'Code',
                required: true,
                maxLength: 10,
                pattern: CODE,
                hint: 'e.g. NOS, KG, LTR',
              },
            ]),
        { key: 'name', label: 'Name', required: true, maxLength: 40 },
        {
          key: 'decimals',
          label: 'Decimal places',
          type: 'number' as const,
          required: true,
          min: 0,
          max: 3,
          hint: '0 for whole numbers',
        },
        ...(uom
          ? [{ key: 'isActive', label: 'Active', type: 'checkbox' as const }]
          : []),
      ],
      value: uom ? { ...uom } : { decimals: 0 },
      save: (v) =>
        uom
          ? this.api.call(
              updateUom,
              { uomId: uom.id, body: v as UomUpdate },
              withRowVersion(uom.rowVersion),
            )
          : this.api.call(createUom, { body: v as unknown as UomCreate }),
    })
      .pipe(filter((saved) => !!saved))
      .subscribe(() => {
        this.lookups.reset();
        this.loadUoms();
      });
  }

  protected addConversion(): void {
    openFieldsDialog(this.dialog, {
      title: 'Add conversion for every item',
      submitText: 'Add',
      fields: [
        {
          key: 'fromUomId',
          label: '1 of this unit',
          type: 'select',
          required: true,
          options: this.uomOptions(),
        },
        {
          key: 'toUomId',
          label: 'equals, in this unit',
          type: 'select',
          required: true,
          options: this.uomOptions(),
        },
        {
          key: 'factor',
          label: 'How many',
          type: 'number',
          required: true,
          min: 0.000001,
          hint: 'e.g. 1000 for 1 KG = 1000 GM',
        },
      ],
      save: (v) =>
        this.api.call(createUomConversion, {
          body: v as unknown as ConversionCreate,
        }),
    })
      .pipe(filter((saved) => !!saved))
      .subscribe(() => this.loadConversions());
  }

  protected editConversion(conversion: ConversionOut): void {
    openFieldsDialog(this.dialog, {
      title: `1 ${conversion.fromUomCode} = ? ${conversion.toUomCode}`,
      submitText: 'Save',
      fields: [
        {
          key: 'factor',
          label: 'How many',
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

  protected editPriceList(list: PriceListOut | null): void {
    openFieldsDialog(this.dialog, {
      title: list ? `Change ${list.code}` : 'Add price list',
      submitText: list ? 'Save' : 'Add',
      fields: [
        ...(list
          ? []
          : [
              {
                key: 'code',
                label: 'Code',
                required: true,
                maxLength: 20,
                pattern: CODE,
              },
            ]),
        { key: 'name', label: 'Name', required: true, maxLength: 80 },
        {
          key: 'priceListType',
          label: 'Type',
          type: 'select' as const,
          required: true,
          options: PRICE_LIST_TYPES.map((t) => ({ value: t, label: t })),
        },
        { key: 'validFrom', label: 'Valid from', type: 'date' as const },
        { key: 'validTo', label: 'Valid to', type: 'date' as const },
        {
          key: 'includesTax',
          label: 'Prices include GST',
          type: 'checkbox' as const,
        },
        ...(list
          ? [{ key: 'isActive', label: 'Active', type: 'checkbox' as const }]
          : []),
      ],
      value: list ? { ...list } : { priceListType: 'Retail' },
      save: (v) =>
        list
          ? this.api.call(
              updatePriceList,
              { priceListId: list.id, body: v as PriceListUpdate },
              withRowVersion(list.rowVersion),
            )
          : this.api.call(createPriceList, {
              body: v as unknown as PriceListCreate,
            }),
    })
      .pipe(filter((saved) => !!saved))
      .subscribe(() => this.loadPriceLists());
  }
}
