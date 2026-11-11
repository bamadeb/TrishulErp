import { DatePipe } from '@angular/common';
import {
  ChangeDetectionStrategy,
  Component,
  inject,
  signal,
} from '@angular/core';
import { takeUntilDestroyed, toSignal } from '@angular/core/rxjs-interop';
import { FormControl, ReactiveFormsModule } from '@angular/forms';
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
  MatPrefix,
  MatSuffix,
} from '@angular/material/form-field';
import { MatIcon } from '@angular/material/icon';
import { MatInput } from '@angular/material/input';
import { MatPaginator, PageEvent } from '@angular/material/paginator';
import { MatProgressBar } from '@angular/material/progress-bar';
import { MatOption, MatSelect } from '@angular/material/select';
import { RouterLink } from '@angular/router';
import {
  ApiClient,
  ListQuotations$Params,
  listQuotations,
} from '@trishul/core-api';
import { HasPermission } from '@trishul/core-auth';
import { isoDate, pagedList } from '@trishul/inventory-data-access';
import {
  CustomerPicker,
  NO_SALES_OPTIONS,
  PickedCustomer,
  SAL_QUOTATION_MANAGE,
  SalesLookups,
} from '@trishul/sales-data-access';
import { PageHeader, StatusBadge } from '@trishul/shared-ui';
import { Subject, debounceTime, distinctUntilChanged } from 'rxjs';
import { QUOTATION_STATE, QUOTATION_STATES, rupees } from './sales.shared';

/** Quotations: by number, customer, branch, date and state (submitted ones past validity show Expired). */
@Component({
  selector: 'trishul-quotation-list-page',
  imports: [
    DatePipe,
    ReactiveFormsModule,
    RouterLink,
    MatButton,
    MatIcon,
    MatFormField,
    MatLabel,
    MatPrefix,
    MatSuffix,
    MatInput,
    MatSelect,
    MatOption,
    MatDatepicker,
    MatDatepickerInput,
    MatDatepickerToggle,
    MatPaginator,
    MatProgressBar,
    HasPermission,
    CustomerPicker,
    PageHeader,
    StatusBadge,
  ],
  providers: [provideNativeDateAdapter()],
  changeDetection: ChangeDetectionStrategy.OnPush,
  styleUrl: '../../../../inventory/data-access/src/lib/inventory.scss',
  template: `
    <trishul-page-header
      title="Sales quotations"
      subtitle="Quotations sent to customers, their revisions and answers"
    >
      <a mat-flat-button routerLink="new" *trishulHasPermission="manage"
        ><mat-icon>add</mat-icon>New quotation</a
      >
    </trishul-page-header>
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
          placeholder="Quotation no or customer"
          aria-label="Search quotations"
          (input)="search$.next($any($event.target).value)"
        />
      </mat-form-field>
      <trishul-customer-picker
        [formControl]="customer"
        style="flex: 1 1 16rem"
      />
      <mat-form-field appearance="outline" subscriptSizing="dynamic">
        <mat-label>State</mat-label>
        <mat-select
          [value]="query().state ?? null"
          (valueChange)="update({ state: $event })"
        >
          <mat-option [value]="null">All</mat-option>
          @for (s of states; track s) {
            <mat-option [value]="s">{{ s }}</mat-option>
          }
        </mat-select>
      </mat-form-field>
      <mat-form-field appearance="outline" subscriptSizing="dynamic">
        <mat-label>Branch</mat-label>
        <mat-select
          [value]="query().branchId ?? null"
          (valueChange)="update({ branchId: $event })"
        >
          <mat-option [value]="null">All</mat-option>
          @for (b of options().branches; track b.id) {
            <mat-option [value]="b.id">{{ b.name }}</mat-option>
          }
        </mat-select>
      </mat-form-field>
      <mat-form-field appearance="outline" subscriptSizing="dynamic">
        <mat-label>From</mat-label>
        <input
          matInput
          [matDatepicker]="fromPicker"
          (dateChange)="
            update({ fromDate: $event.value ? iso($event.value) : null })
          "
        />
        <mat-datepicker-toggle matSuffix [for]="fromPicker" /><mat-datepicker
          #fromPicker
        />
      </mat-form-field>
      <mat-form-field appearance="outline" subscriptSizing="dynamic">
        <mat-label>To</mat-label>
        <input
          matInput
          [matDatepicker]="toPicker"
          (dateChange)="
            update({ toDate: $event.value ? iso($event.value) : null })
          "
        />
        <mat-datepicker-toggle matSuffix [for]="toPicker" /><mat-datepicker
          #toPicker
        />
      </mat-form-field>
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
              <th>Quotation</th>
              <th>Date</th>
              <th>Valid until</th>
              <th>Customer</th>
              <th>Brand · branch</th>
              <th>State</th>
              <th class="num">Version</th>
              <th class="num">Total</th>
            </tr>
          </thead>
          <tbody>
            @for (q of list.items(); track q.id) {
              <tr>
                <td>
                  <a class="name" [routerLink]="[q.id]">{{ q.quotationNo }}</a>
                </td>
                <td class="nowrap">
                  {{ q.quotationDate | date: 'dd MMM yyyy' }}
                </td>
                <td class="nowrap">
                  {{
                    q.validUntil ? (q.validUntil | date: 'dd MMM yyyy') : '—'
                  }}
                </td>
                <td>
                  {{ q.customerName }}
                  @if (q.customerSiteName) {
                    <div class="muted">{{ q.customerSiteName }}</div>
                  }
                </td>
                <td>
                  {{ q.principalName }}
                  <div class="muted">{{ q.branchName }}</div>
                </td>
                <td>
                  <trishul-status-badge
                    [status]="q.state"
                    [severities]="severity"
                  />
                </td>
                <td class="num">{{ q.currentVersion }}</td>
                <td class="num">{{ money(q.total) }}</td>
              </tr>
            } @empty {
              <tr>
                <td colspan="8" class="empty">
                  {{ list.loading() ? 'Loading…' : 'No quotations match.' }}
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
        aria-label="Pages of quotations"
        (page)="onPage($event)"
      />
    </div>
  `,
})
export class QuotationListPage {
  private readonly api = inject(ApiClient);
  protected readonly manage = SAL_QUOTATION_MANAGE;
  protected readonly states = QUOTATION_STATES;
  protected readonly severity = QUOTATION_STATE;
  protected readonly money = rupees;
  protected readonly iso = isoDate;
  protected readonly options = toSignal(inject(SalesLookups).options(), {
    initialValue: NO_SALES_OPTIONS,
  });
  protected readonly customer = new FormControl<PickedCustomer | null>(null);
  protected readonly query = signal<ListQuotations$Params>({
    page: 1,
    pageSize: 20,
  });
  protected readonly list = pagedList(this.query, (q) =>
    this.api.call(listQuotations, q),
  );
  protected readonly search$ = new Subject<string>();

  constructor() {
    this.search$
      .pipe(debounceTime(350), distinctUntilChanged(), takeUntilDestroyed())
      .subscribe((search) => this.update({ search: search.trim() || null }));
    this.customer.valueChanges
      .pipe(takeUntilDestroyed())
      .subscribe((c) => this.update({ customerId: c?.id ?? null }));
  }

  protected update(change: Partial<ListQuotations$Params>): void {
    this.query.update((q) => ({ ...q, ...change, page: change.page ?? 1 }));
  }

  protected onPage(event: PageEvent): void {
    this.update({ page: event.pageIndex + 1, pageSize: event.pageSize });
  }
}
