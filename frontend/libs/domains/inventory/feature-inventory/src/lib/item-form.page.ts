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
  NonNullableFormBuilder,
  ReactiveFormsModule,
  Validators,
} from '@angular/forms';
import { MatButton } from '@angular/material/button';
import { MatCheckbox } from '@angular/material/checkbox';
import {
  MatError,
  MatFormField,
  MatHint,
  MatLabel,
} from '@angular/material/form-field';
import { MatInput } from '@angular/material/input';
import { MatProgressBar } from '@angular/material/progress-bar';
import { MatOption, MatSelect } from '@angular/material/select';
import { Router, RouterLink } from '@angular/router';
import {
  ApiClient,
  ItemCreate,
  ItemDetail,
  ItemFormOptions,
  createItem,
  getItem,
  getItemFormOptions,
  updateItem,
  withRowVersion,
} from '@trishul/core-api';
import { PageHeader } from '@trishul/shared-ui';
import { EMPTY, catchError, finalize, of } from 'rxjs';
import { num } from './inventory.shared';

type ItemItemType = NonNullable<ItemCreate['itemType']>;

const EMPTY_OPTIONS: ItemFormOptions = {
  categories: [],
  uoms: [],
  principals: [],
  hsnCodes: [],
};

/** Add an item (/inventory/items/new) or change one (/inventory/items/:itemId/edit). */
@Component({
  selector: 'trishul-item-form-page',
  imports: [
    ReactiveFormsModule,
    RouterLink,
    MatFormField,
    MatLabel,
    MatError,
    MatHint,
    MatInput,
    MatSelect,
    MatOption,
    MatCheckbox,
    MatButton,
    MatProgressBar,
    PageHeader,
  ],
  changeDetection: ChangeDetectionStrategy.OnPush,
  styleUrl: './inventory.scss',
  template: `
    <trishul-page-header
      [title]="item() ? 'Edit ' + item()!.itemCode : 'Add item'"
      subtitle="Code, category, stock unit, costs and reorder levels"
    />
    <div class="progress">
      @if (loading()) {
        <mat-progress-bar mode="indeterminate" />
      }
    </div>
    <form [formGroup]="form" (ngSubmit)="save()">
      <section class="card">
        <h2>Item</h2>
        <div class="form-grid">
          <mat-form-field appearance="outline">
            <mat-label>Item code</mat-label>
            <input matInput formControlName="itemCode" autocomplete="off" />
            <mat-hint>Unique; saved in capitals.</mat-hint>
            <mat-error>Required, at most 40 characters.</mat-error>
          </mat-form-field>
          <mat-form-field appearance="outline">
            <mat-label>OEM part number</mat-label>
            <input matInput formControlName="oemPartNumber" />
          </mat-form-field>
          <mat-form-field appearance="outline" class="wide">
            <mat-label>Description</mat-label>
            <input matInput formControlName="description" />
            <mat-error>Required.</mat-error>
          </mat-form-field>
          <mat-form-field appearance="outline" class="wide">
            <mat-label>Long description</mat-label>
            <textarea
              matInput
              rows="2"
              formControlName="longDescription"
            ></textarea>
          </mat-form-field>
          <mat-form-field appearance="outline">
            <mat-label>Category</mat-label>
            <mat-select
              formControlName="categoryId"
              (valueChange)="categoryChanged($event)"
            >
              @for (c of options().categories; track c.id) {
                <mat-option [value]="c.id">{{ c.path }}</mat-option>
              }
            </mat-select>
            <mat-error>Choose a category.</mat-error>
          </mat-form-field>
          <mat-form-field appearance="outline">
            <mat-label>Stock unit</mat-label>
            <mat-select formControlName="uomId">
              @for (u of options().uoms; track u.id) {
                <mat-option [value]="u.id"
                  >{{ u.code }} · {{ u.name }}</mat-option
                >
              }
            </mat-select>
            @if (item()) {
              <mat-hint>Can't change once the item has stock.</mat-hint>
            }
            <mat-error>Choose the unit stock is kept in.</mat-error>
          </mat-form-field>
          <mat-form-field appearance="outline">
            <mat-label>Type</mat-label>
            <mat-select formControlName="itemType">
              @for (t of itemTypes; track t) {
                <mat-option [value]="t">{{ t }}</mat-option>
              }
            </mat-select>
            <mat-hint>Only stock items are received and transferred.</mat-hint>
          </mat-form-field>
          <mat-form-field appearance="outline">
            <mat-label>Brand</mat-label>
            <mat-select formControlName="principalId">
              <mat-option [value]="null">Common item (no brand)</mat-option>
              @for (p of options().principals; track p.id) {
                <mat-option [value]="p.id">{{ p.name }}</mat-option>
              }
            </mat-select>
          </mat-form-field>
          <mat-form-field appearance="outline">
            <mat-label>HSN / SAC</mat-label>
            <mat-select formControlName="hsnSacId">
              <mat-option [value]="null">—</mat-option>
              @for (h of options().hsnCodes; track h.id) {
                <mat-option [value]="h.id"
                  >{{ h.code }} {{ h.description }}</mat-option
                >
              }
            </mat-select>
          </mat-form-field>
          <div class="wide">
            <mat-checkbox formControlName="isSerialized"
              >Tracked by serial number</mat-checkbox
            >
            <mat-checkbox formControlName="isBatchTracked"
              >Tracked by batch</mat-checkbox
            >
            @if (item()) {
              <mat-checkbox formControlName="isActive">Active</mat-checkbox>
            }
          </div>
        </div>
      </section>

      <section class="card">
        <h2>Costs and reorder</h2>
        <div class="form-grid">
          <mat-form-field appearance="outline">
            <mat-label>Standard cost (₹)</mat-label>
            <input
              matInput
              type="number"
              min="0"
              step="0.01"
              formControlName="standardCost"
            />
            <mat-hint>For valuation and reports</mat-hint>
          </mat-form-field>
          <mat-form-field appearance="outline">
            <mat-label>MRP (₹)</mat-label>
            <input
              matInput
              type="number"
              min="0"
              step="0.01"
              formControlName="mrp"
            />
          </mat-form-field>
          <mat-form-field appearance="outline">
            <mat-label>Reorder level</mat-label>
            <input
              matInput
              type="number"
              min="0"
              formControlName="reorderLevel"
            />
          </mat-form-field>
          <mat-form-field appearance="outline">
            <mat-label>Reorder quantity</mat-label>
            <input
              matInput
              type="number"
              min="0"
              formControlName="reorderQty"
            />
          </mat-form-field>
          <mat-form-field appearance="outline">
            <mat-label>Lead time (days)</mat-label>
            <input
              matInput
              type="number"
              min="0"
              max="999"
              formControlName="leadTimeDays"
            />
          </mat-form-field>
        </div>
      </section>

      <div class="form-actions">
        <a mat-button [routerLink]="item() ? ['..'] : ['..']">Cancel</a>
        <button mat-flat-button type="submit" [disabled]="saving()">
          {{ item() ? 'Save' : 'Add item' }}
        </button>
      </div>
    </form>
  `,
})
export class ItemFormPage {
  private readonly api = inject(ApiClient);
  private readonly router = inject(Router);
  private readonly fb = inject(NonNullableFormBuilder);

