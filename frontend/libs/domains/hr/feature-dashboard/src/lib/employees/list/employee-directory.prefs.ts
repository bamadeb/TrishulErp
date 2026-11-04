import { Injectable, computed, inject, signal } from '@angular/core';
import { AuthStore } from '@trishul/core-auth';
import {
  EmployeeQuery,
  EmployeeStatusFilter,
  EmployeeType,
} from '@trishul/hr-data-access';

/** A table column the directory can show. Actions stay on the table and are not listed here. */
export interface EmployeeColumnDef {
  id: string;
  /** Short heading in the table. */
  header: string;
  /** Name in Customize Columns. */
  label: string;
  /** Query `sort` value. Omitted when the API cannot sort this column. */
  sort?: string;
  defaultVisible: boolean;
}

export const EMPLOYEE_COLUMNS: readonly EmployeeColumnDef[] = [
  { id: 'employeeCode', header: 'Code', label: 'Employee Code', sort: 'employeeCode', defaultVisible: true },
  { id: 'fullName', header: 'Name', label: 'Employee Name', sort: 'fullName', defaultVisible: true },
  { id: 'mobile', header: 'Mobile', label: 'Mobile', sort: 'mobile', defaultVisible: true },
  { id: 'email', header: 'Email', label: 'Email', sort: 'email', defaultVisible: false },
  { id: 'company', header: 'Company', label: 'Company', defaultVisible: false },
  { id: 'branch', header: 'Branch', label: 'Branch', sort: 'branch', defaultVisible: true },
  { id: 'department', header: 'Department', label: 'Department', sort: 'department', defaultVisible: true },
  { id: 'designation', header: 'Designation', label: 'Designation', sort: 'designation', defaultVisible: true },
  { id: 'grade', header: 'Grade', label: 'Grade', sort: 'grade', defaultVisible: false },
  { id: 'dateOfJoining', header: 'Date of joining', label: 'Date of Joining', sort: 'dateOfJoining', defaultVisible: false },
  { id: 'confirmationDate', header: 'Confirmation', label: 'Confirmation Date', defaultVisible: false },
  { id: 'employeeType', header: 'Type', label: 'Employment Type', sort: 'employeeType', defaultVisible: true },
  { id: 'status', header: 'Status', label: 'Status', defaultVisible: true },
  { id: 'employmentStatus', header: 'Employment status', label: 'Employment Status', sort: 'status', defaultVisible: false },
  { id: 'reportingManager', header: 'Reporting manager', label: 'Reporting Manager', defaultVisible: false },
  { id: 'gender', header: 'Gender', label: 'Gender', defaultVisible: false },
  { id: 'dateOfBirth', header: 'Date of birth', label: 'Date of Birth', defaultVisible: false },
  { id: 'yearsInService', header: 'Years in service', label: 'Years in Service', defaultVisible: false },
  { id: 'login', header: 'Login', label: 'Login', defaultVisible: true },
];

const COLUMN_IDS = new Set(EMPLOYEE_COLUMNS.map((column) => column.id));

export interface EmployeeViewFilters {
  status: EmployeeStatusFilter;
  lifecycle: 'all' | 'active' | 'probation' | 'notice' | 'exited' | 'archived';
  search: string;
  branchId: number | null;
  departmentId: number | null;
  designationId: number | null;
  employeeType: EmployeeType | null;
}

export interface EmployeeSavedView {
  id: string;
  name: string;
  builtin: boolean;
  columns: string[];
  filters: EmployeeViewFilters;
}

const EMPTY_FILTERS: EmployeeViewFilters = {
  status: 'all',
  lifecycle: 'all',
  search: '',
  branchId: null,
  departmentId: null,
  designationId: null,
  employeeType: null,
};

function columnsOf(ids: string[]): string[] {
  return ids.filter((id) => COLUMN_IDS.has(id));
}

const DEFAULT_COLUMNS = columnsOf(
  EMPLOYEE_COLUMNS.filter((column) => column.defaultVisible).map((column) => column.id),
);

function view(
  id: string,
  name: string,
  columnIds: string[],
  filters: EmployeeViewFilters = EMPTY_FILTERS,
): EmployeeSavedView {
  return { id, name, builtin: true, columns: columnsOf(columnIds), filters };
}

