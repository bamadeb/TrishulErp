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
import { MatSnackBar } from '@angular/material/snack-bar';
import { Subject, debounceTime, distinctUntilChanged } from 'rxjs';
import { HasPermission } from '@trishul/core-auth';
import {
  SALARY_COMPONENT_MANAGE,
  SalaryTemplateListItem,
  SalaryTemplateQuery,
  SalaryTemplateSummary,
  SalaryTemplatesApi,
} from '@trishul/hr-data-access';
import { PageHeader, StatusBadge } from '@trishul/shared-ui';
import { SalaryTemplateDialog } from './salary-template.dialog';

const EMPTY: SalaryTemplateSummary = {
  total: 0,
  active: 0,
  inactive: 0,
  assignedEmployees: 0,
  departments: [],
  designations: [],
};

@Component({
  selector: 'trishul-salary-templates-page',
  imports: [
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
  templateUrl: './salary-templates.page.html',
  styleUrl: './salary-templates.page.scss',
})
export class SalaryTemplatesPage {
  private readonly api = inject(SalaryTemplatesApi);
  private readonly dialog = inject(MatDialog);
  private readonly snackBar = inject(MatSnackBar);
  private readonly destroyRef = inject(DestroyRef);
  private readonly searchInput = new Subject<string>();

  protected readonly manage = SALARY_COMPONENT_MANAGE;
  protected readonly categories = ['Permanent', 'Contract', 'Trainee', 'Consultant'];
  protected readonly grades = ['E1', 'E2', 'E3', 'E4', 'E5', 'G1', 'G2', 'G3', 'G4', 'G5', 'G6'];
  protected readonly statusTones = { Active: 'success', Inactive: 'neutral' } as const;
  protected readonly summary = signal<SalaryTemplateSummary>(EMPTY);
  protected readonly rows = signal<SalaryTemplateListItem[]>([]);
  protected readonly total = signal(0);
  protected readonly loading = signal(true);
  protected readonly error = signal('');
  protected readonly query = signal<SalaryTemplateQuery>({
    search: '',
    status: 'all',
    departmentId: null,
    designationId: null,
    grade: null,
    employeeCategory: null,
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

  protected update(change: Partial<SalaryTemplateQuery>): void {
    this.query.update((current) => ({ ...current, ...change }));
    this.load(false);
  }

  protected onPage(event: PageEvent): void {
    this.update({ page: event.pageIndex + 1, pageSize: event.pageSize });
  }

  protected add(): void {
    this.open(null, 'edit');
  }

  protected open(row: SalaryTemplateListItem | null, mode: 'view' | 'edit'): void {
    this.dialog
      .open(SalaryTemplateDialog, {
        data: { id: row?.id ?? null, mode, summary: this.summary() },
        width: '48rem',
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

  protected toggle(row: SalaryTemplateListItem): void {
    this.api.setStatus(row.id, row.rowVersion, !row.isActive).subscribe({
      next: () => {
        this.snackBar.open(row.isActive ? 'Template deactivated.' : 'Template activated.', 'OK', { duration: 3000 });
        this.load(true);
      },
      error: (error: { error?: { detail?: string } }) => {
        const detail = error.error?.detail;
        this.snackBar.open(typeof detail === 'string' && detail ? detail : 'The template status could not be changed.', 'OK', {
          duration: 5000,
        });
      },
    });
  }

  private load(includeSummary: boolean): void {
    this.loading.set(true);
    this.error.set('');
    if (includeSummary) {
      this.api.summary().subscribe({
        next: (summary) => this.summary.set(summary),
        error: () => undefined,
      });
    }
    this.api.list(this.query()).subscribe({
      next: (page) => {
        this.rows.set(page.items);
        this.total.set(page.total);
        this.loading.set(false);
      },
      error: () => {
        this.error.set('Salary templates could not be loaded.');
        this.loading.set(false);
      },
    });
  }
}
