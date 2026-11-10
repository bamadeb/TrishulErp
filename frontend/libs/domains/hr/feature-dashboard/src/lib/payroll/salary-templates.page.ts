import { DatePipe } from '@angular/common';
import { ChangeDetectionStrategy, Component, computed, inject, signal } from '@angular/core';
import { MatButton, MatIconButton } from '@angular/material/button';
import { MatDialog } from '@angular/material/dialog';
import { MatFormField, MatLabel, MatPrefix } from '@angular/material/form-field';
import { MatIcon } from '@angular/material/icon';
import { MatInput } from '@angular/material/input';
import { MatProgressBar } from '@angular/material/progress-bar';
import { MatOption, MatSelect } from '@angular/material/select';
import { SalaryComponentListItem, SalaryComponentSummary } from '@trishul/core-api';
import {
  COMPONENT_TYPES,
  ComponentType,
  SalaryComponentsApi,
} from '@trishul/hr-data-access';
import { PageHeader, StatusBadge } from '@trishul/shared-ui';
import { SalaryComponentDialog } from './components/salary-component.dialog';

const EMPTY_SUMMARY: SalaryComponentSummary = { total: 0, earning: 0, deduction: 0, active: 0 };

@Component({
  selector: 'trishul-salary-templates-page',
  imports: [
    DatePipe,
    MatButton,
    MatFormField,
    MatIcon,
    MatIconButton,
    MatInput,
    MatLabel,
    MatOption,
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
  private readonly api = inject(SalaryComponentsApi);
  private readonly dialog = inject(MatDialog);

  protected readonly types = COMPONENT_TYPES;
  protected readonly statusTones = { Active: 'success', Inactive: 'neutral' } as const;
  protected readonly summary = signal<SalaryComponentSummary>(EMPTY_SUMMARY);
  protected readonly rows = signal<SalaryComponentListItem[]>([]);
  protected readonly loading = signal(true);
  protected readonly error = signal('');
  protected readonly search = signal('');
  protected readonly componentType = signal<ComponentType | null>(null);
  protected readonly activeOnly = signal(false);

  protected readonly groups = computed(() => {
    const search = this.search().trim().toLowerCase();
    const type = this.componentType();
    const activeOnly = this.activeOnly();
    const matched = this.rows().filter((row) => {
      if (activeOnly && !row.isActive) return false;
      if (type && row.componentType !== type) return false;
      if (!search) return true;
      return `${row.code} ${row.name}`.toLowerCase().includes(search);
    });
    return this.types
      .filter((item) => type == null || item === type)
      .map((item) => ({
        type: item,
        rows: matched.filter((row) => row.componentType === item),
      }))
      .filter((group) => group.rows.length > 0 || (type == null && !search));
  });

  constructor() {
    this.api.summary().subscribe({
      next: (summary) => this.summary.set(summary),
      error: () => undefined,
    });
    this.api
      .list({
        search: '',
        componentType: null,
        calculationMethod: null,
        status: 'all',
        page: 1,
        pageSize: 200,
      })
      .subscribe({
        next: (page) => {
          this.rows.set(page.items);
          this.loading.set(false);
        },
        error: () => {
          this.error.set('Salary components could not be loaded.');
          this.loading.set(false);
        },
      });
  }

  protected selectCard(card: 'total' | 'earning' | 'deduction' | 'active'): void {
    this.activeOnly.set(card === 'active');
    if (card === 'earning') this.componentType.set('Earning');
    else if (card === 'deduction') this.componentType.set('Employee Deduction');
    else this.componentType.set(null);
    if (card === 'total') this.search.set('');
  }

  protected clearFilters(): void {
    this.search.set('');
    this.componentType.set(null);
    this.activeOnly.set(false);
  }

  protected view(row: SalaryComponentListItem): void {
    this.dialog.open(SalaryComponentDialog, {
      data: { mode: 'view', id: row.id },
      width: '42rem',
      maxWidth: '100vw',
      height: '100vh',
      maxHeight: '100vh',
      position: { right: '0', top: '0' },
      panelClass: 'salary-component-drawer',
      autoFocus: 'dialog',
    });
  }
}
