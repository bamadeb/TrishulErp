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
import { MatInput } from '@angular/material/input';
import { MatOption, MatSelect } from '@angular/material/select';
import { MatSnackBar } from '@angular/material/snack-bar';
import { Router, RouterLink } from '@angular/router';
import {
  ApiClient,
  CustomerBranchOut,
  ItemListItem,
  PartRequestQuotationDraft,
  QuotationCreate,
  QuotationDetail,
  createPartRequestQuotation,
  createQuotation,
  getCustomerAccount,
  getItem,
  getPartRequestQuotationDraft,
  getQuotation,
  listCustomerBranches,
  updateQuotation,
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
import {
  EMPTY,
  Observable,
  catchError,
  finalize,
  forkJoin,
  map,
  of,
} from 'rxjs';
import { SaleLines } from './sale-lines';
import {
  SaleLineForm,
  rupees,
  saleLine,
  saleLineBody,
  saleLinesTotals,
  saleLinesValid,
} from './sales.shared';

type QuotationType = NonNullable<QuotationCreate['quotationType']>;

/** New quotation, or change a draft (/sales/quotations/:quotationId/edit). Saved as a draft. */
@Component({
  selector: 'trishul-quotation-form-page',
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
    CustomerPicker,
    PageHeader,
    SaleLines,
  ],
  providers: [provideNativeDateAdapter()],
  changeDetection: ChangeDetectionStrategy.OnPush,
  styleUrl: '../../../../inventory/data-access/src/lib/inventory.scss',
  template: `
    <trishul-page-header
      [title]="
        existing()
          ? 'Edit ' +
            existing()!.quotationNo +
            ' (version ' +
            existing()!.currentVersion +
            ')'
          : 'New quotation'
      "
      subtitle="Saved as a draft; submit it to the customer from the quotation page"
    />
    @if (fromParts(); as d) {
      <p class="muted" role="status">
        Filled in from {{ d.partRequestIds.length }} part{{
          d.partRequestIds.length === 1 ? '' : 's'
        }}
        requested on {{ d.callNos.join(', ') }}. Check the prices, then save:
        the parts are marked Quoted only when you save. A part line you remove
        stays waiting on the parts requests page.
      </p>
    }
    <form [formGroup]="form" (ngSubmit)="save()">
      <section class="card">
        <h2>Quotation</h2>
        <div class="form-grid">
          <trishul-customer-picker formControlName="customer" />
          <mat-form-field appearance="outline">
            <mat-label>Customer branch</mat-label>
            <mat-select formControlName="customerSiteId">
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
            <mat-label>Branch</mat-label>
            <mat-select formControlName="branchId">
              @for (b of options().branches; track b.id) {
                <mat-option [value]="b.id">{{ b.name }}</mat-option>
              }
            </mat-select>
            <mat-hint>The quotation number comes from this branch</mat-hint>
            <mat-error>Choose the branch.</mat-error>
          </mat-form-field>
          <mat-form-field appearance="outline">
            <mat-label>Type</mat-label>
            <mat-select formControlName="quotationType">
              <mat-option value="Parts">Parts</mat-option>
              <mat-option value="Machine">Machine</mat-option>
              <mat-option value="Service">Service</mat-option>
            </mat-select>
          </mat-form-field>
          <mat-form-field appearance="outline">
            <mat-label>Quotation date</mat-label>
            <input
              matInput
              [matDatepicker]="datePicker"
              formControlName="quotationDate"
            />
            <mat-datepicker-toggle
              matSuffix
              [for]="datePicker"
            /><mat-datepicker #datePicker />
          </mat-form-field>
          <mat-form-field appearance="outline">
            <mat-label>Valid until</mat-label>
            <input
              matInput
              [matDatepicker]="validPicker"
              formControlName="validUntil"
            />
            <mat-datepicker-toggle
              matSuffix
              [for]="validPicker"
            /><mat-datepicker #validPicker />
            <mat-hint>Blank: 30 days</mat-hint>
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
          <mat-form-field appearance="outline" class="wide">
            <mat-label>Terms and conditions</mat-label>
            <textarea matInput rows="3" formControlName="terms"></textarea>
          </mat-form-field>
          <mat-form-field appearance="outline" class="wide">
            <mat-label>Internal remarks</mat-label>
            <input matInput formControlName="remarks" />
          </mat-form-field>
        </div>
      </section>

      <section class="card">
        <h2>Items</h2>
        <trishul-sale-lines
          [(lines)]="lines"
          [allowText]="true"
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
            existing()
              ? ['/sales/quotations', existing()!.id]
              : fromParts()
                ? ['/sales/part-requests']
                : ['/sales/quotations']
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
export class QuotationFormPage {
  private readonly api = inject(ApiClient);
  private readonly router = inject(Router);
  private readonly auth = inject(AuthStore);
  private readonly snackBar = inject(MatSnackBar);

  readonly quotationId = input<string>();
  /** ?customerId=… from a customer page. */
  readonly customerId = input<string>();
  /** ?partRequests=1,2,3 from the parts requests page: filled in from those parts. */
  readonly partRequests = input<string>();

  /** The parts this quotation is for (they become Quoted when it is saved). */
  protected readonly fromParts = signal<PartRequestQuotationDraft | null>(null);
  /** The requested part each prefilled line is for: a line removed here leaves its part waiting. */
  private readonly partOf = new WeakMap<SaleLineForm, number>();

  protected readonly money = (v: number) => rupees(v);
  protected readonly options = toSignal(inject(SalesLookups).options(), {
    initialValue: NO_SALES_OPTIONS,
  });
  protected readonly existing = signal<QuotationDetail | null>(null);
  protected readonly sites = signal<CustomerBranchOut[]>([]);
  protected readonly saving = signal(false);
  private readonly changes = signal(0);

  protected readonly form = new FormGroup({
    customer: new FormControl<PickedCustomer | null>(null, Validators.required),
    customerSiteId: new FormControl<number | null>(null),
    principalId: new FormControl<number | null>(null, Validators.required),
    branchId: new FormControl<number | null>(null, Validators.required),
    quotationType: new FormControl<QuotationType>('Parts', {
      nonNullable: true,
    }),
    quotationDate: new FormControl<Date | null>(new Date()),
    validUntil: new FormControl<Date | null>(null),
    otherCharges: new FormControl<number | null>(0, Validators.min(0)),
    terms: new FormControl<string | null>(null, Validators.maxLength(2000)),
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
      const id = Number(this.quotationId());
      if (id) untracked(() => this.load(id));
    });
    effect(() => {
      const customer = Number(this.customerId());
      if (customer && !this.quotationId())
        untracked(() =>
          this.api
            .call(getCustomerAccount, { customerId: customer })
            .pipe(catchError(() => EMPTY))
            .subscribe((c) => this.form.controls.customer.setValue(c)),
        );
    });
    effect(() => {
      const ids = (this.partRequests() ?? '')
        .split(',')
        .map(Number)
        .filter((n) => n > 0);
      if (ids.length && !this.quotationId())
        untracked(() => this.loadParts(ids));
    });
  }

  private loadParts(ids: number[]): void {
    this.api
      .call(getPartRequestQuotationDraft, { partRequestIds: ids })
      .pipe(catchError(() => EMPTY))
      .subscribe((d) => {
        this.fromParts.set(d);
        this.api
          .call(getCustomerAccount, { customerId: d.customerId })
          .pipe(catchError(() => EMPTY))
          // customerChanged() loads the customer's branches (and picks the default one).
          .subscribe((c) => this.form.controls.customer.setValue(c));
        this.form.patchValue({
          principalId: d.principalId,
          branchId: d.branchId,
          quotationType: 'Parts',
          remarks: d.remarks,
        });
        // The parts are for this customer and brand.
        this.form.controls.customer.disable();
        this.form.controls.principalId.disable();
        this.setLines(d.lines);
      });
  }

  /** Lines with their items loaded (the line editor shows the picked item). */
  private setLines(
    lines: {
      partRequestId?: number;
      itemId?: number | null;
      description?: string | null;
      quantity: string | number;
      unitPrice: string | number;
      discountPct: string | number;
      gstPct: string | number;
    }[],
  ): void {
    forkJoin(
      lines.map((l) =>
        l.itemId
          ? this.api
              .call(getItem, { itemId: l.itemId })
              .pipe(catchError(() => of(null)))
          : of(null),
      ),
    ).subscribe((items) => {
      this.lines.set(
        lines.map((l, i) => {
          const line = this.watched(saleLine());
          line.patchValue({
            item: items[i] as unknown as ItemListItem | null,
            description: l.description ?? null,
            quantity: num(l.quantity),
            unitPrice: num(l.unitPrice),
            discountPct: num(l.discountPct),
            gstPct: num(l.gstPct),
          });
          if (l.partRequestId) this.partOf.set(line, l.partRequestId);
          return line;
        }),
      );
    });
  }

  private load(id: number): void {
    this.api
      .call(getQuotation, { quotationId: id })
      .pipe(catchError(() => EMPTY))
      .subscribe((q) => {
        this.existing.set(q);
        this.api
          .call(getCustomerAccount, { customerId: q.customerId })
          .pipe(catchError(() => EMPTY))
          .subscribe((c) => {
            this.lastCustomer = c.id; // keep the saved branch: don't reset it as a new pick
            this.form.controls.customer.setValue(c);
            this.loadSites(c.id, q.customerSiteId);
          });
        this.form.patchValue({
          principalId: q.principalId,
          branchId: q.branchId,
          quotationType: q.quotationType,
          quotationDate: fromIso(q.quotationDate),
          validUntil: fromIso(q.validUntil),
          otherCharges: num(q.otherCharges),
          terms: q.terms,
          remarks: q.remarks,
        });
        this.form.controls.branchId.disable();
        this.setLines(q.lines);
      });
  }

  protected customerChanged(): void {
    const customer = this.form.controls.customer.value;
    if ((customer?.id ?? null) === this.lastCustomer) return;
    this.lastCustomer = customer?.id ?? null;
    this.form.controls.customerSiteId.setValue(null);
    this.sites.set([]);
    if (customer) this.loadSites(customer.id, null);
  }

  private loadSites(customerId: number, selected: number | null): void {
    this.lastCustomer = customerId;
    this.api
      .call(listCustomerBranches, { customerId })
      .pipe(catchError(() => of([] as CustomerBranchOut[])))
      .subscribe((sites) => {
        this.sites.set(sites);
        const chosen = selected ?? sites.find((s) => s.isDefault)?.id ?? null;
        this.form.controls.customerSiteId.setValue(chosen);
      });
  }

  protected save(): void {
    this.form.markAllAsTouched();
    for (const line of this.lines()) line.markAllAsTouched();
    if (
      this.form.invalid ||
      !saleLinesValid(this.lines(), true) ||
      this.saving()
    )
      return;
    const v = this.form.getRawValue();
    const body: QuotationCreate = {
      customerId: (v.customer as PickedCustomer).id,
      customerSiteId: v.customerSiteId,
      principalId: v.principalId as number,
      branchId: v.branchId as number,
      quotationType: v.quotationType,
      quotationDate: v.quotationDate ? isoDate(v.quotationDate) : null,
      validUntil: v.validUntil ? isoDate(v.validUntil) : null,
      otherCharges: v.otherCharges ?? 0,
      terms: v.terms?.trim() || null,
      remarks: v.remarks?.trim() || null,
      lines: this.lines().map(saleLineBody),
    };
    const existing = this.existing();
    const parts = this.fromParts();
    const partIds = this.lines()
      .map((l) => this.partOf.get(l))
      .filter((id): id is number => id !== undefined);
    if (parts && !partIds.length) {
      this.snackBar.open(
        'Keep at least one requested part on the quotation, or reject the parts on the parts requests page.',
        'OK',
        { duration: 6000 },
      );
      return;
    }
    this.saving.set(true);
    const request: Observable<number> = existing
      ? this.api
          .call(
            updateQuotation,
            { quotationId: existing.id, body },
            withRowVersion(existing.rowVersion),
          )
          .pipe(map((q) => q.id))
      : parts
        ? this.api
            .call(createPartRequestQuotation, {
              body: { ...body, partRequestIds: partIds },
            })
            .pipe(map((r) => r.quotationId))
        : this.api.call(createQuotation, { body }).pipe(map((q) => q.id));
    request
      .pipe(
        finalize(() => this.saving.set(false)),
        catchError(() => EMPTY),
      )
      .subscribe((id) => void this.router.navigate(['/sales/quotations', id]));
  }
}