  /** Route parameter on the edit route. */
  readonly itemId = input<string>();

  protected readonly itemTypes: ItemItemType[] = [
    'Stock',
    'Non stock',
    'Service',
  ];
  protected readonly item = signal<ItemDetail | null>(null);
  protected readonly loading = signal(false);
  protected readonly saving = signal(false);
  protected readonly options = toSignal(
    this.api.call(getItemFormOptions).pipe(catchError(() => of(EMPTY_OPTIONS))),
    { initialValue: EMPTY_OPTIONS },
  );

  protected readonly form = this.fb.group({
    itemCode: this.fb.control('', [
      Validators.required,
      Validators.maxLength(40),
    ]),
    description: this.fb.control('', [
      Validators.required,
      Validators.maxLength(200),
    ]),
    longDescription: new FormControl<string | null>(
      null,
      Validators.maxLength(1000),
    ),
    oemPartNumber: new FormControl<string | null>(
      null,
      Validators.maxLength(40),
    ),
    categoryId: new FormControl<number | null>(null, Validators.required),
    uomId: new FormControl<number | null>(null, Validators.required),
    itemType: this.fb.control<ItemItemType>('Stock'),
    principalId: new FormControl<number | null>(null),
    hsnSacId: new FormControl<number | null>(null),
    isSerialized: this.fb.control(false),
    isBatchTracked: this.fb.control(false),
    isActive: this.fb.control(true),
    standardCost: new FormControl<number | null>(null, Validators.min(0)),
    mrp: new FormControl<number | null>(null, Validators.min(0)),
    reorderLevel: new FormControl<number | null>(null, Validators.min(0)),
    reorderQty: new FormControl<number | null>(null, Validators.min(0)),
    leadTimeDays: new FormControl<number | null>(null, [
      Validators.min(0),
      Validators.max(999),
    ]),
  });

