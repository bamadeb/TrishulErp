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
  CreditNoteLineIn,
  ItemListItem,
  OpenInvoice,
  StockRow,
  createCreditNote,
  getSupplierOpenItems,
  listReturnReasons,
  listStock,
} from '@trishul/core-api';
import { AuthStore } from '@trishul/core-auth';
import {
  InventoryLookups,
  ItemPicker,
  isoDate,
  locationLabel,
  n0,
} from '@trishul/inventory-data-access';
import { PageHeader, confirmAction } from '@trishul/shared-ui';
import { EMPTY, catchError, filter, finalize, of, switchMap } from 'rxjs';
import { lineAmounts, rupees } from './purchases.shared';

type NoteType =
  'Purchase return' | 'Damaged goods' | 'Price difference' | 'Other';
const TYPES: NoteType[] = [
  'Purchase return',
  'Damaged goods',
  'Price difference',
  'Other',
];

class NoteLine {
  readonly form = new FormGroup({
    item: new FormControl<ItemListItem | null>(null),
    description: new FormControl<string | null>(
      null,
      Validators.maxLength(200),
    ),
    quantity: new FormControl<number | null>(1, [
      Validators.required,
      Validators.min(0.001),
    ]),
    unitPrice: new FormControl<number | null>(null, [
      Validators.required,
      Validators.min(0),
    ]),
    gstPct: new FormControl<number | null>(18, [
      Validators.required,
      Validators.min(0),
      Validators.max(100),
    ]),
    stockLotId: new FormControl<number | null>(null),
  });
  /** For a return: this item's GRN batches at the location, from this supplier. */
  readonly batches = signal<StockRow[]>([]);
}

