import {
  ChangeDetectionStrategy,
  Component,
  computed,
  inject,
  signal,
} from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { MatButton, MatIconButton } from '@angular/material/button';
import { MatDialog } from '@angular/material/dialog';
import { MatFormField, MatPrefix } from '@angular/material/form-field';
import { MatIcon } from '@angular/material/icon';
import { MatInput } from '@angular/material/input';
import { MatMenu, MatMenuItem, MatMenuTrigger } from '@angular/material/menu';
import { MatProgressBar } from '@angular/material/progress-bar';
import { MatSnackBar } from '@angular/material/snack-bar';
import { EMPTY, Subject, catchError, debounceTime, distinctUntilChanged, filter } from 'rxjs';
import { AuthStore } from '@trishul/core-auth';
import {
  ORGANIZATION_MANAGE_PERMISSION,
  OrganizationApi,
  OrganizationStore,
  OrgStatus,
  OrgTabId,
} from '@trishul/hr-data-access';
import { PageHeader, StatusBadge, StatusSeverity, confirmAction } from '@trishul/shared-ui';
import { OrganizationRecordDialog } from './organization-record.dialog';
import { OrgRow, toRows } from './organization.rows';

interface OrgTab {
  id: OrgTabId;
  label: string;
  icon: string;
  noun: string;
  addLabel: string;
  search: string;
}

interface OrgCard {
  label: string;
  icon: string;
  tone: 'violet' | 'green' | 'orange' | 'blue' | 'cyan';
  count: number;
}

const TABS: readonly OrgTab[] = [
  {
    id: 'departments',
    label: 'Departments',
    icon: 'domain',
    noun: 'Departments',
    addLabel: 'Add Department',
    search: 'Search by department name or code',
  },
  {
    id: 'designations',
    label: 'Designations',
    icon: 'badge',
    noun: 'Designations',
    addLabel: 'Add Designation',
    search: 'Search by designation name or code',
  },
  {
    id: 'grades',
    label: 'Grades',
    icon: 'layers',
    noun: 'Grades',
    addLabel: 'Add Grade',
    search: 'Search by grade',
  },
  {
    id: 'locations',
    label: 'Locations / Branches',
    icon: 'location_on',
    noun: 'Locations',
    addLabel: 'Add Location',
    search: 'Search by location name or code',
  },
  {
    id: 'companies',
    label: 'Companies',
    icon: 'apartment',
    noun: 'Companies',
    addLabel: 'Add Company',
    search: 'Search by company name or code',
  },
  {
    id: 'hierarchy',
    label: 'Reporting Hierarchy',
    icon: 'account_tree',
    noun: 'Reporting levels',
    addLabel: 'Add Level',
    search: 'Search by employee or manager',
  },
];

const STATUS: Record<string, StatusSeverity> = {
  Active: 'success',
  Inactive: 'neutral',
  Notice: 'warn',
  Exited: 'neutral',
};

/** Organization masters loaded from /hr. The layout matches the approved screen. */
@Component({
  selector: 'trishul-organization-page',
  imports: [
    MatButton,
    MatIconButton,
    MatFormField,
    MatPrefix,
    MatIcon,
    MatInput,
    MatMenu,
    MatMenuItem,
    MatMenuTrigger,
    MatProgressBar,
    PageHeader,
    StatusBadge,
  ],
  providers: [OrganizationStore],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './organization.page.html',
  styleUrl: './organization.page.scss',
})
export class OrganizationPage {
  protected readonly store = inject(OrganizationStore);
  private readonly api = inject(OrganizationApi);
  private readonly dialog = inject(MatDialog);
  private readonly snackBar = inject(MatSnackBar);
  private readonly auth = inject(AuthStore);

  protected readonly tabs = TABS;
  protected readonly activeSeverity = STATUS;
  protected readonly canManage = this.auth.hasPermission(ORGANIZATION_MANAGE_PERMISSION);
  protected readonly search = signal('');

