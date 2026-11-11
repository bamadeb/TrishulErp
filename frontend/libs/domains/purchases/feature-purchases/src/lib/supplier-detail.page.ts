import { DatePipe } from '@angular/common';
import {
  ChangeDetectionStrategy,
  Component,
  effect,
  inject,
  input,
  signal,
  untracked,
} from '@angular/core';
import { MatButton } from '@angular/material/button';
import { provideNativeDateAdapter } from '@angular/material/core';
import {
  MatDatepicker,
  MatDatepickerInput,
  MatDatepickerToggle,
} from '@angular/material/datepicker';
import {
  MatFormField,
  MatLabel,
  MatSuffix,
} from '@angular/material/form-field';
import { MatIcon } from '@angular/material/icon';
import { MatInput } from '@angular/material/input';
import { MatTab, MatTabGroup } from '@angular/material/tabs';
import { RouterLink } from '@angular/router';
import {
  ApiClient,
  SupplierDetail,
  SupplierOpenItems,
  SupplierStatement,
  getSupplier,
  getSupplierOpenItems,
  getSupplierStatement,
} from '@trishul/core-api';
import { AuthStore, HasPermission } from '@trishul/core-auth';
import { downloadCsv, isoDate, n0 } from '@trishul/inventory-data-access';
import {
  PUR_ACCOUNT_PERMISSIONS,
  PUR_INVOICE_CREATE_PERMISSIONS,
  PUR_PAYMENT_MANAGE,
  PUR_SUPPLIER_MANAGE,
} from '@trishul/purchases-data-access';
import { PageHeader } from '@trishul/shared-ui';
import { EMPTY, catchError, filter } from 'rxjs';
import { rupees } from './purchases.shared';
import { SupplierEditor } from './supplier-editor';

const LINKS: Record<string, string> = {
  'Purchase order': '/purchases/orders',
  GRN: '/purchases/grns',
  Invoice: '/purchases/invoices',
  Payment: '/purchases/payments',
  'Credit note': '/purchases/credit-notes',
};

