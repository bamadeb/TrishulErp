import { ChangeDetectionStrategy, Component, computed, inject, signal } from '@angular/core';
import { MatButton } from '@angular/material/button';
import {
  MAT_DIALOG_DATA,
  MatDialogActions,
  MatDialogClose,
  MatDialogContent,
  MatDialogRef,
  MatDialogTitle,
} from '@angular/material/dialog';
import { MatFormField, MatLabel } from '@angular/material/form-field';
import { MatInput } from '@angular/material/input';
import { MatProgressBar } from '@angular/material/progress-bar';
import { MatOption, MatSelect, MatSelectChange } from '@angular/material/select';
import { MatSnackBar } from '@angular/material/snack-bar';
import { EMPTY, Observable, catchError, forkJoin, of, tap } from 'rxjs';
import {
  BranchListItem,
  CompanyOption,
  DepartmentOption,
  DesignationOption,
  EmployeeListItem,
  GradeDesignation,
  StateOption,
} from '@trishul/core-api';
import { OrganizationApi, OrgTabId } from '@trishul/hr-data-access';

export type OrgDialogMode = 'create' | 'edit' | 'view';

export interface OrgDialogData {
  tab: OrgTabId;
  mode: OrgDialogMode;
  id?: number | string;
}

interface OrgForm {
  code: string;
  name: string;
  parentDepartmentId: number | null;
  headEmployeeId: number | null;
  grade: string;
  departmentId: number | null;
  designationId: number | null;
  branchType: '' | 'Head office' | 'Warehouse' | 'Branch' | 'Service point';
  companyId: number | null;
  stateId: number | null;
  parentWarehouseId: number | null;
  address: string;
  phone: string;
  email: string;
  legalName: string;
  tradeName: string;
  pan: string;
  cin: string;
  logoUrl: string;
  fiscalYearStartMonth: number;
  employeeId: number | null;
  reportingManagerId: number | null;
}

interface ViewLine {
  label: string;
  value: string;
}

const BRANCH_TYPES = ['Head office', 'Warehouse', 'Branch', 'Service point'] as const;

const NOUN: Record<OrgTabId, string> = {
  departments: 'department',
  designations: 'designation',
  grades: 'grade',
  locations: 'location',
  companies: 'company',
  hierarchy: 'reporting link',
};

function blankForm(): OrgForm {
  return {
    code: '',
    name: '',
    parentDepartmentId: null,
    headEmployeeId: null,
    grade: '',
    departmentId: null,
    designationId: null,
    branchType: '',
    companyId: null,
    stateId: null,
    parentWarehouseId: null,
    address: '',
    phone: '',
    email: '',
    legalName: '',
    tradeName: '',
    pan: '',
    cin: '',
    logoUrl: '',
    fiscalYearStartMonth: 4,
    employeeId: null,
    reportingManagerId: null,
  };
}

function text(value: string): string | null {
  const trimmed = value.trim();
  return trimmed ? trimmed : null;
}

function shown(value: string | number | null | undefined): string {
  if (value === null || value === undefined || value === '') return '—';
  return String(value);
}

/** Add, edit, or view one organization record. The page reloads after a successful save. */
@Component({
  selector: 'trishul-organization-record-dialog',
  imports: [
    MatButton,
    MatDialogTitle,
    MatDialogContent,
    MatDialogActions,
    MatDialogClose,
    MatFormField,
    MatLabel,
    MatInput,
    MatSelect,
    MatOption,
    MatProgressBar,
  ],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './organization-record.dialog.html',
  styleUrl: './organization-record.dialog.scss',
})
export class OrganizationRecordDialog {
  protected readonly data = inject<OrgDialogData>(MAT_DIALOG_DATA);
  private readonly dialogRef = inject(MatDialogRef<OrganizationRecordDialog, boolean>);
  private readonly api = inject(OrganizationApi);
  private readonly snackBar = inject(MatSnackBar);

  protected readonly branchTypes = BRANCH_TYPES;
  protected readonly loading = signal(true);
  protected readonly saving = signal(false);
  protected readonly form = signal<OrgForm>(blankForm());
  protected readonly lines = signal<ViewLine[]>([]);
  protected readonly gradeDesignations = signal<GradeDesignation[]>([]);
  protected readonly departments = signal<DepartmentOption[]>([]);
  protected readonly designations = signal<DesignationOption[]>([]);
  protected readonly companies = signal<CompanyOption[]>([]);
  protected readonly states = signal<StateOption[]>([]);
  protected readonly employees = signal<EmployeeListItem[]>([]);
  protected readonly branches = signal<BranchListItem[]>([]);
  private rowVersion = '';

