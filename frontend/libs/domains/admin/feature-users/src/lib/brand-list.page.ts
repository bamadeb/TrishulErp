import {
  ChangeDetectionStrategy,
  Component,
  inject,
  signal,
} from '@angular/core';
import { MatButton, MatIconButton } from '@angular/material/button';
import { MatDialog } from '@angular/material/dialog';
import { MatIcon } from '@angular/material/icon';
import { MatProgressBar } from '@angular/material/progress-bar';
import { MatTableModule } from '@angular/material/table';
import { MatTooltip } from '@angular/material/tooltip';
import { BrandApi, BrandItem } from '@trishul/admin-data-access';
import { PageHeader, StatusBadge } from '@trishul/shared-ui';
import { ACTIVE_SEVERITY } from './alert-rule-list.page';
import { BrandEditData, BrandEditDialog } from './brand-edit.dialog';
import { CompanyAddDialog } from './company-add.dialog';

/** Administration > Companies & brands: the brands, and the company behind each. */
@Component({
  selector: 'trishul-brand-list-page',
  imports: [
    MatButton,
    MatIconButton,
    MatIcon,
    MatProgressBar,
    MatTableModule,
    MatTooltip,
    PageHeader,
    StatusBadge,
  ],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <trishul-page-header
      title="Companies & brands"
      subtitle="The brands you sell and service, and the company behind each. The company name shows beside the brand in every brand dropdown."
    >
      <button mat-stroked-button type="button" (click)="addCompany()">
        <mat-icon>domain_add</mat-icon>
        Add company
      </button>
      <button mat-flat-button type="button" (click)="edit({})">
        <mat-icon>add</mat-icon>
        Add brand
      </button>
    </trishul-page-header>

    <div class="table-card">
      <div class="progress">
        @if (loading()) {
          <mat-progress-bar mode="indeterminate" />
        }
      </div>
      <div class="table-scroll">
        <table mat-table [dataSource]="brands()">
          <ng-container matColumnDef="name">
            <th mat-header-cell *matHeaderCellDef>Brand</th>
            <td mat-cell *matCellDef="let b">
              {{ b.name
              }}@if (b.companyName) {
                <span class="muted"> – {{ b.companyName }}</span>
              }
              <div class="muted">{{ b.code }}</div>
            </td>
          </ng-container>
          <ng-container matColumnDef="handles">
            <th mat-header-cell *matHeaderCellDef>Handles</th>
            <td mat-cell *matCellDef="let b">{{ handles(b) }}</td>
          </ng-container>
          <ng-container matColumnDef="status">
            <th mat-header-cell *matHeaderCellDef>Status</th>
            <td mat-cell *matCellDef="let b">
              <trishul-status-badge
                [status]="b.isActive ? 'Active' : 'Inactive'"
                [severities]="activeSeverity"
              />
            </td>
          </ng-container>
          <ng-container matColumnDef="actions">
            <th mat-header-cell *matHeaderCellDef>
              <span class="sr-only">Actions</span>
            </th>
            <td mat-cell *matCellDef="let b" class="actions">
              <button
                mat-icon-button
                type="button"
                matTooltip="Edit"
                [attr.aria-label]="'Edit ' + b.name"
                (click)="edit({ brand: b })"
              >
                <mat-icon>edit</mat-icon>
              </button>
              <button
                mat-icon-button
                type="button"
                [matTooltip]="b.isActive ? 'Deactivate' : 'Activate'"
                [attr.aria-label]="
                  (b.isActive ? 'Deactivate ' : 'Activate ') + b.name
                "
                (click)="toggle(b)"
              >
                <mat-icon>{{ b.isActive ? 'block' : 'check_circle' }}</mat-icon>
              </button>
            </td>
          </ng-container>
          <tr mat-header-row *matHeaderRowDef="columns; sticky: true"></tr>
          <tr mat-row *matRowDef="let row; columns: columns"></tr>
          <tr class="mat-mdc-row" *matNoDataRow>
            <td class="empty" [attr.colspan]="columns.length">
              {{ loading() ? 'Loading…' : 'No brands yet.' }}
            </td>
          </tr>
        </table>
      </div>
    </div>
  `,
  styleUrl: './customer-list.page.scss',
})
export class BrandListPage {
  private readonly api = inject(BrandApi);
  private readonly dialog = inject(MatDialog);

  protected readonly brands = signal<BrandItem[]>([]);
  protected readonly loading = signal(true);
  protected readonly columns = [
    'name',
    'handles',
    'status',
    'actions',
  ];
  protected readonly activeSeverity = ACTIVE_SEVERITY;

  constructor() {
    this.reload();
  }

  protected handles(brand: BrandItem): string {
    return (
      [
        brand.handlesSales && 'Sales',
        brand.handlesService && 'Service',
        brand.handlesParts && 'Parts',
      ]
        .filter(Boolean)
        .join(', ') || '—'
    );
  }

  protected edit(data: BrandEditData): void {
    this.dialog
      .open(BrandEditDialog, { data, width: '30rem', autoFocus: 'dialog' })
      .afterClosed()
      .subscribe((saved) => {
        if (saved) this.reload();
      });
  }

  protected addCompany(): void {
    this.dialog.open(CompanyAddDialog, { width: '28rem', autoFocus: 'dialog' });
  }

  protected toggle(brand: BrandItem): void {
    this.api.setActive(brand, !brand.isActive).subscribe(() => this.reload());
  }

  private reload(): void {
    this.loading.set(true);
    this.api.list().subscribe({
      next: (brands) => {
        this.brands.set(brands);
        this.loading.set(false);
      },
      error: () => this.loading.set(false),
    });
  }
}