/** Column and filter presets. They do not contain employee rows. */
export const BUILTIN_VIEWS: readonly EmployeeSavedView[] = [
  view('default', 'Default', DEFAULT_COLUMNS),
  view('employee-master', 'Employee Master', [
    'employeeCode',
    'fullName',
    'department',
    'designation',
    'grade',
    'branch',
    'employeeType',
    'status',
    'dateOfJoining',
  ]),
  view('personal-details', 'Personal Details', [
    'fullName',
    'gender',
    'dateOfBirth',
    'mobile',
    'email',
  ]),
  view('contact-id', 'Contact & ID Proof', ['fullName', 'mobile', 'email']),
  view('employment-details', 'Employment Details', [
    'fullName',
    'employeeType',
    'employmentStatus',
    'dateOfJoining',
    'confirmationDate',
    'designation',
    'department',
    'reportingManager',
    'yearsInService',
  ]),
];

interface StoredPrefs {
  columns: string[];
  filters: EmployeeViewFilters;
  customViews: EmployeeSavedView[];
  defaultViewId: string;
  activeViewId: string;
  pageSize: number;
  sort: string;
}

const PAGE_SIZES = [10, 20, 50, 100];

/** Completed years from a joining date. The value is not stored in the database. */
export function yearsInService(iso: string | null | undefined): number | null {
  if (!iso) {
    return null;
  }
  const start = new Date(`${iso.slice(0, 10)}T00:00:00`);
  if (Number.isNaN(start.getTime())) {
    return null;
  }
  const today = new Date();
  let years = today.getFullYear() - start.getFullYear();
  const beforeAnniversary =
    today.getMonth() < start.getMonth() ||
    (today.getMonth() === start.getMonth() && today.getDate() < start.getDate());
  if (beforeAnniversary) {
    years -= 1;
  }
  return Math.max(years, 0);
}

function storageKey(userId: number | null): string {
  return `trishul.hr.employee-directory.${userId ?? 'signed-out'}`;
}

function read(userId: number | null): StoredPrefs {
  const fallback: StoredPrefs = {
    columns: DEFAULT_COLUMNS,
    filters: { ...EMPTY_FILTERS },
    customViews: [],
    defaultViewId: 'default',
    activeViewId: 'default',
    pageSize: 20,
    sort: 'fullName',
  };
  try {
    const raw = localStorage.getItem(storageKey(userId));
    if (!raw) {
      return fallback;
    }
    const parsed = JSON.parse(raw) as Partial<StoredPrefs>;
    return {
      columns: columnsOf(parsed.columns ?? DEFAULT_COLUMNS),
      filters: normalizeFilters(parsed.filters),
      customViews: (parsed.customViews ?? [])
        .filter((item) => item && !item.builtin && item.name && item.id)
        .map((item) => ({
          ...item,
          builtin: false,
          columns: columnsOf(item.columns ?? []),
          filters: normalizeFilters(item.filters),
        })),
      defaultViewId: parsed.defaultViewId || 'default',
      activeViewId: parsed.activeViewId || 'default',
      pageSize: PAGE_SIZES.includes(parsed.pageSize ?? 0) ? (parsed.pageSize as number) : 20,
      sort: parsed.sort || 'fullName',
    };
  } catch {
    return fallback;
  }
}

/**
 * Column layout and saved views for the signed-in user.
 * Stored in the browser so a refresh or a later sign-in on this machine keeps the layout.
 */
@Injectable({ providedIn: 'root' })
export class EmployeeDirectoryPrefs {
  private readonly auth = inject(AuthStore);
  private readonly stored = signal(read(this.auth.user()?.id ?? null));

  readonly columns = computed(() => this.stored().columns);
  readonly filters = computed(() => this.stored().filters);
  readonly pageSize = computed(() => this.stored().pageSize);
  readonly sort = computed(() => this.stored().sort);
  readonly activeViewId = computed(() => this.stored().activeViewId);
  readonly defaultViewId = computed(() => this.stored().defaultViewId);
  readonly views = computed<EmployeeSavedView[]>(() => [
    ...BUILTIN_VIEWS,
    ...this.stored().customViews,
  ]);