/** Record a supplier credit note. A purchase return takes the goods out of stock from their GRN batch. */
@Component({
  selector: 'trishul-credit-note-form-page',
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
    MatDatepicker,
    MatDatepickerInput,
    MatDatepickerToggle,
    MatButton,
    MatIconButton,
    MatIcon,
    MatTooltip,
    ItemPicker,
    PageHeader,
  ],
  providers: [provideNativeDateAdapter()],
  changeDetection: ChangeDetectionStrategy.OnPush,
  styleUrl: '../../../../inventory/data-access/src/lib/inventory.scss',
  template: `
    <trishul-page-header
      title="Record supplier credit note"
      subtitle="Returns, damaged goods, price differences; reduces what we owe the supplier"
    />
    <form [formGroup]="form" (ngSubmit)="save()">
      <section class="card">
        <h2>Credit note</h2>
        <div class="form-grid">
          <mat-form-field appearance="outline">
            <mat-label>Supplier</mat-label>
            <mat-select
              formControlName="supplierId"
              (valueChange)="supplierChanged($event)"
            >
              @for (s of suppliers(); track s.id) {
                <mat-option [value]="s.id"
                  >{{ s.name }} ({{ s.code }})</mat-option
                >
              }
            </mat-select>
            <mat-error>Choose the supplier.</mat-error>
          </mat-form-field>
          <mat-form-field appearance="outline">
            <mat-label>Type</mat-label>
            <mat-select formControlName="noteType">
              @for (t of types; track t) {
                <mat-option [value]="t">{{ t }}</mat-option>
              }
            </mat-select>
            @if (isReturn()) {
              <mat-hint>The goods leave stock when you post</mat-hint>
            }
          </mat-form-field>
          <mat-form-field appearance="outline">
            <mat-label>Branch</mat-label>
            <mat-select formControlName="branchId">
              @for (b of branches(); track b.id) {
                <mat-option [value]="b.id">{{ b.name }}</mat-option>
              }
            </mat-select>
          </mat-form-field>
          <mat-form-field appearance="outline">
            <mat-label>Date</mat-label>
            <input
              matInput
              [matDatepicker]="datePicker"
              formControlName="noteDate"
              [max]="today"
            />
            <mat-datepicker-toggle
              matSuffix
              [for]="datePicker"
            /><mat-datepicker #datePicker />
          </mat-form-field>
          <mat-form-field appearance="outline">
            <mat-label>Supplier's credit note no</mat-label>
            <input matInput formControlName="supplierNoteNo" />
          </mat-form-field>
          <mat-form-field appearance="outline">
            <mat-label>Its date</mat-label>
            <input
              matInput
              [matDatepicker]="notePicker"
              formControlName="supplierNoteDate"
            />
            <mat-datepicker-toggle
              matSuffix
              [for]="notePicker"
            /><mat-datepicker #notePicker />
          </mat-form-field>
          <mat-form-field appearance="outline">
            <mat-label>Against invoice</mat-label>
            <mat-select formControlName="supplierInvoiceId">
              <mat-option [value]="null">None (stays unallocated)</mat-option>
              @for (i of invoices(); track i.id) {
                <mat-option [value]="i.id"
                  >{{ i.invoiceNo }} · {{ i.supplierInvoiceNo }} ·
                  {{ money(i.outstanding) }} due</mat-option
                >
              }
            </mat-select>
            <mat-hint>Set against it automatically</mat-hint>
          </mat-form-field>
          <mat-form-field appearance="outline">
            <mat-label>Reason</mat-label>
            <mat-select formControlName="reasonId">
              <mat-option [value]="null">—</mat-option>
              @for (r of reasons(); track r.id) {
                <mat-option [value]="r.id">{{ r.label }}</mat-option>
              }
            </mat-select>
          </mat-form-field>
          @if (isReturn()) {
            <mat-form-field appearance="outline">
              <mat-label>Returned from</mat-label>
              <mat-select
                formControlName="locationId"
                (valueChange)="reloadBatches()"
              >
                @for (l of locations(); track l.id) {
                  <mat-option [value]="l.id">{{ label(l) }}</mat-option>
                }
              </mat-select>
            </mat-form-field>
          }
          <mat-form-field appearance="outline" class="wide">
            <mat-label>Remarks</mat-label>
            <input matInput formControlName="remarks" />
          </mat-form-field>
        </div>
      </section>

      <section class="card">
        <h2>Lines</h2>
        <div class="lines">
          @for (line of lines(); track line; let i = $index) {
            <div class="line" [formGroup]="line.form">
              <span class="index">{{ i + 1 }}</span>
              <trishul-item-picker
                formControlName="item"
                [label]="isReturn() ? 'Item returned' : 'Item (optional)'"
                [stockOnly]="isReturn()"
                (focusout)="loadBatches(line)"
              />
              @if (isReturn()) {
                <mat-form-field appearance="outline" subscriptSizing="dynamic">
                  <mat-label>GRN batch</mat-label>
                  <mat-select formControlName="stockLotId">
                    <mat-option [value]="null">Oldest first</mat-option>
                    @for (b of line.batches(); track b.lotBalanceId) {
                      <mat-option [value]="b.stockLotId"
                        >{{ b.grnNo }} · {{ b.binCode ?? 'no rack' }} ·
                        {{ n0(b.qtyOnHand) }} left</mat-option
                      >
                    }
                  </mat-select>
                </mat-form-field>
              } @else {
                <mat-form-field appearance="outline" subscriptSizing="dynamic">
                  <mat-label>Description</mat-label>
                  <input matInput formControlName="description" />
                </mat-form-field>
              }
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
                <mat-label>Price (₹)</mat-label>
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
      </section>

      <div class="form-actions">
        <span class="summary">Total {{ money(total()) }}</span>
        <a mat-button routerLink="/purchases/credit-notes">Cancel</a>
        <button mat-flat-button type="submit" [disabled]="saving()">
          Post credit note
        </button>
      </div>
    </form>
  `,
})
export class CreditNoteFormPage {
  private readonly api = inject(ApiClient);
  private readonly router = inject(Router);
  private readonly dialog = inject(MatDialog);
  private readonly lookups = inject(InventoryLookups);
  private readonly auth = inject(AuthStore);

  readonly supplierId = input<string>();

  protected readonly today = new Date();
  protected readonly types = TYPES;
  protected readonly label = locationLabel;
  protected readonly n0 = n0;
  protected readonly money = (v: number | string) => rupees(v);
  protected readonly suppliers = toSignal(this.lookups.suppliers(), {
    initialValue: [],
  });
  protected readonly branches = toSignal(this.lookups.branches(), {
    initialValue: [],
  });
  protected readonly locations = toSignal(this.lookups.locations(), {
    initialValue: [],
  });
  protected readonly reasons = toSignal(
    this.api.call(listReturnReasons).pipe(catchError(() => of([]))),
    {
      initialValue: [],
    },
  );
  protected readonly invoices = signal<OpenInvoice[]>([]);
  protected readonly saving = signal(false);
  private readonly changes = signal(0);

  protected readonly form = new FormGroup({
    supplierId: new FormControl<number | null>(null, Validators.required),
    noteType: new FormControl<NoteType>('Purchase return', {
      nonNullable: true,
    }),
    branchId: new FormControl<number | null>(
      this.auth.branchId(),
      Validators.required,
    ),
    noteDate: new FormControl<Date | null>(new Date(), Validators.required),
    supplierNoteNo: new FormControl<string | null>(
      null,
      Validators.maxLength(40),
    ),
    supplierNoteDate: new FormControl<Date | null>(null),
    supplierInvoiceId: new FormControl<number | null>(null),
    reasonId: new FormControl<number | null>(null),
    locationId: new FormControl<number | null>(null),
    remarks: new FormControl<string | null>(null, Validators.maxLength(300)),
  });
  protected readonly lines = signal<NoteLine[]>([this.watched(new NoteLine())]);
  protected readonly isReturn = computed(() => {
    this.changes();
    return this.form.controls.noteType.value === 'Purchase return';
  });
  protected readonly total = computed(() => {
    this.changes();
    return this.lines().reduce((sum, l) => {
      const v = l.form.getRawValue();
      return sum + lineAmounts(v.quantity, v.unitPrice, 0, v.gstPct).total;
    }, 0);
  });

