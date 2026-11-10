import {
  ChangeDetectionStrategy,
  Component,
  inject,
  signal,
} from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { MatButton, MatIconButton } from '@angular/material/button';
import { MatDialog } from '@angular/material/dialog';
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
import { MatTooltip } from '@angular/material/tooltip';
import {
  ApiClient,
  ListSuppliers$Params,
  SupplierCreate,
  SupplierOut,
  SupplierUpdate,
  createSupplier,
  listSuppliers,
  updateSupplier,
  withRowVersion,
} from '@trishul/core-api';
import { AuthStore } from '@trishul/core-auth';
import { PageHeader } from '@trishul/shared-ui';
import { Subject, debounceTime, distinctUntilChanged, filter } from 'rxjs';
import { openFieldsDialog } from './fields.dialog';
import { INV_GRN_MANAGE } from '@trishul/inventory-data-access';
import { InventoryLookups, pagedList } from './inventory.shared';

type SupplierSupplierType = NonNullable<SupplierCreate['supplierType']>;

const TYPES: SupplierSupplierType[] = [
  'OEM',
  'Parts',
  'Lubricants',
  'Services',
  'Transporter',
  'Other',
];
const GSTIN = '^\\d{2}[A-Z]{5}\\d{4}[A-Z][A-Z\\d]Z[A-Z\\d]$';
const PAN = '^[A-Z]{5}\\d{4}[A-Z]$';

/** Suppliers goods are received from (GRN) and their purchase prices. */
@Component({
  selector: 'trishul-suppliers-page',
  imports: [
    MatButton,
    MatIconButton,
    MatIcon,
    MatTooltip,
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
  changeDetection: ChangeDetectionStrategy.OnPush,
  styleUrl: './inventory.scss',
  template: `
    <trishul-page-header
      title="Suppliers"
      subtitle="Who goods are received from"
    >
      @if (canManage) {
        <button mat-flat-button (click)="edit(null)">
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
    </div>
    <div class="table-card">
      <div class="progress">
        @if (list.loading()) {
          <mat-progress-bar mode="indeterminate" />
        }
      </div>
      <div class="table-scroll">
        <table class="plain">
          <thead>
            <tr>
              <th>Code</th>
              <th>Name</th>
              <th>Type</th>
              <th>GSTIN</th>
              <th>Phone</th>
              <th>Email</th>
              <th>Status</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            @for (s of list.items(); track s.id) {
              <tr>
                <td>{{ s.code }}</td>
                <td>
                  {{ s.name }}
                  @if (s.address) {
                    <div class="muted">{{ s.address }}</div>
                  }
                </td>
                <td>{{ s.supplierType }}</td>
                <td>{{ s.gstin ?? '—' }}</td>
                <td>{{ s.phone ?? '—' }}</td>
                <td>{{ s.email ?? '—' }}</td>
                <td>{{ s.isActive ? 'Active' : 'Inactive' }}</td>
                <td class="actions">
                  @if (canManage) {
                    <button
                      mat-icon-button
                      matTooltip="Change"
                      (click)="edit(s)"
                    >
                      <mat-icon>edit</mat-icon>
                    </button>
                  }
                </td>
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
  private readonly dialog = inject(MatDialog);
  private readonly lookups = inject(InventoryLookups);
  protected readonly canManage =
    inject(AuthStore).hasPermission(INV_GRN_MANAGE);

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

  protected edit(supplier: SupplierOut | null): void {
    openFieldsDialog(this.dialog, {
      title: supplier ? `Change ${supplier.code}` : 'Add supplier',
      submitText: supplier ? 'Save' : 'Add',
      fields: [
        ...(supplier
          ? []
          : [
              {
                key: 'code',
                label: 'Code',
                required: true,
                maxLength: 20,
                pattern: '^[A-Za-z0-9][A-Za-z0-9_./-]*$',
              },
            ]),
        {
          key: 'name',
          label: 'Name',
          required: true,
          maxLength: 200,
          wide: !supplier,
        },
        {
          key: 'supplierType',
          label: 'Type',
          type: 'select' as const,
          required: true,
          options: TYPES.map((t) => ({ value: t, label: t })),
        },
        {
          key: 'gstin',
          label: 'GSTIN',
          pattern: GSTIN,
          hint: '15 characters, capitals',
        },
        { key: 'pan', label: 'PAN', pattern: PAN },
        { key: 'phone', label: 'Phone', maxLength: 15 },
        { key: 'email', label: 'Email', maxLength: 120 },
        { key: 'address', label: 'Address', type: 'textarea' as const },
        ...(supplier
          ? [{ key: 'isActive', label: 'Active', type: 'checkbox' as const }]
          : []),
      ],
      value: supplier ? { ...supplier } : { supplierType: 'Parts' },
      save: (v) =>
        supplier
          ? this.api.call(
              updateSupplier,
              { supplierId: supplier.id, body: v as SupplierUpdate },
              withRowVersion(supplier.rowVersion),
            )
          : this.api.call(createSupplier, {
              body: v as unknown as SupplierCreate,
            }),
    })
      .pipe(filter((saved) => !!saved))
      .subscribe(() => {
        this.lookups.reset();
        this.list.reload();
      });
  }
}