  protected readonly title = computed(() => {
    const noun = NOUN[this.data.tab];
    if (this.data.mode === 'create') return `Add ${noun}`;
    if (this.data.mode === 'edit') return `Edit ${noun}`;
    return noun[0].toUpperCase() + noun.slice(1);
  });

  protected readonly canSave = computed(() => {
    if (this.loading() || this.saving()) return false;
    const form = this.form();
    switch (this.data.tab) {
      case 'departments':
        return form.code.trim().length > 0 && form.name.trim().length > 0;
      case 'designations':
        return form.code.trim().length > 0 && form.name.trim().length > 0;
      case 'grades':
        return form.grade.trim().length > 0 && (this.data.mode === 'edit' || form.designationId !== null);
      case 'locations':
        return (
          form.code.trim().length > 0 &&
          form.name.trim().length > 0 &&
          form.branchType !== '' &&
          form.companyId !== null &&
          form.stateId !== null
        );
      case 'companies':
        return form.code.trim().length > 0 && form.legalName.trim().length > 0;
      case 'hierarchy':
        return this.data.mode === 'edit' || form.employeeId !== null;
    }
  });

  constructor() {
    const detail = this.loadDetail();
    const options = this.data.mode === 'view' ? of(undefined) : this.loadOptions();
    forkJoin({ detail, options }).subscribe({
      next: () => this.loading.set(false),
      error: () => this.dialogRef.close(false),
    });
  }

  protected setText<K extends 'code' | 'name' | 'grade' | 'address' | 'phone' | 'email' | 'legalName' | 'tradeName' | 'pan' | 'cin' | 'logoUrl'>(
    field: K,
    event: Event,
  ): void {
    const value = (event.target as HTMLInputElement).value;
    this.form.update((form) => ({ ...form, [field]: value }));
  }

  protected setMonth(event: Event): void {
    const value = Number((event.target as HTMLInputElement).value);
    this.form.update((form) => ({ ...form, fiscalYearStartMonth: value }));
  }

  protected setId(
    field:
      | 'parentDepartmentId'
      | 'headEmployeeId'
      | 'departmentId'
      | 'designationId'
      | 'companyId'
      | 'stateId'
      | 'parentWarehouseId'
      | 'employeeId'
      | 'reportingManagerId',
    event: MatSelectChange,
  ): void {
    this.form.update((form) => ({ ...form, [field]: event.value as number | null }));
  }

  protected setBranchType(event: MatSelectChange): void {
    this.form.update((form) => ({ ...form, branchType: event.value as OrgForm['branchType'] }));
  }

  protected save(): void {
    const request = this.buildRequest();
    if (!request) return;
    this.saving.set(true);
    request
      .pipe(
        tap(() => {
          const noun = NOUN[this.data.tab];
          this.snackBar.open(`${noun[0].toUpperCase()}${noun.slice(1)} saved`, 'OK', { duration: 5000 });
          this.dialogRef.close(true);
        }),
        catchError(() => {
          this.saving.set(false);
          return EMPTY;
        }),
      )
      .subscribe();
  }