/** One supplier: balance, statement (transaction inquiry) and open items. */
@Component({
  selector: 'trishul-supplier-detail-page',
  imports: [
    DatePipe,
    RouterLink,
    MatButton,
    MatIcon,
    MatFormField,
    MatLabel,
    MatSuffix,
    MatInput,
    MatDatepicker,
    MatDatepickerInput,
    MatDatepickerToggle,
    MatTabGroup,
    MatTab,
    HasPermission,
    PageHeader,
  ],
  providers: [SupplierEditor, provideNativeDateAdapter()],
  changeDetection: ChangeDetectionStrategy.OnPush,
  styleUrl: '../../../../inventory/data-access/src/lib/inventory.scss',
  template: `
    @if (supplier(); as s) {
      <trishul-page-header
        [title]="s.name"
        [subtitle]="
          s.code + ' · ' + s.supplierType + (s.isActive ? '' : ' · Inactive')
        "
      >
        <a mat-stroked-button routerLink="/purchases/suppliers"
          ><mat-icon>arrow_back</mat-icon>Suppliers</a
        >
        <a
          mat-stroked-button
          routerLink="/purchases/invoices/new"
          [queryParams]="{ supplierId: s.id }"
          *trishulHasPermission="invoicePermissions"
          ><mat-icon>receipt_long</mat-icon>Invoice</a
        >
        <a
          mat-stroked-button
          routerLink="/purchases/payments/new"
          [queryParams]="{ supplierId: s.id }"
          *trishulHasPermission="payPermission"
          ><mat-icon>payments</mat-icon>Pay</a
        >
        @if (canManage) {
          <button mat-flat-button (click)="edit(s)">
            <mat-icon>edit</mat-icon>Edit
          </button>
        }
      </trishul-page-header>

      <div class="tiles">
        <div class="tile">
          <div class="value" [class.negative]="n0(s.balance) > 0">
            {{ money(s.balance) }}
          </div>
          <div class="label">
            Balance (we owe){{ n0(s.balance) < 0 ? ' · advance' : '' }}
          </div>
        </div>
        <div class="tile">
          <div class="value" [class.negative]="n0(s.overdue) > 0">
            {{ money(s.overdue) }}
          </div>
          <div class="label">Overdue</div>
        </div>
        <div class="tile">
          <div class="value">{{ money(s.unallocated) }}</div>
          <div class="label">Not allocated</div>
        </div>
        <div class="tile">
          <div class="value">{{ money(s.invoiced) }}</div>
          <div class="label">Invoiced</div>
        </div>
        <div class="tile">
          <div class="value">{{ money(s.paid) }}</div>
          <div class="label">Paid</div>
        </div>
        <div class="tile">
          <div class="value">{{ money(s.credited) }}</div>
          <div class="label">Credit notes</div>
        </div>
      </div>

      <section class="card">
        <dl class="facts">
          <div>
            <dt>Contact</dt>
            <dd>
              {{ s.contactPerson ?? '—' }} {{ s.phone ? '· ' + s.phone : '' }}
            </dd>
          </div>
          <div>
            <dt>Email</dt>
            <dd>{{ s.email ?? '—' }}</dd>
          </div>
          <div>
            <dt>GSTIN</dt>
            <dd>
              {{ s.gstin ?? '—' }}
              {{
                s.gstRegistrationType ? '(' + s.gstRegistrationType + ')' : ''
              }}
            </dd>
          </div>
          <div>
            <dt>PAN</dt>
            <dd>{{ s.pan ?? '—' }}</dd>
          </div>
          <div>
            <dt>State</dt>
            <dd>{{ s.stateName ?? '—' }}</dd>
          </div>
          <div>
            <dt>Payment terms</dt>
            <dd>{{ s.paymentTerms ?? '—' }}</dd>
          </div>
          <div>
            <dt>Credit limit</dt>
            <dd>{{ money(s.creditLimit) }}</dd>
          </div>
          <div>
            <dt>Bank</dt>
            <dd>
              {{ s.bankName ?? '—' }} {{ s.bankAccountNo ?? '' }}
              {{ s.ifsc ?? '' }}
            </dd>
          </div>
          <div>
            <dt>Opening balance</dt>
            <dd>
              {{ money(s.openingBalance) }}
              {{
                s.openingBalanceDate
                  ? 'as of ' + (s.openingBalanceDate | date: 'dd MMM yyyy')
                  : ''
              }}
            </dd>
          </div>
          <div style="grid-column: 1 / -1">
            <dt>Billing address</dt>
            <dd>{{ s.address ?? '—' }}</dd>
          </div>
        </dl>
      </section>

      @if (canSeeAccounts) {
        <mat-tab-group mat-stretch-tabs="false" animationDuration="0ms">
          <mat-tab label="Statement">
            <div class="filters">
              <mat-form-field appearance="outline" subscriptSizing="dynamic">
                <mat-label>From</mat-label>
                <input
                  matInput
                  [matDatepicker]="fromPicker"
                  (dateChange)="from.set($event.value); loadStatement()"
                />
                <mat-datepicker-toggle
                  matSuffix
                  [for]="fromPicker"
                /><mat-datepicker #fromPicker />
              </mat-form-field>
              <mat-form-field appearance="outline" subscriptSizing="dynamic">
                <mat-label>To</mat-label>
                <input
                  matInput
                  [matDatepicker]="toPicker"
                  (dateChange)="to.set($event.value); loadStatement()"
                />
                <mat-datepicker-toggle
                  matSuffix
                  [for]="toPicker"
                /><mat-datepicker #toPicker />
              </mat-form-field>
              <button
                mat-stroked-button
                (click)="exportStatement()"
                [disabled]="!statement()"
              >
                <mat-icon>download</mat-icon>Export
              </button>
            </div>
            @if (statement(); as st) {
              <div class="table-card">
                <div class="table-scroll">
                  <table class="plain wide">
                    <thead>
                      <tr>
                        <th>Date</th>
                        <th>Type</th>
                        <th>Number</th>
                        <th>Their ref</th>
                        <th>Details</th>
                        <th class="num">Paid / credited</th>
                        <th class="num">Invoiced</th>
                        <th class="num">Balance</th>
                      </tr>
                    </thead>
                    <tbody>
                      <tr>
                        <td colspan="7"><strong>Opening balance</strong></td>
                        <td class="num">
                          <strong>{{ money(st.openingBalance) }}</strong>
                        </td>
                      </tr>
                      @for (e of st.entries; track e.entryType + e.documentId) {
                        <tr [class.muted]="e.memoAmount !== null">
                          <td class="nowrap">
                            {{ e.date | date: 'dd MMM yyyy' }}
                          </td>
                          <td>{{ e.entryType }}</td>
                          <td>
                            <a
                              class="name"
                              [routerLink]="[link(e.entryType), e.documentId]"
                              >{{ e.documentNo }}</a
                            >
                          </td>
                          <td>{{ e.reference ?? '' }}</td>
                          <td>
                            {{ e.description }}
                            @if (e.memoAmount !== null) {
                              · {{ money(e.memoAmount) }}
                            }
                          </td>
                          <td class="num">
                            {{ n0(e.debit) ? money(e.debit) : '' }}
                          </td>
                          <td class="num">
                            {{ n0(e.credit) ? money(e.credit) : '' }}
                          </td>
                          <td class="num">
                            {{ e.balance !== null ? money(e.balance) : '' }}
                          </td>
                        </tr>
                      }
                    </tbody>
                    <tfoot>
                      <tr>
                        <td colspan="5">Closing balance</td>
                        <td class="num">{{ money(st.totalDebit) }}</td>
                        <td class="num">{{ money(st.totalCredit) }}</td>
                        <td class="num">{{ money(st.closingBalance) }}</td>
                      </tr>
                    </tfoot>
                  </table>
                </div>
              </div>
            }
          </mat-tab>
          <mat-tab label="Open items">
            @if (openItems(); as items) {
              <section class="card">
                <h2>Outstanding invoices</h2>
                <table class="plain">
                  <thead>
                    <tr>
                      <th>Invoice</th>
                      <th>Their no</th>
                      <th>Date</th>
                      <th>Due</th>
                      <th class="num">Total</th>
                      <th class="num">Settled</th>
                      <th class="num">Outstanding</th>
                    </tr>
                  </thead>
                  <tbody>
                    @for (i of items.invoices; track i.id) {
                      <tr>
                        <td>
                          <a
                            class="name"
                            [routerLink]="['/purchases/invoices', i.id]"
                            >{{ i.invoiceNo }}</a
                          >
                        </td>
                        <td>{{ i.supplierInvoiceNo }}</td>
                        <td class="nowrap">
                          {{ i.supplierInvoiceDate | date: 'dd MMM yyyy' }}
                        </td>
                        <td class="nowrap" [class.negative]="i.overdueDays > 0">
                          {{
                            i.dueDate ? (i.dueDate | date: 'dd MMM yyyy') : '—'
                          }}{{
                            i.overdueDays > 0
                              ? ' (' + i.overdueDays + ' days late)'
                              : ''
                          }}
                        </td>
                        <td class="num">{{ money(i.total) }}</td>
                        <td class="num">{{ money(i.allocated) }}</td>
                        <td class="num">{{ money(i.outstanding) }}</td>
                      </tr>
                    } @empty {
                      <tr>
                        <td colspan="7" class="empty">Nothing outstanding.</td>
                      </tr>
                    }
                  </tbody>
                </table>
              </section>
              <section class="card">
                <h2>Payments and credit notes not yet allocated</h2>
                <table class="plain">
                  <thead>
                    <tr>
                      <th>Kind</th>
                      <th>Number</th>
                      <th>Date</th>
                      <th>Reference</th>
                      <th class="num">Amount</th>
                      <th class="num">Unallocated</th>
                    </tr>
                  </thead>
                  <tbody>
                    @for (c of items.credits; track c.kind + c.id) {
                      <tr>
                        <td>{{ c.kind }}</td>
                        <td>
                          <a
                            class="name"
                            [routerLink]="[
                              c.kind === 'Payment'
                                ? '/purchases/payments'
                                : '/purchases/credit-notes',
                              c.id,
                            ]"
                            >{{ c.documentNo }}</a
                          >
                        </td>
                        <td class="nowrap">
                          {{ c.date | date: 'dd MMM yyyy' }}
                        </td>
                        <td>{{ c.reference ?? '' }}</td>
                        <td class="num">{{ money(c.amount) }}</td>
                        <td class="num">{{ money(c.unallocated) }}</td>
                      </tr>
                    } @empty {
                      <tr>
                        <td colspan="6" class="empty">
                          Everything is allocated.
                        </td>
                      </tr>
                    }
                  </tbody>
                </table>
                @if (items.credits.length && items.invoices.length) {
                  <a
                    mat-stroked-button
                    routerLink="/purchases/allocations"
                    [queryParams]="{ supplierId: s.id }"
                  >
                    <mat-icon>link</mat-icon>Allocate
                  </a>
                }
              </section>
            }
          </mat-tab>
        </mat-tab-group>
      }
    }
  `,
})
export class SupplierDetailPage {
  private readonly api = inject(ApiClient);
  private readonly editor = inject(SupplierEditor);
  private readonly auth = inject(AuthStore);
  readonly supplierId = input.required<string>();

