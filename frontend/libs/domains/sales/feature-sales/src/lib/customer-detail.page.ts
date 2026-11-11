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
import { toSignal } from '@angular/core/rxjs-interop';
import { MatButton } from '@angular/material/button';
import { provideNativeDateAdapter } from '@angular/material/core';
import {
  MatDatepicker,
  MatDatepickerInput,
  MatDatepickerToggle,
} from '@angular/material/datepicker';
import { MatDialog } from '@angular/material/dialog';
import {
  MatFormField,
  MatLabel,
  MatSuffix,
} from '@angular/material/form-field';
import { MatIcon } from '@angular/material/icon';
import { MatInput } from '@angular/material/input';
import { MatProgressBar } from '@angular/material/progress-bar';
import { RouterLink } from '@angular/router';
import {
  ApiClient,
  CustomerAccountDetail,
  CustomerBranchOut,
  CustomerOpenItems,
  CustomerStatement,
  addCustomerBranch,
  getCustomerAccount,
  getCustomerOpenItems,
  getCustomerStatement,
  listCustomerBranches,
  updateCustomerBranch,
  updateCustomerCreditTerms,
  withRowVersion,
} from '@trishul/core-api';
import { AuthStore } from '@trishul/core-auth';
import {
  FieldDef,
  isoDate,
  n0,
  num,
  openFieldsDialog,
} from '@trishul/inventory-data-access';
import {
  NO_SALES_OPTIONS,
  SAL_ACCOUNT_PERMISSIONS,
  SAL_CUSTOMER_MANAGE,
  SAL_INVOICE_CREATE_PERMISSIONS,
  SAL_ORDER_MANAGE,
  SAL_QUOTATION_MANAGE,
  SAL_RECEIPT_MANAGE,
  SalesLookups,
} from '@trishul/sales-data-access';
import { PageHeader } from '@trishul/shared-ui';
import { EMPTY, catchError, filter, of } from 'rxjs';
import { rupees } from './sales.shared';