  query(): EmployeeQuery {
    const filters = this.filters();
    return {
      page: 1,
      pageSize: this.pageSize(),
      sort: this.sort(),
      status: 'all',
      lifecycle: filters.lifecycle,
      search: filters.search || undefined,
      branchId: filters.branchId ?? undefined,
      departmentId: filters.departmentId ?? undefined,
      designationId: filters.designationId ?? undefined,
      employeeType: filters.employeeType ?? undefined,
    };
  }

  patchFilters(change: Partial<EmployeeViewFilters>): void {
    this.update({ filters: { ...this.filters(), ...change } });
  }

  rememberList(change: { pageSize?: number; sort?: string }): void {
    this.update(change);
  }

  /** Returns whether the employee query changed. Column-only switches do not. */
  selectView(id: string): boolean {
    const next = this.views().find((item) => item.id === id);
    if (!next) {
      return false;
    }
    const filtersChanged = !sameFilters(this.filters(), next.filters);
    this.update({
      activeViewId: next.id,
      columns: next.columns,
      filters: { ...next.filters },
    });
    return filtersChanged;
  }

  applyColumns(columnIds: string[]): void {
    const next = columnsOf(columnIds);
    this.update({ columns: next.length ? next : DEFAULT_COLUMNS });
  }

  resetColumns(): string[] {
    return DEFAULT_COLUMNS;
  }

  saveCurrentView(name: string): void {
    const trimmed = name.trim();
    if (!trimmed) {
      return;
    }
    const active = this.views().find((item) => item.id === this.activeViewId());
    if (active && !active.builtin && active.name === trimmed) {
      this.overwriteActive();
      return;
    }
    const created: EmployeeSavedView = {
      id: `view-${crypto.randomUUID()}`,
      name: trimmed,
      builtin: false,
      columns: this.columns(),
      filters: { ...this.filters() },
    };
    this.update({
      customViews: [...this.stored().customViews, created],
      activeViewId: created.id,
    });
  }

  overwriteActive(): void {
    const id = this.activeViewId();
    this.update({
      customViews: this.stored().customViews.map((item) =>
        item.id === id
          ? { ...item, columns: this.columns(), filters: { ...this.filters() } }
          : item,
      ),
    });
  }

  rename(id: string, name: string): void {
    const trimmed = name.trim();
    if (!trimmed) {
      return;
    }
    this.update({
      customViews: this.stored().customViews.map((item) =>
        item.id === id ? { ...item, name: trimmed } : item,
      ),
    });
  }

  remove(id: string): void {
    const customViews = this.stored().customViews.filter((item) => item.id !== id);
    const activeGone = this.activeViewId() === id;
    const defaultGone = this.defaultViewId() === id;
    this.update({
      customViews,
      ...(activeGone ? { activeViewId: 'default', columns: DEFAULT_COLUMNS, filters: { ...EMPTY_FILTERS } } : {}),
      ...(defaultGone ? { defaultViewId: 'default' } : {}),
    });
  }

  setDefault(id: string): void {
    if (this.views().some((item) => item.id === id)) {
      this.update({ defaultViewId: id });
    }
  }

  private update(change: Partial<StoredPrefs>): void {
    const next = { ...this.stored(), ...change };
    this.stored.set(next);
    localStorage.setItem(storageKey(this.auth.user()?.id ?? null), JSON.stringify(next));
  }
}

function normalizeFilters(filters: Partial<EmployeeViewFilters> | undefined): EmployeeViewFilters {
  const merged: EmployeeViewFilters = { ...EMPTY_FILTERS, ...filters };
  if (!filters?.lifecycle) {
    merged.lifecycle =
      merged.status === 'inactive' ? 'archived' : merged.status === 'active' ? 'active' : 'all';
  }
  return merged;
}

function sameFilters(left: EmployeeViewFilters, right: EmployeeViewFilters): boolean {
  return (
    left.status === right.status &&
    left.lifecycle === right.lifecycle &&
    left.search === right.search &&
    left.branchId === right.branchId &&
    left.departmentId === right.departmentId &&
    left.designationId === right.designationId &&
    left.employeeType === right.employeeType
  );
}