  protected readonly tab = computed(() => this.store.snapshot().tab);
  protected readonly current = computed(
    () => this.tabs.find((item) => item.id === this.tab()) ?? this.tabs[0],
  );
  protected readonly rows = computed(() => toRows(this.store.snapshot()));
  protected readonly cards = computed((): OrgCard[] => {
    const counts = this.store.counts();
    return [
      { label: 'Total Departments', icon: 'domain', tone: 'violet', count: counts.departments },
      { label: 'Total Designations', icon: 'groups', tone: 'green', count: counts.designations },
      { label: 'Total Grades', icon: 'layers', tone: 'orange', count: counts.grades },
      { label: 'Total Locations', icon: 'location_on', tone: 'blue', count: counts.locations },
      { label: 'Reporting Levels', icon: 'account_tree', tone: 'cyan', count: counts.hierarchy },
    ];
  });

  protected readonly pageIndex = computed(() => this.store.query().page - 1);
  protected readonly pageCount = computed(() =>
    Math.max(1, Math.ceil(this.store.total() / this.store.query().pageSize)),
  );
  protected readonly pages = computed(() => {
    const count = this.pageCount();
    const current = this.pageIndex();
    if (count <= 7) return Array.from({ length: count }, (_, index) => index);
    const start = Math.max(0, Math.min(current - 3, count - 7));
    return Array.from({ length: 7 }, (_, index) => start + index);
  });
  protected readonly rangeLabel = computed(() => {
    const total = this.store.total();
    if (!total) return '0 of 0';
    const start = this.pageIndex() * this.store.query().pageSize + 1;
    const end = Math.min(total, start + this.rows().length - 1);
    return `${start}–${end} of ${total}`;
  });

  private readonly search$ = new Subject<string>();

  constructor() {
    this.store.start();
    this.search$
      .pipe(debounceTime(350), distinctUntilChanged(), takeUntilDestroyed())
      .subscribe((search) => {
        if (search === this.search().trim()) this.store.updateQuery({ search });
      });
  }

  protected selectTab(id: OrgTabId): void {
    if (id === this.tab()) return;
    this.search.set('');
    this.store.selectTab(id);
  }

  protected onSearch(value: string): void {
    this.search.set(value);
    this.search$.next(value.trim());
  }

  protected onStatus(value: string): void {
    this.store.updateQuery({ status: value as OrgStatus });
  }

  protected onPageSize(value: string): void {
    this.store.updateQuery({ pageSize: Number(value) });
  }

  protected goTo(index: number): void {
    const next = Math.min(Math.max(index, 0), this.pageCount() - 1);
    this.store.updateQuery({ page: next + 1 });
  }

  protected rowNumber(index: number): number {
    return this.pageIndex() * this.store.query().pageSize + index + 1;
  }

  protected nameHeading(): string {
    if (this.tab() === 'departments') return 'Department Name';
    if (this.tab() === 'grades') return 'Designations';
    return 'Name';
  }

  protected extraHeading(): string {
    return this.tab() === 'designations' ? 'Department' : 'Type';
  }

  protected headHeading(): string {
    const tab = this.tab();
    if (tab === 'designations') return 'Grade';
    if (tab === 'locations') return 'State';
    if (tab === 'companies') return 'Trade name';
    return 'Head of Department';
  }

  protected open(mode: 'create' | 'edit' | 'view', row?: OrgRow): void {
    this.dialog
      .open(OrganizationRecordDialog, {
        data: { tab: this.tab(), mode, id: row?.id },
        width: '36rem',
        autoFocus: 'dialog',
      })
      .afterClosed()
      .subscribe((saved) => {
        if (saved) this.store.reload();
      });
  }

  protected toggle(row: OrgRow): void {
    if (!row.canToggle || typeof row.id !== 'number') return;
    const id = row.id;
    const next = !row.active;
    const apply = (): void => {
      this.api
        .setActive(this.tab(), id, next)
        .pipe(catchError(() => EMPTY))
        .subscribe(() => {
          this.snackBar.open(`${row.name} ${next ? 'activated' : 'deactivated'}`, 'OK', {
            duration: 5000,
          });
          this.store.reload();
        });
    };
    if (next) {
      apply();
      return;
    }
    confirmAction(this.dialog, {
      title: `Deactivate ${row.name}?`,
      message: `${row.code} will be hidden from active lists. You can activate it again later.`,
      confirmText: 'Deactivate',
      destructive: true,
    })
      .pipe(filter(Boolean))
      .subscribe(() => apply());
  }
}