  constructor() {
    effect(() => {
      const id = Number(this.itemId());
      if (!id) return;
      untracked(() => this.load(id));
    });
  }

  private load(id: number): void {
    this.loading.set(true);
    this.api
      .call(getItem, { itemId: id })
      .pipe(
        finalize(() => this.loading.set(false)),
        catchError(() => EMPTY),
      )
      .subscribe((item) => {
        this.item.set(item);
        this.form.reset({
          itemCode: item.itemCode,
          description: item.description,
          longDescription: item.longDescription,
          oemPartNumber: item.oemPartNumber,
          categoryId: item.categoryId,
          uomId: item.uomId,
          itemType: item.itemType,
          principalId: item.principalId,
          hsnSacId: item.hsnSacId,
          isSerialized: item.isSerialized,
          isBatchTracked: item.isBatchTracked,
          isActive: item.isActive,
          standardCost: num(item.standardCost),
          mrp: num(item.mrp),
          reorderLevel: num(item.reorderLevel),
          reorderQty: num(item.reorderQty),
          leadTimeDays: item.leadTimeDays,
        });
      });
  }

  /** A new item takes its category's default unit. */
  protected categoryChanged(categoryId: number): void {
    if (this.item() || this.form.controls.uomId.value) return;
    const category = this.options().categories.find((c) => c.id === categoryId);
    if (category?.defaultUomId)
      this.form.controls.uomId.setValue(category.defaultUomId);
  }

  protected save(): void {
    this.form.markAllAsTouched();
    if (this.form.invalid || this.saving()) return;
    const v = this.form.getRawValue();
    const body = {
      itemCode: v.itemCode.trim(),
      description: v.description.trim(),
      longDescription: v.longDescription?.trim() || null,
      oemPartNumber: v.oemPartNumber?.trim() || null,
      categoryId: v.categoryId as number,
      uomId: v.uomId as number,
      itemType: v.itemType,
      principalId: v.principalId,
      hsnSacId: v.hsnSacId,
      isSerialized: v.isSerialized,
      isBatchTracked: v.isBatchTracked,
      standardCost: v.standardCost,
      mrp: v.mrp,
      reorderLevel: v.reorderLevel,
      reorderQty: v.reorderQty,
      leadTimeDays: v.leadTimeDays,
    };
    const existing = this.item();
    this.saving.set(true);
    const request = existing
      ? this.api.call(
          updateItem,
          { itemId: existing.id, body: { ...body, isActive: v.isActive } },
          withRowVersion(existing.rowVersion),
        )
      : this.api.call(createItem, { body });
    request
      .pipe(
        finalize(() => this.saving.set(false)),
        catchError(() => EMPTY),
      )
      .subscribe(
        (saved) => void this.router.navigate(['/inventory/items', saved.id]),
      );
  }
}
