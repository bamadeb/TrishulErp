import {
  ChangeDetectionStrategy,
  Component,
  DestroyRef,
  inject,
  signal,
} from '@angular/core';
import { DatePipe } from '@angular/common';
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
import { SalaryComponentListItem, SalaryComponentSummary } from '@trishul/core-api';
import { HasPermission } from '@trishul/core-auth';
import {
  CALCULATION_METHODS,
  COMPONENT_TYPES,
  CalculationMethod,
  ComponentStatus,
  ComponentType,
  SALARY_COMPONENT_MANAGE,
  SalaryComponentQuery,
  SalaryComponentsApi,
} from '@trishul/hr-data-access';
import { PageHeader, StatusBadge, confirmAction } from '@trishul/shared-ui';
import { SalaryComponentDialog } from './salary-component.dialog';

const EMPTY_SUMMARY: SalaryComponentSummary = {
  total: 0,
  earning: 0,
  deduction: 0,
  active: 0,
};

@Component({
  selector: 'trishul-salary-components-page',
  imports: [
    HasPermission,
    DatePipe,
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
  templateUrl: './salary-components.page.html',
  styleUrl: './salary-components.page.scss',
})
export class SalaryComponentsPage {
  private readonly api = inject(SalaryComponentsApi);
  private readonly dialog = inject(MatDialog);
  private readonly snackBar = inject(MatSnackBar);
  private readonly destroyRef = inject(DestroyRef);
  private readonly searchInput = new Subject<string>();

  protected readonly manage = SALARY_COMPONENT_MANAGE;
  protected readonly statusTones = { Active: 'success', Inactive: 'neutral' } as const;
  protected readonly types = COMPONENT_TYPES;
  protected readonly methods = CALCULATION_METHODS;
  protected readonly summary = signal<SalaryComponentSummary>(EMPTY_SUMMARY);
  protected readonly rows = signal<SalaryComponentListItem[]>([]);
  protected readonly total = signal(0);
  protected readonly loading = signal(true);
  protected readonly error = signal('');
  protected readonly query = signal<SalaryComponentQuery>({
    search: '',
    componentType: null,
    calculationMethod: null,
    status: 'all',
    page: 1,
    pageSize: 20,
  });

  constructor() {
    this.searchInput
      .pipe(debounceTime(300), distinctUntilChanged(), takeUntilDestroyed(this.destroyRef))
      .subscribe((search) => this.update({ search, page: 1 }));
    this.load(true);
  }

  protected yesNo(value: boolean): string {
    return value ? 'Yes' : 'No';
  }

  protected onSearch(value: string): void {
    this.query.update((current) => ({ ...current, search: value }));
    this.searchInput.next(value);
  }

  protected onType(componentType: ComponentType | null): void {
    this.update({ componentType, page: 1 });
  }

  protected onMethod(calculationMethod: CalculationMethod | null): void {
    this.update({ calculationMethod, page: 1 });
  }

  protected onStatus(status: ComponentStatus): void {
    this.update({ status, page: 1 });
  }

  protected selectCard(card: 'total' | 'earning' | 'deduction' | 'active'): void {
    if (card === 'earning') {
      this.update({ componentType: 'Earning', status: 'all', page: 1 });
    } else if (card === 'deduction') {
      this.update({ componentType: 'Employee Deduction', status: 'all', page: 1 });
    } else if (card === 'active') {
      this.update({ componentType: null, status: 'active', page: 1 });
    } else {
      this.update({ componentType: null, calculationMethod: null, status: 'all', search: '', page: 1 });
    }
  }

  protected clearFilters(): void {
    this.update({ search: '', componentType: null, calculationMethod: null, status: 'all', page: 1 });
  }

  protected onPage(event: PageEvent): void {
    this.update({ page: event.pageIndex + 1, pageSize: event.pageSize });
  }

  protected open(mode: 'create' | 'edit' | 'view', row?: SalaryComponentListItem): void {
    this.dialog
      .open(SalaryComponentDialog, {
        data: { mode, id: row?.id },
        width: '42rem',
        maxWidth: '100vw',
        height: '100vh',
        maxHeight: '100vh',
        position: { right: '0', top: '0' },
        autoFocus: 'dialog',
        panelClass: 'salary-component-drawer',
      })
      .afterClosed()
      .subscribe((saved) => {
        if (saved) {
          this.load(true);
        }
      });
  }

  protected toggle(row: SalaryComponentListItem): void {
    const next = !row.isActive;
    const run = () => {
      this.api.setStatus(row.id, row.rowVersion, next).subscribe({
        next: () => {
          this.snackBar.open(next ? 'Component activated.' : 'Component deactivated.', 'OK', { duration: 4000 });
          this.load(true);
        },
        error: () => undefined,
      });
    };
    if (next) {
      run();
      return;
    }
    confirmAction(this.dialog, {
      title: 'Deactivate component',
      message: `Deactivate ${row.name}? It will stay on past payroll and can be activated again.`,
      confirmText: 'Deactivate',
      destructive: true,
    }).subscribe((confirmed) => {
      if (confirmed) {
        run();
      }
    });
  }

  private update(change: Partial<SalaryComponentQuery>): void {
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
        this.error.set('Salary components could not be loaded.');
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