  protected readonly canManage = this.auth.hasPermission(PUR_SUPPLIER_MANAGE);
  protected readonly canSeeAccounts = this.auth.hasAnyPermission(
    PUR_ACCOUNT_PERMISSIONS,
  );
  protected readonly invoicePermissions = PUR_INVOICE_CREATE_PERMISSIONS;
  protected readonly payPermission = PUR_PAYMENT_MANAGE;
  protected readonly money = rupees;
  protected readonly n0 = n0;

  protected readonly supplier = signal<SupplierDetail | null>(null);
  protected readonly statement = signal<SupplierStatement | null>(null);
  protected readonly openItems = signal<SupplierOpenItems | null>(null);
  protected readonly from = signal<Date | null>(null);
  protected readonly to = signal<Date | null>(null);

  constructor() {
    effect(() => {
      const id = Number(this.supplierId());
      untracked(() => this.load(id));
    });
  }

  private load(id: number): void {
    this.api
      .call(getSupplier, { supplierId: id })
      .pipe(catchError(() => EMPTY))
      .subscribe((s) => this.supplier.set(s));
    if (this.canSeeAccounts) {
      this.loadStatement();
      this.api
        .call(getSupplierOpenItems, { supplierId: id })
        .pipe(catchError(() => EMPTY))
        .subscribe((items) => this.openItems.set(items));
    }
  }

