import { DatePipe, DecimalPipe } from '@angular/common';
import {
  ChangeDetectionStrategy,
  Component,
  inject,
  signal,
} from '@angular/core';
import { toSignal } from '@angular/core/rxjs-interop';
import {
  FormControl,
  FormGroup,
  ReactiveFormsModule,
  Validators,
} from '@angular/forms';
import { MatButton, MatIconButton } from '@angular/material/button';
import { provideNativeDateAdapter } from '@angular/material/core';
import {
  MatDatepicker,
  MatDatepickerInput,
  MatDatepickerToggle,
} from '@angular/material/datepicker';
import { MatDialog } from '@angular/material/dialog';
import {
  MatError,
  MatFormField,
  MatLabel,
  MatSuffix,
} from '@angular/material/form-field';
import { MatIcon } from '@angular/material/icon';
import { MatInput } from '@angular/material/input';
import { MatPaginator, PageEvent } from '@angular/material/paginator';
import { MatOption, MatSelect } from '@angular/material/select';
import { MatTooltip } from '@angular/material/tooltip';
import { RouterLink } from '@angular/router';
import {
  ApiClient,
  ItemListItem,
  ListLots$Params,
  OpeningLineIn,
  RackOut,
  createOpeningStock,
  listLots,
} from '@trishul/core-api';
import { AuthStore } from '@trishul/core-auth';
import { PageHeader, confirmAction } from '@trishul/shared-ui';
import { EMPTY, catchError, filter, finalize, switchMap } from 'rxjs';
import { ItemPicker } from '@trishul/inventory-data-access';
import { INV_GRN_MANAGE } from '@trishul/inventory-data-access';
import {
  InventoryLookups,
  ageClass,
  isoDate,
  locationLabel,
  pagedList,
} from '@trishul/inventory-data-access';

function openingLine() {
  return new FormGroup({
    item: new FormControl<ItemListItem | null>(null, Validators.required),
    quantity: new FormControl<number | null>(null, [
      Validators.required,
      Validators.min(0.001),
    ]),
    unitCost: new FormControl<number | null>(null, [
      Validators.required,
      Validators.min(0),
    ]),
    binId: new FormControl<number | null>(null),
    grnNo: new FormControl<string | null>(null, [
      Validators.required,
      Validators.maxLength(30),
    ]),
    grnDate: new FormControl<Date | null>(null, Validators.required),
    supplierId: new FormControl<number | null>(null),
  });
}

/**
 * Stock already on hand at go-live. Each line keeps the original GRN number and date so its age is
 * right from the first day, and the batches entered so far are listed below.
 */
@Component({
  selector: 'trishul-opening-stock-page',
  imports: [
    DatePipe,
    DecimalPipe,
    ReactiveFormsModule,
    RouterLink,
    MatFormField,
    MatLabel,
    MatError,
    MatSuffix,
    MatInput,
    MatSelect,
    MatOption,
    MatDatepicker,
    MatDatepickerInput,
    MatDatepickerToggle,
    MatButton,
    MatIconButton,
    MatIcon,
    MatTooltip,
    MatPaginator,
    ItemPicker,
    PageHeader,
  ],
  providers: [provideNativeDateAdapter()],
  changeDetection: ChangeDetectionStrategy.OnPush,
  styleUrl: '../../../data-access/src/lib/inventory.scss',
  template: `
    <trishul-page-header
      title="Opening stock"
      subtitle="Stock on hand at go-live, entered with its original GRN number and date"
    />

    @if (canEnter) {
      <form [formGroup]="form" (ngSubmit)="post()">
        <section class="card">
          <h2>Enter stock</h2>
          <div class="form-grid">
            <mat-form-field appearance="outline">
              <mat-label>Location</mat-label>
              <mat-select formControlName="locationId">
                @for (l of locations(); track l.id) {
                  <mat-option [value]="l.id">{{ label(l) }}</mat-option>
                }
              </mat-select>
              <mat-error>Choose the location.</mat-error>
            </mat-form-field>
          </div>
          <div class="lines">
            @for (line of lines(); track line; let i = $index) {
              <div class="line" [formGroup]="line">
                <span class="index">{{ i + 1 }}</span>
                <trishul-item-picker formControlName="item" />
                <mat-form-field appearance="outline" subscriptSizing="dynamic">
                  <mat-label>Quantity</mat-label>
                  <input
                    matInput
                    type="number"
                    min="0"
                    formControlName="quantity"
                  />
                </mat-form-field>
                <mat-form-field appearance="outline" subscriptSizing="dynamic">
                  <mat-label>Cost / unit (₹)</mat-label>
                  <input
                    matInput
                    type="number"
                    min="0"
                    formControlName="unitCost"
                  />
                </mat-form-field>
                <mat-form-field appearance="outline" subscriptSizing="dynamic">
                  <mat-label>Original GRN no</mat-label>
                  <input matInput formControlName="grnNo" />
                </mat-form-field>
                <mat-form-field appearance="outline" subscriptSizing="dynamic">
                  <mat-label>GRN date</mat-label>
                  <input
                    matInput
                    [matDatepicker]="picker"
                    formControlName="grnDate"
                    [max]="today"
                  />
                  <mat-datepicker-toggle matSuffix [for]="picker" />
                  <mat-datepicker #picker />
                </mat-form-field>
                <mat-form-field appearance="outline" subscriptSizing="dynamic">
                  <mat-label>Rack</mat-label>
                  <mat-select formControlName="binId">
                    <mat-option [value]="null">No rack</mat-option>
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
                  [disabled]="lines().length === 1"
                  (click)="removeLine(i)"
                >
                  <mat-icon>delete</mat-icon>
                </button>
              </div>
            }
          </div>
          <button mat-button type="button" (click)="addLine()">
            <mat-icon>add</mat-icon>Add line
          </button>
          <div class="form-actions">
            <span class="summary">{{ lines().length }} line(s)</span>
            <button mat-flat-button type="submit" [disabled]="saving()">
              Post opening stock
            </button>
          </div>
        </section>
      </form>
    }

    <section class="card">
      <h2>Opening stock entered</h2>
      <table class="plain wide">
        <thead>
          <tr>
            <th>Item</th>
            <th>GRN no</th>
            <th>GRN date</th>
            <th>Age</th>
            <th>Location</th>
            <th class="num">Entered</th>
            <th class="num">Left</th>
            <th class="num">Cost</th>
            <th class="num">Value left</th>
          </tr>
        </thead>
        <tbody>
          @for (lot of entered.items(); track lot.id) {
            <tr>
              <td>
                <a class="name" [routerLink]="['../items', lot.itemId]">{{
                  lot.itemCode
                }}</a>
                <div class="muted">{{ lot.itemDescription }}</div>
              </td>
              <td>
                {{ lot.grnNo }}
                <div class="muted">{{ lot.lotNo }}</div>
              </td>
              <td class="nowrap">{{ lot.grnDate | date: 'dd MMM yyyy' }}</td>
              <td>
                <span [class]="'age ' + ageClass(lot.ageDays)"
                  >{{ lot.ageDays }} days</span
                >
              </td>
              <td>
                {{ lot.receivedBranchName }}
                <div class="muted">{{ lot.receivedLocationName }}</div>
              </td>
              <td class="num">
                {{ lot.qtyReceived | number: '1.0-3' }} {{ lot.uomCode }}
              </td>
              <td class="num">{{ lot.qtyOnHand | number: '1.0-3' }}</td>
              <td class="num">{{ lot.unitCost | number: '1.2-2' }}</td>
              <td class="num">{{ lot.valueOnHand | number: '1.2-2' }}</td>
            </tr>
          } @empty {
            <tr>
              <td colspan="9" class="empty">No opening stock entered yet.</td>
            </tr>
          }
        </tbody>
      </table>
      <mat-paginator
        [length]="entered.total()"
        [pageIndex]="(lotQuery().page ?? 1) - 1"
        [pageSize]="lotQuery().pageSize"
        [hidePageSize]="true"
        aria-label="Pages of opening stock"
        (page)="onPage($event)"
      />
    </section>
  `,
})
export class OpeningStockPage {
  private readonly api = inject(ApiClient);
  private readonly dialog = inject(MatDialog);
  private readonly lookups = inject(InventoryLookups);
  protected readonly canEnter = inject(AuthStore).hasPermission(INV_GRN_MANAGE);

