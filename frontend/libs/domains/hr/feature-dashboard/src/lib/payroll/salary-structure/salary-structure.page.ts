import { DatePipe } from '@angular/common';
import { ChangeDetectionStrategy, Component, DestroyRef, inject, signal } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { MatButton, MatIconButton } from '@angular/material/button';
import { MatDialog } from '@angular/material/dialog';
import { MatFormField, MatLabel, MatPrefix } from '@angular/material/form-field';
import { MatIcon } from '@angular/material/icon';
import { MatInput } from '@angular/material/input';
import { MatPaginator, PageEvent } from '@angular/material/paginator';
import { MatProgressBar } from '@angular/material/progress-bar';
import { MatOption, MatSelect } from '@angular/material/select';
import { Subject, debounceTime, distinctUntilChanged } from 'rxjs';
import { SalaryStructureListItem, SalaryStructureSummary } from '@trishul/core-api';
import { HasPermission } from '@trishul/core-auth';
import {
  SALARY_STRUCTURE_MANAGE,
  SalaryStructureQuery,
  SalaryStructuresApi,
  StructureAssignment,
} from '@trishul/hr-data-access';
import { PageHeader, StatusBadge } from '@trishul/shared-ui';
import { SalaryStructureDialog } from './salary-structure.dialog';

const EMPTY_SUMMARY: SalaryStructureSummary = { employees: 0, assigned: 0, unassigned: 0, active: 0 };

@Component({
  selector: 'trishul-salary-structure-page',
  imports: [
    DatePipe,
    HasPermission,
    MatButton,
    MatFormField,
    MatIcon,
    MatIconButton,
    MatInput,
    MatLabel,
    MatOption,
    MatPaginator,
    MatPrefix,
    MatProgressBar,
    MatSelect,
    PageHeader,
    StatusBadge,
  ],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './salary-structure.page.html',
  styleUrl: './salary-structure.page.scss',
})
export class SalaryStructurePage {
  private readonly api = inject(SalaryStructuresApi);
  private readonly dialog = inject(MatDialog);
  private readonly destroyRef = inject(DestroyRef);
  private readonly searchInput = new Subject<string>();

  protected readonly manage = SALARY_STRUCTURE_MANAGE;
  protected readonly statusTones = { Assigned: 'success', 'Not assigned': 'neutral' } as const;
  protected readonly summary = signal<SalaryStructureSummary>(EMPTY_SUMMARY);
  protected readonly rows = signal<SalaryStructureListItem[]>([]);
  protected readonly total = signal(0);
  protected readonly loading = signal(true);
  protected readonly error = signal('');
  protected readonly query = signal<SalaryStructureQuery>({
    search: '',
    assignment: 'all',
    page: 1,
    pageSize: 20,
  });

  constructor() {
    this.searchInput
      .pipe(debounceTime(300), distinctUntilChanged(), takeUntilDestroyed(this.destroyRef))
      .subscribe((search) => this.update({ search, page: 1 }));
    this.load(true);
  }

  protected onSearch(value: string): void {
    this.searchInput.next(value);
  }

  protected onAssignment(assignment: StructureAssignment): void {
    this.update({ assignment, page: 1 });
  }

  protected selectCard(card: 'all' | 'assigned' | 'unassigned'): void {
    this.update({
      assignment: card === 'all' ? 'all' : card,
      search: card === 'all' ? '' : this.query().search,
      page: 1,
    });
  }

  protected clearFilters(): void {
    this.update({ search: '', assignment: 'all', page: 1 });
  }

  protected onPage(event: PageEvent): void {
    this.update({ page: event.pageIndex + 1, pageSize: event.pageSize });
  }

  protected money(value: string | null): string {
    if (value == null || value === '') return '—';
    const amount = Number(value);
    if (!Number.isFinite(amount)) return value;
    return amount.toLocaleString('en-IN', { style: 'currency', currency: 'INR', maximumFractionDigits: 2 });
  }

  protected open(mode: 'view' | 'edit', row: SalaryStructureListItem): void {
    this.dialog
      .open(SalaryStructureDialog, {
        data: { mode, employeeId: row.employeeId },
        width: '42rem',
        maxWidth: '100vw',
        height: '100vh',
        maxHeight: '100vh',
        position: { right: '0', top: '0' },
        panelClass: 'salary-component-drawer',
        autoFocus: 'dialog',
      })
      .afterClosed()
      .subscribe((saved) => {
        if (saved) this.load(true);
      });
  }

  private update(change: Partial<SalaryStructureQuery>): void {
    this.query.update((current) => ({ ...current, ...change }));
    this.load(false);
  }

  private load(includeSummary: boolean): void {
    this.loading.set(true);
    this.error.set('');
    this.api.list(this.query()).subscribe({
      next: (page) => {
        this.rows.set(page.items);
        this.total.set(page.total);
        this.loading.set(false);
      },
      error: () => {
        this.error.set('Salary structures could not be loaded.');
        this.loading.set(false);
      },
    });
    if (includeSummary) {
      this.api.summary().subscribe({
        next: (summary) => this.summary.set(summary),
        error: () => undefined,
      });
    }
  }
}