  private loadDetail(): Observable<unknown> {
    if (this.data.mode === 'create' || this.data.id === undefined) return of(null);
    switch (this.data.tab) {
      case 'departments':
        return this.api.getDepartment(Number(this.data.id)).pipe(
          tap((row) => {
            this.rowVersion = row.rowVersion;
            this.form.update((form) => ({
              ...form,
              code: row.code,
              name: row.name,
              parentDepartmentId: row.parentDepartmentId,
              headEmployeeId: row.headEmployeeId,
            }));
            this.lines.set([
              { label: 'Code', value: row.code },
              { label: 'Name', value: row.name },
              { label: 'Parent department', value: shown(row.parentDepartmentName) },
              { label: 'Head of department', value: shown(row.headName) },
              { label: 'Employees', value: String(row.employeeCount) },
              { label: 'Status', value: row.isActive ? 'Active' : 'Inactive' },
            ]);
          }),
        );
      case 'designations':
        return this.api.getDesignation(Number(this.data.id)).pipe(
          tap((row) => {
            this.rowVersion = row.rowVersion;
            this.form.update((form) => ({
              ...form,
              code: row.code,
              name: row.name,
              grade: row.grade ?? '',
              departmentId: row.departmentId,
            }));
            this.lines.set([
              { label: 'Code', value: row.code },
              { label: 'Name', value: row.name },
              { label: 'Grade', value: shown(row.grade) },
              { label: 'Department', value: shown(row.departmentName) },
              { label: 'Employees', value: String(row.employeeCount) },
              { label: 'Status', value: row.isActive ? 'Active' : 'Inactive' },
            ]);
          }),
        );
      case 'grades':
        return this.api.getGrade(String(this.data.id)).pipe(
          tap((row) => {
            this.form.update((form) => ({ ...form, grade: row.grade }));
            this.gradeDesignations.set(row.designations);
            this.lines.set([
              { label: 'Grade', value: row.grade },
              { label: 'Designations', value: String(row.designationCount) },
              { label: 'Employees', value: String(row.employeeCount) },
            ]);
          }),
        );
      case 'locations':
        return this.api.getBranch(Number(this.data.id)).pipe(
          tap((row) => {
            this.rowVersion = row.rowVersion;
            this.form.update((form) => ({
              ...form,
              code: row.code,
              name: row.name,
              branchType: row.branchType,
              companyId: row.companyId,
              stateId: row.stateId,
              parentWarehouseId: row.parentWarehouseId,
              address: row.address ?? '',
              phone: row.phone ?? '',
              email: row.email ?? '',
            }));
            this.lines.set([
              { label: 'Code', value: row.code },
              { label: 'Name', value: row.name },
              { label: 'Type', value: row.branchType },
              { label: 'Company', value: shown(row.companyName) },
              { label: 'State', value: shown(row.stateName) },
              { label: 'Parent warehouse', value: shown(row.parentWarehouseName) },
              { label: 'Address', value: shown(row.address) },
              { label: 'Phone', value: shown(row.phone) },
              { label: 'Email', value: shown(row.email) },
              { label: 'Employees', value: String(row.employeeCount) },
              { label: 'Status', value: row.isActive ? 'Active' : 'Inactive' },
            ]);
          }),
        );
      case 'companies':
        return this.api.getCompany(Number(this.data.id)).pipe(
          tap((row) => {
            this.rowVersion = row.rowVersion;
            this.form.update((form) => ({
              ...form,
              code: row.code,
              legalName: row.legalName,
              tradeName: row.tradeName ?? '',
              pan: row.pan ?? '',
              cin: row.cin ?? '',
              address: row.address ?? '',
              stateId: row.stateId,
              logoUrl: row.logoUrl ?? '',
              fiscalYearStartMonth: row.fiscalYearStartMonth,
            }));
            this.lines.set([
              { label: 'Code', value: row.code },
              { label: 'Legal name', value: row.legalName },
              { label: 'Trade name', value: shown(row.tradeName) },
              { label: 'PAN', value: shown(row.pan) },
              { label: 'CIN', value: shown(row.cin) },
              { label: 'State', value: shown(row.stateName) },
              { label: 'Address', value: shown(row.address) },
              { label: 'Fiscal year starts', value: `Month ${row.fiscalYearStartMonth}` },
              { label: 'Employees', value: String(row.employeeCount) },
              { label: 'Status', value: row.isActive ? 'Active' : 'Inactive' },
            ]);
          }),
        );
      case 'hierarchy':
        return this.api.getHierarchyMember(Number(this.data.id)).pipe(
          tap((row) => {
            this.rowVersion = row.rowVersion;
            this.form.update((form) => ({
              ...form,
              employeeId: row.id,
              reportingManagerId: row.reportingManagerId,
            }));
            this.lines.set([
              { label: 'Employee', value: `${row.fullName} (${row.employeeCode})` },
              { label: 'Reports to', value: shown(row.reportingManagerName) },
              { label: 'Department', value: shown(row.departmentName) },
              { label: 'Designation', value: shown(row.designationName) },
              { label: 'Grade', value: shown(row.grade) },
              { label: 'Company', value: shown(row.companyName) },
              { label: 'Location', value: shown(row.branchName) },
              { label: 'Direct reports', value: String(row.directReportCount) },
              { label: 'Status', value: row.isActive ? row.status : 'Inactive' },
            ]);
          }),
        );
    }
  }