/** A customer's sales account: balance and credit, branches, open items and the statement. */
@Component({
  selector: 'trishul-customer-account-page',
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
    MatProgressBar,
    PageHeader,
  ],
  providers: [provideNativeDateAdapter()],
  changeDetection: ChangeDetectionStrategy.OnPush,
  styleUrl: '../../../../inventory/data-access/src/lib/inventory.scss',
  template: `
    @if (account(); as c) {
      <trishul-page-header
        [title]="c.name"
        [subtitle]="c.code + ' · ' + c.customerType + ' · ' + c.primaryPhone"
      >
        <a mat-stroked-button routerLink="/sales/customers"
          ><mat-icon>arrow_back</mat-icon>Customers</a
        >
        @if (can.manage) {
          <button mat-stroked-button (click)="editTerms(c)">
            <mat-icon>tune</mat-icon>Credit &amp; terms
          </button>
        }
        @if (can.quote) {
          <a
            mat-stroked-button
            routerLink="/sales/quotations/new"
            [queryParams]="{ customerId: c.id }"
            ><mat-icon>request_quote</mat-icon>Quotation</a
          >
        }
        @if (can.order) {
          <a
            mat-stroked-button
            routerLink="/sales/orders/new"
            [queryParams]="{ customerId: c.id }"
            ><mat-icon>shopping_cart</mat-icon>Order</a
          >
        }
        @if (can.invoice) {
          <a
            mat-stroked-button
            routerLink="/sales/invoices/new"
            [queryParams]="{ customerId: c.id }"
            ><mat-icon>receipt_long</mat-icon>Invoice</a
          >
        }
        @if (can.receive) {
          <a
            mat-flat-button
            routerLink="/sales/receipts/new"
            [queryParams]="{ customerId: c.id }"
            ><mat-icon>payments</mat-icon>Receipt</a
          >
        }
      </trishul-page-header>

      <div class="tiles">
        <div class="tile">
          <div class="value" [class.positive]="n0(c.balance) < 0">
            {{ money(c.balance) }}
          </div>
          <div class="label">Balance (owes us)</div>
        </div>
        <div class="tile">
          <div class="value">
            {{ c.creditLimit ? money(c.creditLimit) : 'No limit' }}
          </div>
          <div class="label">Credit limit</div>
        </div>
        <div class="tile">
          <div
            class="value"
            [class.negative]="
              c.availableCredit !== null && n0(c.availableCredit) < 0
            "
          >
            {{ c.availableCredit !== null ? money(c.availableCredit) : '—' }}
          </div>
          <div class="label">Credit available</div>
        </div>
        <div class="tile">
          <div class="value" [class.negative]="n0(c.overdue) > 0">
            {{ money(c.overdue) }}
          </div>
          <div class="label">Overdue</div>
        </div>
        <div class="tile">
          <div class="value">{{ money(c.unallocated) }}</div>
          <div class="label">Unallocated receipts</div>
        </div>
        <div class="tile">
          <div class="value">{{ c.openOrders }}</div>
          <div class="label">Open orders</div>
        </div>
      </div>

      <section class="card">
        <dl class="facts">
          <div>
            <dt>Payment terms</dt>
            <dd>{{ c.paymentTerms ?? '—' }}</dd>
          </div>
          <div>
            <dt>GSTIN · PAN</dt>
            <dd>{{ c.gstin ?? '—' }} · {{ c.pan ?? '—' }}</dd>
          </div>
          <div>
            <dt>Opening balance</dt>
            <dd>
              {{ money(c.openingBalance)
              }}{{
                c.openingBalanceDate
                  ? ' on ' + (c.openingBalanceDate | date: 'dd MMM yyyy')
                  : ''
              }}
            </dd>
          </div>
          <div>
            <dt>Invoiced · received</dt>
            <dd>{{ money(c.invoiced) }} · {{ money(c.received) }}</dd>
          </div>
          <div style="grid-column: span 2">
            <dt>Billing address</dt>
            <dd>
              {{ c.billingAddress ?? '—'
              }}{{ c.billingStateName ? ', ' + c.billingStateName : '' }}
            </dd>
          </div>
        </dl>
      </section>

      <section class="card">
        <h2>
          Branches and delivery addresses
          @if (can.manage) {
            <button mat-button (click)="editBranch(null)">
              <mat-icon>add</mat-icon>Add branch
            </button>
          }
        </h2>
        <table class="plain">
          <thead>
            <tr>
              <th>Branch</th>
              <th>Delivery address</th>
              <th>Billing address</th>
              <th>GSTIN</th>
              <th>Contact</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            @for (b of branches(); track b.id) {
              <tr [class.muted]="!b.isActive">
                <td>
                  <strong>{{ b.siteName }}</strong
                  >{{ b.siteCode ? ' (' + b.siteCode + ')' : '' }}
                  @if (b.isDefault) {
                    <div class="muted">Default</div>
                  }
                  @if (!b.isActive) {
                    <div>Inactive</div>
                  }
                </td>
                <td>
                  {{ b.address }}{{ b.stateName ? ', ' + b.stateName : '' }}
                </td>
                <td>{{ b.billingAddress ?? '—' }}</td>
                <td>{{ b.gstin ?? '—' }}</td>
                <td>
                  {{ b.siteContactName ?? '' }}
                  <div class="muted">
                    {{ b.siteContactPhone ?? '' }} {{ b.email ?? '' }}
                  </div>
                </td>
                <td>
                  @if (can.manage) {
                    <button mat-button (click)="editBranch(b)">Edit</button>
                  }
                </td>
              </tr>
            } @empty {
              <tr>
                <td colspan="6" class="empty">
                  No branches: documents use the billing address.
                </td>
              </tr>
            }
          </tbody>
        </table>
      </section>

      @if (can.accounts) {
        @if (openItems(); as open) {
          <section class="card">
            <h2>Outstanding invoices</h2>
            <table class="plain">
              <thead>
                <tr>
                  <th>Invoice</th>
                  <th>Date</th>
                  <th>Due</th>
                  <th class="num">Total</th>
                  <th class="num">Outstanding</th>
                </tr>
              </thead>
              <tbody>
                @for (i of open.invoices; track i.id) {
                  <tr>
                    <td>
                      <a
                        class="name"
                        [routerLink]="['/sales/invoices', i.id]"
                        >{{ i.invoiceNo }}</a
                      >
                    </td>
                    <td class="nowrap">
                      {{ i.invoiceDate | date: 'dd MMM yyyy' }}
                    </td>
                    <td class="nowrap" [class.negative]="i.overdueDays > 0">
                      {{ i.dueDate ? (i.dueDate | date: 'dd MMM yyyy') : '—' }}
                      @if (i.overdueDays > 0) {
                        <span class="muted">
                          · {{ i.overdueDays }} days late</span
                        >
                      }
                    </td>
                    <td class="num">{{ money(i.total) }}</td>
                    <td class="num">{{ money(i.outstanding) }}</td>
                  </tr>
                } @empty {
                  <tr>
                    <td colspan="5" class="empty">Nothing outstanding.</td>
                  </tr>
                }
              </tbody>
            </table>
          </section>
        }

        <section class="card">
          <h2>Statement</h2>
          <div class="filters">
            <mat-form-field appearance="outline" subscriptSizing="dynamic">
              <mat-label>From</mat-label>
              <input
                matInput
                [matDatepicker]="fromPicker"
                (dateChange)="loadStatement($event.value, null)"
              />
              <mat-datepicker-toggle
                matSuffix
                [for]="fromPicker"
              /><mat-datepicker #fromPicker />
            </mat-form-field>
          </div>
          @if (statement(); as s) {
            <table class="plain">
              <thead>
                <tr>
                  <th>Date</th>
                  <th>Document</th>
                  <th>Description</th>
                  <th class="num">Debit</th>
                  <th class="num">Credit</th>
                  <th class="num">Balance</th>
                </tr>
              </thead>
              <tbody>
                <tr>
                  <td colspan="5">Opening balance</td>
                  <td class="num">{{ money(s.openingBalance) }}</td>
                </tr>
                @for (e of s.entries; track $index) {
                  <tr [class.muted]="e.balance === null">
                    <td class="nowrap">{{ e.date | date: 'dd MMM yyyy' }}</td>
                    <td>
                      <a
                        class="name"
                        [routerLink]="link(e.entryType, e.documentId)"
                        >{{ e.documentNo }}</a
                      >
                      <div class="muted">{{ e.entryType }}</div>
                    </td>
                    <td>
                      {{ e.description
                      }}{{ e.memoAmount ? ' · ' + money(e.memoAmount) : '' }}
                    </td>
                    <td class="num">{{ n0(e.debit) ? money(e.debit) : '' }}</td>
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
                  <td colspan="3">Closing balance</td>
                  <td class="num">{{ money(s.totalDebit) }}</td>
                  <td class="num">{{ money(s.totalCredit) }}</td>
                  <td class="num">{{ money(s.closingBalance) }}</td>
                </tr>
              </tfoot>
            </table>
          }
        </section>
      }
    } @else {
      <mat-progress-bar mode="indeterminate" />
    }
  `,
})
export class CustomerAccountPage {
  private readonly api = inject(ApiClient);
  private readonly dialog = inject(MatDialog);
  private readonly auth = inject(AuthStore);
  readonly customerId = input.required<string>();