  protected loadStatement(): void {
    const from = this.from();
    const to = this.to();
    this.api
      .call(getSupplierStatement, {
        supplierId: Number(this.supplierId()),
        fromDate: from ? isoDate(from) : null,
        toDate: to ? isoDate(to) : null,
      })
      .pipe(catchError(() => EMPTY))
      .subscribe((st) => this.statement.set(st));
  }

  protected link(type: string): string {
    return LINKS[type] ?? '/purchases';
  }

  protected edit(supplier: SupplierDetail): void {
    this.editor
      .edit(supplier)
      .pipe(filter((saved): saved is SupplierDetail => !!saved))
      .subscribe((saved) => this.supplier.set(saved));
  }

  protected exportStatement(): void {
    const st = this.statement();
    if (!st) return;
    downloadCsv(
      `statement-${this.supplier()?.code ?? st.supplierId}.csv`,
      [
        'Date',
        'Type',
        'Number',
        'Their ref',
        'Details',
        'Paid / credited',
        'Invoiced',
        'Balance',
      ],
      [
        [
          st.fromDate ?? '',
          'Opening',
          '',
          '',
          '',
          null,
          null,
          n0(st.openingBalance),
        ],
        ...st.entries.map((e) => [
          e.date,
          e.entryType,
          e.documentNo,
          e.reference,
          e.description,
          n0(e.debit),
          n0(e.credit),
          e.balance === null ? null : n0(e.balance),
        ]),
        [
          st.toDate,
          'Closing',
          '',
          '',
          '',
          n0(st.totalDebit),
          n0(st.totalCredit),
          n0(st.closingBalance),
        ],
      ],
    );
  }
}
