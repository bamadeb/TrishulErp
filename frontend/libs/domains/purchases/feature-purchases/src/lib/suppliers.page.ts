import {
  ChangeDetectionStrategy,
  Component,
  inject,
  signal,
} from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { MatButton } from '@angular/material/button';
import { MatCheckbox } from '@angular/material/checkbox';
import {
  MatFormField,
  MatLabel,
  MatPrefix,
} from '@angular/material/form-field';
import { MatIcon } from '@angular/material/icon';
import { MatInput } from '@angular/material/input';
import { MatPaginator, PageEvent } from '@angular/material/paginator';
import { MatProgressBar } from '@angular/material/progress-bar';
import { MatOption, MatSelect } from '@angular/material/select';
import { Router, RouterLink } from '@angular/router';
import {
  ApiClient,
  ListSuppliers$Params,
  SupplierDetail,
  listSuppliers,
} from '@trishul/core-api';
import { AuthStore } from '@trishul/core-auth';
import { pagedList } from '@trishul/inventory-data-access';
import { PUR_SUPPLIER_MANAGE } from '@trishul/purchases-data-access';
import { PageHeader } from '@trishul/shared-ui';
import { Subject, debounceTime, distinctUntilChanged, filter } from 'rxjs';
import { rupees } from './purchases.shared';
import { SupplierEditor } from './supplier-editor';

/** Suppliers with what we owe each one. */
@Component({
  selector: 'trishul-suppliers-page',
  imports: [
    RouterLink,
    MatButton,
    MatIcon,
    MatCheckbox,
    MatFormField,
    MatLabel,
    MatPrefix,
    MatInput,
    MatSelect,
    MatOption,
    MatPaginator,
    MatProgressBar,
    PageHeader,
  ],
  providers: [SupplierEditor],
  changeDetection: ChangeDetectionStrategy.OnPush,
  styleUrl: '../../../../inventory/data-access/src/lib/inventory.scss',
  template: `
    <trishul-page-header
      title="Suppliers"
      subtitle="Who we buy from, and what we owe each of them"
    >
      @if (canManage) {
        <button mat-flat-button (click)="add()">
          <mat-icon>add</mat-icon>Add supplier
        </button>
      }
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
          placeholder="Code, name or GSTIN"
          aria-label="Search suppliers"
          (input)="search$.next($any($event.target).value)"
        />
      </mat-form-field>
      <mat-form-field appearance="outline" subscriptSizing="dynamic">
        <mat-label>Status</mat-label>
        <mat-select
          [value]="query().status"
          (valueChange)="update({ status: $event })"
        >
          <mat-option value="active">Active</mat-option>
          <mat-option value="inactive">Inactive</mat-option>
          <mat-option value="all">All</mat-option>
        </mat-select>
      </mat-form-field>
      <mat-checkbox
        [checked]="!!query().withBalance"
        (change)="update({ withBalance: $event.checked })"
      >
        With a balance only
      </mat-checkbox>
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
              <th>Code</th>
              <th>Name</th>
              <th>Type</th>
              <th>GSTIN</th>
              <th>Contact</th>
              <th>Terms</th>
              <th class="num">Balance</th>
              <th>Status</th>
            </tr>
          </thead>
          <tbody>
            @for (s of list.items(); track s.id) {
              <tr>
                <td>
                  <a class="name" [routerLink]="[s.id]">{{ s.code }}</a>
                </td>
                <td>
                  {{ s.name }}
                  @if (s.stateName) {
                    <div class="muted">{{ s.stateName }}</div>
                  }
                </td>
                <td>{{ s.supplierType }}</td>
                <td>{{ s.gstin ?? '—' }}</td>
                <td>
                  {{ s.contactPerson ?? '' }}
                  <div class="muted">{{ s.phone ?? '' }}</div>
                </td>
                <td>{{ s.paymentTerms ?? '—' }}</td>
                <td class="num" [class.negative]="+s.balance > 0">
                  {{ money(s.balance) }}
                </td>
                <td>{{ s.isActive ? 'Active' : 'Inactive' }}</td>
              </tr>
            } @empty {
              <tr>
                <td colspan="8" class="empty">
                  {{ list.loading() ? 'Loading…' : 'No suppliers match.' }}
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
        aria-label="Pages of suppliers"
        (page)="onPage($event)"
      />
    </div>
  `,
})
export class SuppliersPage {
  private readonly api = inject(ApiClient);
  private readonly editor = inject(SupplierEditor);
  private readonly router = inject(Router);
  protected readonly canManage =
    inject(AuthStore).hasPermission(PUR_SUPPLIER_MANAGE);
  protected readonly money = rupees;

  protected readonly query = signal<ListSuppliers$Params>({
    page: 1,
    pageSize: 20,
    status: 'active',
    sort: 'name',
  });
  protected readonly list = pagedList(this.query, (q) =>
    this.api.call(listSuppliers, q),
  );
  protected readonly search$ = new Subject<string>();

  constructor() {
    this.search$
      .pipe(debounceTime(350), distinctUntilChanged(), takeUntilDestroyed())
      .subscribe((search) => this.update({ search: search.trim() || null }));
  }

  protected update(change: Partial<ListSuppliers$Params>): void {
    this.query.update((q) => ({ ...q, ...change, page: change.page ?? 1 }));
  }

  protected onPage(event: PageEvent): void {
    this.update({ page: event.pageIndex + 1, pageSize: event.pageSize });
  }

  protected add(): void {
    this.editor
      .edit(null)
      .pipe(filter((saved): saved is SupplierDetail => !!saved))
      .subscribe(
        (saved) =>
          void this.router.navigate(['/purchases/suppliers', saved.id]),
      );
  }
}