  protected readonly can = {
    manage: this.auth.hasPermission(SAL_CUSTOMER_MANAGE),
    accounts: this.auth.hasAnyPermission(SAL_ACCOUNT_PERMISSIONS),
    quote: this.auth.hasPermission(SAL_QUOTATION_MANAGE),
    order: this.auth.hasPermission(SAL_ORDER_MANAGE),
    invoice: this.auth.hasAnyPermission(SAL_INVOICE_CREATE_PERMISSIONS),
    receive: this.auth.hasPermission(SAL_RECEIPT_MANAGE),
  };
  protected readonly money = rupees;
  protected readonly n0 = n0;
  private readonly options = toSignal(inject(SalesLookups).options(), {
    initialValue: NO_SALES_OPTIONS,
  });
  protected readonly account = signal<CustomerAccountDetail | null>(null);
  protected readonly branches = signal<CustomerBranchOut[]>([]);
  protected readonly openItems = signal<CustomerOpenItems | null>(null);
  protected readonly statement = signal<CustomerStatement | null>(null);

  constructor() {
    effect(() => {
      const id = Number(this.customerId());
      untracked(() => this.load(id));
    });
  }

  private load(id: number): void {
    this.api
      .call(getCustomerAccount, { customerId: id })
      .pipe(catchError(() => EMPTY))
      .subscribe((c) => this.account.set(c));
    this.loadBranches(id);
    if (this.can.accounts) {
      this.api
        .call(getCustomerOpenItems, { customerId: id })
        .pipe(catchError(() => EMPTY))
        .subscribe((o) => this.openItems.set(o));
      this.loadStatement(null, id);
    }
  }

  private loadBranches(id: number): void {
    this.api
      .call(listCustomerBranches, { customerId: id, includeInactive: true })
      .pipe(catchError(() => of([] as CustomerBranchOut[])))
      .subscribe((b) => this.branches.set(b));
  }

  protected loadStatement(from: Date | null, id: number | null): void {
    const customerId = id ?? Number(this.customerId());
    this.api
      .call(getCustomerStatement, {
        customerId,
        fromDate: from ? isoDate(from) : null,
      })
      .pipe(catchError(() => EMPTY))
      .subscribe((s) => this.statement.set(s));
  }

  protected link(type: string, id: number): unknown[] {
    const base: Record<string, string> = {
      'Sales order': '/sales/orders',
      Delivery: '/sales/deliveries',
      Invoice: '/sales/invoices',
      Receipt: '/sales/receipts',
    };
    return [base[type], id];
  }