  private loadOptions(): Observable<unknown> {
    const empty = <T>(source: Observable<T[]>): Observable<T[]> => source.pipe(catchError(() => of([])));
    switch (this.data.tab) {
      case 'departments':
        return forkJoin({
          departments: empty(this.api.departmentOptions()).pipe(tap((rows) => this.departments.set(rows))),
          employees: empty(this.api.employeeOptions()).pipe(tap((rows) => this.employees.set(rows))),
        });
      case 'designations':
        return empty(this.api.departmentOptions()).pipe(tap((rows) => this.departments.set(rows)));
      case 'grades':
        return this.data.mode === 'edit'
          ? of(null)
          : empty(this.api.designationOptions()).pipe(tap((rows) => this.designations.set(rows)));
      case 'locations':
        return forkJoin({
          companies: empty(this.api.companyOptions()).pipe(tap((rows) => this.companies.set(rows))),
          states: empty(this.api.stateOptions()).pipe(tap((rows) => this.states.set(rows))),
          branches: this.api.listBranches({ page: 1, pageSize: 200, search: '', status: 'active' }).pipe(
            tap((page) => this.branches.set(page.items)),
            catchError(() => of(null)),
          ),
        });
      case 'companies':
        return empty(this.api.stateOptions()).pipe(tap((rows) => this.states.set(rows)));
      case 'hierarchy':
        return empty(this.api.employeeOptions()).pipe(tap((rows) => this.employees.set(rows)));
    }
  }

  private buildRequest(): Observable<unknown> | null {
    const form = this.form();
    switch (this.data.tab) {
      case 'departments': {
        const body = {
          code: form.code.trim(),
          name: form.name.trim(),
          parentDepartmentId: form.parentDepartmentId,
          headEmployeeId: form.headEmployeeId,
        };
        return this.data.mode === 'create'
          ? this.api.createDepartment(body)
          : this.api.updateDepartment(Number(this.data.id), this.rowVersion, body);
      }
      case 'designations': {
        const body = {
          code: form.code.trim(),
          name: form.name.trim(),
          grade: text(form.grade),
          departmentId: form.departmentId,
        };
        return this.data.mode === 'create'
          ? this.api.createDesignation(body)
          : this.api.updateDesignation(Number(this.data.id), this.rowVersion, body);
      }
      case 'grades':
        return this.data.mode === 'create'
          ? this.api.createGrade({ grade: form.grade.trim(), designationId: form.designationId ?? 0 })
          : this.api.renameGrade(String(this.data.id), form.grade.trim());
      case 'locations': {
        if (form.branchType === '' || form.companyId === null || form.stateId === null) return null;
        const body = {
          code: form.code.trim(),
          name: form.name.trim(),
          branchType: form.branchType,
          companyId: form.companyId,
          stateId: form.stateId,
          parentWarehouseId: form.parentWarehouseId,
          address: text(form.address),
          phone: text(form.phone),
          email: text(form.email),
        };
        return this.data.mode === 'create'
          ? this.api.createBranch(body)
          : this.api.updateBranch(Number(this.data.id), this.rowVersion, body);
      }
      case 'companies': {
        const body = {
          code: form.code.trim(),
          legalName: form.legalName.trim(),
          tradeName: text(form.tradeName),
          pan: text(form.pan),
          cin: text(form.cin),
          address: text(form.address),
          stateId: form.stateId,
          logoUrl: text(form.logoUrl),
          fiscalYearStartMonth: form.fiscalYearStartMonth,
        };
        return this.data.mode === 'create'
          ? this.api.createCompany(body)
          : this.api.updateCompany(Number(this.data.id), this.rowVersion, body);
      }
      case 'hierarchy':
        return this.data.mode === 'create'
          ? this.api.createHierarchyLink({
              employeeId: form.employeeId ?? 0,
              reportingManagerId: form.reportingManagerId,
            })
          : this.api.updateHierarchy(Number(this.data.id), this.rowVersion, {
              reportingManagerId: form.reportingManagerId,
            });
    }
  }
}