  protected readonly today = new Date();
  protected readonly label = locationLabel;
  protected readonly ageClass = ageClass;
  protected readonly locations = toSignal(this.lookups.locations(), {
    initialValue: [],
  });
  protected readonly racks = signal<RackOut[]>([]);
  protected readonly saving = signal(false);
  protected readonly form = new FormGroup({
    locationId: new FormControl<number | null>(null, Validators.required),
  });
  protected readonly lines = signal([openingLine()]);

  protected readonly lotQuery = signal<ListLots$Params>({
    sourceType: 'Opening',
    page: 1,
    pageSize: 50,
  });
  protected readonly entered = pagedList(this.lotQuery, (q) =>
    this.api.call(listLots, q),
  );

  constructor() {
    this.form.controls.locationId.valueChanges.subscribe((id) => {
      this.lookups.racks(id).subscribe((racks) => this.racks.set(racks));
      for (const line of this.lines()) line.controls.binId.setValue(null);
    });
  }

  protected addLine(): void {
    // A new line repeats the previous GRN no and date: opening stock is usually entered GRN by GRN.
    const last = this.lines().at(-1)?.getRawValue();
    const line = openingLine();
    line.patchValue({
      grnNo: last?.grnNo ?? null,
      grnDate: last?.grnDate ?? null,
      binId: last?.binId ?? null,
    });
    this.lines.update((lines) => [...lines, line]);
  }

  protected removeLine(index: number): void {
    this.lines.update((lines) => lines.filter((_, i) => i !== index));
  }

  protected onPage(event: PageEvent): void {
    this.lotQuery.update((q) => ({ ...q, page: event.pageIndex + 1 }));
  }

  protected post(): void {
    this.form.markAllAsTouched();
    for (const line of this.lines()) line.markAllAsTouched();
    if (
      this.form.invalid ||
      this.lines().some((l) => l.invalid) ||
      this.saving()
    )
      return;
    const lines: OpeningLineIn[] = this.lines().map((l) => {
      const x = l.getRawValue();
      return {
        itemId: (x.item as ItemListItem).id,
        quantity: x.quantity as number,
        unitCost: x.unitCost as number,
        binId: x.binId,
        grnNo: (x.grnNo as string).trim(),
        grnDate: isoDate(x.grnDate as Date),
        supplierId: x.supplierId,
      };
    });
    confirmAction(this.dialog, {
      title: 'Post opening stock?',
      message: `${lines.length} batch(es) will be added to stock, each aged from its original GRN date.`,
      confirmText: 'Post',
    })
      .pipe(
        filter(Boolean),
        switchMap(() => {
          this.saving.set(true);
          return this.api
            .call(createOpeningStock, {
              body: {
                locationId: this.form.getRawValue().locationId as number,
                lines,
              },
            })
            .pipe(
              finalize(() => this.saving.set(false)),
              catchError(() => EMPTY),
            );
        }),
      )
      .subscribe(() => {
        this.lines.set([openingLine()]);
        this.entered.reload();
      });
  }
}