  constructor() {
    this.form.valueChanges.subscribe(() => this.changes.update((n) => n + 1));
    queueMicrotask(() => {
      const supplier = Number(this.supplierId());
      if (supplier) {
        this.form.controls.supplierId.setValue(supplier);
        this.supplierChanged(supplier);
      }
    });
  }

  private watched(line: NoteLine): NoteLine {
    line.form.valueChanges.subscribe(() => this.changes.update((n) => n + 1));
    return line;
  }

  protected supplierChanged(supplierId: number): void {
    this.form.controls.supplierInvoiceId.setValue(null);
    this.api
      .call(getSupplierOpenItems, { supplierId })
      .pipe(catchError(() => EMPTY))
      .subscribe((items) => this.invoices.set(items.invoices));
    this.reloadBatches();
  }

  protected reloadBatches(): void {
    for (const line of this.lines()) this.loadBatches(line);
  }

  /** The item's batches at the return location that came from this supplier. */
  protected loadBatches(line: NoteLine): void {
    const item = line.form.controls.item.value;
    const locationId = this.form.controls.locationId.value;
    const supplier = this.suppliers().find(
      (s) => s.id === this.form.controls.supplierId.value,
    );
    line.batches.set([]);
    if (!item || !locationId || !this.isReturn()) return;
    if (
      line.form.controls.unitPrice.value === null &&
      item.standardCost !== null
    ) {
      line.form.controls.unitPrice.setValue(Number(item.standardCost));
    }
    this.api
      .call(listStock, { itemId: item.id, locationId, pageSize: 100 })
      .pipe(catchError(() => of({ items: [] as StockRow[] })))
      .subscribe((page) =>
        line.batches.set(
          page.items.filter(
            (b) => !supplier || b.supplierName === supplier.name,
          ),
        ),
      );
  }

  protected addLine(): void {
    this.lines.update((lines) => [...lines, this.watched(new NoteLine())]);
  }

  protected removeLine(index: number): void {
    this.lines.update((lines) => lines.filter((_, i) => i !== index));
  }

  protected save(): void {
    this.form.markAllAsTouched();
    for (const line of this.lines()) line.form.markAllAsTouched();
    const v = this.form.getRawValue();
    const isReturn = v.noteType === 'Purchase return';
    const linesOk = this.lines().every(
      (l) =>
        l.form.valid &&
        (isReturn
          ? !!l.form.controls.item.value
          : !!(
              l.form.controls.item.value || l.form.controls.description.value
            )),
    );
    if (
      this.form.invalid ||
      !linesOk ||
      (isReturn && !v.locationId) ||
      this.saving()
    )
      return;
    const lines: CreditNoteLineIn[] = this.lines().map((l) => {
      const x = l.form.getRawValue();
      return {
        itemId: x.item?.id ?? null,
        description: x.description?.trim() || null,
        quantity: x.quantity as number,
        unitPrice: x.unitPrice as number,
        gstPct: x.gstPct ?? 0,
        stockLotId: isReturn ? x.stockLotId : null,
      };
    });
    confirmAction(this.dialog, {
      title: 'Post this credit note?',
      message: isReturn
        ? `${lines.length} line(s) leave stock now and ${rupees(this.total())} comes off what we owe the supplier.`
        : `${rupees(this.total())} comes off what we owe the supplier.`,
      confirmText: 'Post',
    })
      .pipe(
        filter(Boolean),
        switchMap(() => {
          this.saving.set(true);
          return this.api
            .call(createCreditNote, {
              body: {
                supplierId: v.supplierId as number,
                branchId: v.branchId as number,
                noteType: v.noteType,
                noteDate: isoDate(v.noteDate as Date),
                supplierNoteNo: v.supplierNoteNo?.trim() || null,
                supplierNoteDate: v.supplierNoteDate
                  ? isoDate(v.supplierNoteDate)
                  : null,
                supplierInvoiceId: v.supplierInvoiceId,
                reasonId: v.reasonId,
                locationId: isReturn ? v.locationId : null,
                remarks: v.remarks?.trim() || null,
                lines,
              },
            })
            .pipe(
              finalize(() => this.saving.set(false)),
              catchError(() => EMPTY),
            );
        }),
      )
      .subscribe(
        (note) =>
          void this.router.navigate(['/purchases/credit-notes', note.id]),
      );
  }
}
