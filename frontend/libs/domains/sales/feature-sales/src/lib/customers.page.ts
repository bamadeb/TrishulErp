import {
  ChangeDetectionStrategy,
  Component,
  inject,
  signal,
} from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { MatCheckbox } from '@angular/material/checkbox';
import { MatFormField, MatPrefix } from '@angular/material/form-field';
import { MatIcon } from '@angular/material/icon';
import { MatInput } from '@angular/material/input';
import { MatPaginator, PageEvent } from '@angular/material/paginator';
import { MatProgressBar } from '@angular/material/progress-bar';
import { RouterLink } from '@angular/router';
import {
  ApiClient,
  ListCustomerAccounts$Params,
  listCustomerAccounts,
} from '@trishul/core-api';
import { n0, pagedList } from '@trishul/inventory-data-access';
import { PageHeader } from '@trishul/shared-ui';
import { Subject, debounceTime, distinctUntilChanged } from 'rxjs';
import { rupees } from './sales.shared';

/** Customer accounts: balance, credit limit, terms and branches (the customer master stays in Customers). */
@Component({
  selector: 'trishul-customer-accounts-page',
  imports: [
    RouterLink,
    MatIcon,
    MatCheckbox,
    MatFormField,
    MatPrefix,
    MatInput,
    MatPaginator,
    MatProgressBar,
    PageHeader,
  ],
  changeDetection: ChangeDetectionStrategy.OnPush,
  styleUrl: '../../../../inventory/data-access/src/lib/inventory.scss',
  template: `
    <trishul-page-header
      title="Customer accounts"
      subtitle="What each customer owes, their credit limit, terms and branches"
    />
    <div class="filters">
      <mat-form-field
        class="search"
        appearance="outline"
        subscriptSizing="dynamic"
      >
        <mat-icon matPrefix>search</mat-icon>
        <input
          matInput
          type="search"
          placeholder="Name, code, GSTIN or phone"
          aria-label="Search customers"
          (input)="search$.next($any($event.target).value)"
        />
      </mat-form-field>
      <mat-checkbox
        [checked]="!!query().withBalance"
        (change)="update({ withBalance: $event.checked })"
        >With a balance</mat-checkbox
      >
      <mat-checkbox
        [checked]="!!query().overLimit"
        (change)="update({ overLimit: $event.checked })"
        >Over the credit limit</mat-checkbox
      >
    </div>
    <div class="table-card">
      <div class="progress">
        @if (list.loading()) {
          <mat-progress-bar mode="indeterminate" />
        }
      </div>
      <div class="table-scroll">
        <table class="plain wide">
          <thead>
            <tr>
              <th>Customer</th>
              <th>Type</th>
              <th>GSTIN</th>
              <th>State</th>
              <th>Terms</th>
              <th class="num">Branches</th>
              <th class="num">Credit limit</th>
              <th class="num">Balance</th>
            </tr>
          </thead>
          <tbody>
            @for (c of list.items(); track c.id) {
              <tr>
                <td>
                  <a class="name" [routerLink]="[c.id]">{{ c.name }}</a>
                  <div class="muted">{{ c.code }} · {{ c.primaryPhone }}</div>
                </td>
                <td>{{ c.customerType }}</td>
                <td>{{ c.gstin ?? '—' }}</td>
                <td>{{ c.billingStateName ?? '—' }}</td>
                <td>{{ c.paymentTerms ?? '—' }}</td>
                <td class="num">{{ c.branchCount }}</td>
                <td class="num">
                  {{ c.creditLimit ? money(c.creditLimit) : 'No limit' }}
                </td>
                <td
                  class="num"
                  [class.negative]="
                    c.creditLimit !== null && n0(c.balance) > n0(c.creditLimit)
                  "
                  [class.positive]="n0(c.balance) < 0"
                >
                  {{ money(c.balance) }}
                </td>
              </tr>
            } @empty {
              <tr>
                <td colspan="8" class="empty">
                  {{ list.loading() ? 'Loading…' : 'No customers match.' }}
                </td>
              </tr>
            }
          </tbody>
        </table>
      </div>
      <mat-paginator
        [length]="list.total()"
        [pageIndex]="(query().page ?? 1) - 1"
        [pageSize]="query().pageSize"
        [pageSizeOptions]="[20, 50, 100]"
        aria-label="Pages of customers"
        (page)="onPage($event)"
      />
    </div>
  `,
})
export class CustomerAccountsPage {
  private readonly api = inject(ApiClient);
  protected readonly money = rupees;
  protected readonly n0 = n0;
  protected readonly query = signal<ListCustomerAccounts$Params>({
    page: 1,
    pageSize: 20,
  });
  protected readonly list = pagedList(this.query, (q) =>
    this.api.call(listCustomerAccounts, q),
  );
  protected readonly search$ = new Subject<string>();

  constructor() {
    this.search$
      .pipe(debounceTime(350), distinctUntilChanged(), takeUntilDestroyed())
      .subscribe((search) => this.update({ search: search.trim() || null }));
  }

  protected update(change: Partial<ListCustomerAccounts$Params>): void {
    this.query.update((q) => ({ ...q, ...change, page: change.page ?? 1 }));
  }

  protected onPage(event: PageEvent): void {
    this.update({ page: event.pageIndex + 1, pageSize: event.pageSize });
  }
}