  protected editTerms(c: CustomerAccountDetail): void {
    openFieldsDialog<CustomerAccountDetail>(this.dialog, {
      title: `Credit and terms: ${c.name}`,
      submitText: 'Save',
      value: {
        paymentTermsId: c.paymentTermsId,
        creditLimit: num(c.creditLimit),
        openingBalance: num(c.openingBalance),
        openingBalanceDate: c.openingBalanceDate,
      },
      fields: [
        {
          key: 'paymentTermsId',
          label: 'Payment terms',
          type: 'select',
          options: [
            { value: null, label: '—' },
            ...this.options().paymentTerms.map((t) => ({
              value: t.id,
              label: t.name,
            })),
          ],
        },
        {
          key: 'creditLimit',
          label: 'Credit limit (₹)',
          type: 'number',
          min: 0,
          hint: 'Blank: no limit',
        },
        {
          key: 'openingBalance',
          label: 'Opening balance (₹)',
          type: 'number',
          hint: 'Owed at go-live; negative: advance held',
        },
        { key: 'openingBalanceDate', label: 'As on', type: 'date' },
        {
          key: 'reason',
          label: 'Reason for the change (kept in the log)',
          type: 'textarea',
          required: true,
          maxLength: 300,
        },
      ],
      save: (v) =>
        this.api.call(
          updateCustomerCreditTerms,
          {
            customerId: c.id,
            body: {
              paymentTermsId: (v['paymentTermsId'] as number | null) ?? null,
              creditLimit: (v['creditLimit'] as number | null) ?? null,
              openingBalance: (v['openingBalance'] as number | null) ?? 0,
              openingBalanceDate:
                (v['openingBalanceDate'] as string | null) ?? null,
              reason: v['reason'] as string,
            },
          },
          withRowVersion(c.rowVersion),
        ),
    })
      .pipe(filter((x): x is CustomerAccountDetail => !!x))
      .subscribe((x) => this.account.set(x));
  }

  protected editBranch(branch: CustomerBranchOut | null): void {
    const c = this.account();
    if (!c) return;
    const states = this.options().states.map((s) => ({
      value: s.id,
      label: s.name,
    }));
    const fields: FieldDef[] = [
      { key: 'siteName', label: 'Branch name', required: true, maxLength: 120 },
      {
        key: 'siteCode',
        label: 'Branch code',
        maxLength: 20,
        pattern: '^[A-Za-z0-9][A-Za-z0-9_./-]*$',
      },
      {
        key: 'address',
        label: 'Delivery address',
        type: 'textarea',
        required: true,
        maxLength: 500,
      },
      {
        key: 'stateId',
        label: 'State (place of supply)',
        type: 'select',
        options: [{ value: null, label: '—' }, ...states],
      },
      {
        key: 'billingAddress',
        label: 'Billing address (if different)',
        type: 'textarea',
        maxLength: 500,
      },
      {
        key: 'billingStateId',
        label: 'Billing state',
        type: 'select',
        options: [{ value: null, label: '—' }, ...states],
      },
      {
        key: 'gstin',
        label: 'GSTIN',
        maxLength: 15,
        pattern: '^\\d{2}[A-Z]{5}\\d{4}[A-Z][A-Z\\d]Z[A-Z\\d]$',
      },
      { key: 'siteContactName', label: 'Contact person', maxLength: 100 },
      { key: 'siteContactPhone', label: 'Phone', maxLength: 15 },
      { key: 'email', label: 'Email', maxLength: 120 },
      {
        key: 'isDefault',
        label: 'Default branch for new documents',
        type: 'checkbox',
      },
      ...(branch
        ? [{ key: 'isActive', label: 'Active', type: 'checkbox' as const }]
        : []),
    ];
    openFieldsDialog<CustomerBranchOut>(this.dialog, {
      title: branch ? `Edit ${branch.siteName}` : `New branch of ${c.name}`,
      submitText: branch ? 'Save' : 'Add branch',
      value: branch
        ? { ...branch }
        : { isDefault: this.branches().length === 0 },
      fields,
      save: (v) => {
        const body = {
          siteName: v['siteName'] as string,
          siteCode: (v['siteCode'] as string | null) ?? null,
          address: v['address'] as string,
          stateId: (v['stateId'] as number | null) ?? null,
          billingAddress: (v['billingAddress'] as string | null) ?? null,
          billingStateId: (v['billingStateId'] as number | null) ?? null,
          gstin: (v['gstin'] as string | null)?.toUpperCase() ?? null,
          siteContactName: (v['siteContactName'] as string | null) ?? null,
          siteContactPhone: (v['siteContactPhone'] as string | null) ?? null,
          email: (v['email'] as string | null) ?? null,
          isDefault: Boolean(v['isDefault']),
        };
        return branch
          ? this.api.call(
              updateCustomerBranch,
              {
                branchId: branch.id,
                body: { ...body, isActive: Boolean(v['isActive']) },
              },
              withRowVersion(branch.rowVersion),
            )
          : this.api.call(addCustomerBranch, { customerId: c.id, body });
      },
    })
      .pipe(filter((x): x is CustomerBranchOut => !!x))
      .subscribe(() => this.loadBranches(c.id));
  }
}
