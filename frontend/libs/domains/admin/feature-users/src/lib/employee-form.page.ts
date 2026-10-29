import {
  ChangeDetectionStrategy,
  Component,
  computed,
  effect,
  inject,
  input,
  signal,
  untracked,
} from '@angular/core';
import { toSignal } from '@angular/core/rxjs-interop';
import {
  AbstractControl,
  FormControl,
  NonNullableFormBuilder,
  ReactiveFormsModule,
  ValidationErrors,
  Validators,
} from '@angular/forms';
import {
  MatAutocomplete,
  MatAutocompleteTrigger,
} from '@angular/material/autocomplete';
import { MatButton, MatIconButton } from '@angular/material/button';
import {
  MatError,
  MatFormField,
  MatHint,
  MatLabel,
  MatPrefix,
  MatSuffix,
} from '@angular/material/form-field';
import { MatIcon } from '@angular/material/icon';
import { MatInput } from '@angular/material/input';
import { MatProgressBar } from '@angular/material/progress-bar';
import { MatOption, MatSelect } from '@angular/material/select';
import { Router, RouterLink } from '@angular/router';
import {
  EMPTY,
  Observable,
  catchError,
  debounceTime,
  distinctUntilChanged,
  filter,
  finalize,
  map,
  of,
  switchMap,
} from 'rxjs';
import {
  EMPLOYEE_MANAGE_PERMISSION,
  EMPLOYEE_TYPES,
  EmployeeDetail,
  EmployeeListItem,
  EmployeeType,
  EmployeesApi,
  HR_STATUSES,
  HrStatus,
} from '@trishul/admin-data-access';
import { AuthStore } from '@trishul/core-auth';
import { PageHeader, StatusBadge, StatusSeverity } from '@trishul/shared-ui';
import { TrishulValidators } from '@trishul/shared-util';
import { EmployeeActions } from './employee-actions';

/** A manager chosen from the picker (not just typed text). */
type ManagerChoice = Pick<
  EmployeeListItem,
  'id' | 'employeeCode' | 'firstName' | 'lastName' | 'designation'
>;
type ManagerValue = ManagerChoice | string;

const NONE = 0; // sentinel for optional number selects (mat-select shows null as blank)
const ACTIVE_SEVERITY: Record<string, StatusSeverity> = {
  Active: 'success',
  Inactive: 'neutral',
};

function orNull(id: number): number | null {
  return id === NONE ? null : id;
}

function managerLabel(m: ManagerChoice): string {
  const name = [m.firstName, m.lastName].filter(Boolean).join(' ');
  return [m.employeeCode, name, m.designation].filter(Boolean).join(' · ');
}

/** Empty, or a manager picked from the list (not just typed text). */
function pickedOrEmpty(control: AbstractControl): ValidationErrors | null {
  const value = control.value as ManagerValue;
  return typeof value === 'string' && value.trim() ? { notPicked: true } : null;
}

/** Add an employee (/admin/employees/new) or view and edit one (/admin/employees/:employeeId). */
@Component({
  selector: 'trishul-employee-form-page',
  imports: [
    ReactiveFormsModule,
    RouterLink,
    MatFormField,
    MatLabel,
    MatHint,
    MatError,
    MatPrefix,
    MatSuffix,
    MatInput,
    MatSelect,
    MatOption,
    MatAutocomplete,
    MatAutocompleteTrigger,
    MatButton,
    MatIconButton,
    MatIcon,
    MatProgressBar,
    PageHeader,
    StatusBadge,
  ],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './employee-form.page.html',
  styleUrl: './employee-form.page.scss',
})
export class EmployeeFormPage {
  private readonly api = inject(EmployeesApi);
  private readonly actions = inject(EmployeeActions);
  private readonly router = inject(Router);
  private readonly fb = inject(NonNullableFormBuilder);
  private readonly auth = inject(AuthStore);

  readonly employeeId = input<string>();

  protected readonly isNew = computed(() => !this.employeeId());
  protected readonly canManage = this.auth.hasPermission(
    EMPLOYEE_MANAGE_PERMISSION,
  );
  protected readonly employee = signal<EmployeeDetail | null>(null);
  protected readonly loading = signal(false);
  protected readonly saving = signal(false);
  protected readonly activeSeverity = ACTIVE_SEVERITY;
  protected readonly employeeTypes = EMPLOYEE_TYPES;
  protected readonly hrStatuses = HR_STATUSES;
  protected readonly NONE = NONE;
  protected readonly managerLabel = managerLabel;

  protected readonly branches = computed(
    () => this.auth.user()?.branches ?? [],
  );
  protected readonly companies = toSignal(
    this.api.companies().pipe(catchError(() => of([]))),
    { initialValue: [] },
  );
  protected readonly departments = toSignal(
    this.api.departments().pipe(catchError(() => of([]))),
    { initialValue: [] },
  );
  protected readonly designations = toSignal(
    this.api.designations().pipe(catchError(() => of([]))),
    { initialValue: [] },
  );

  protected readonly form = this.fb.group({
    employeeCode: this.fb.control('', [
      Validators.required,
      Validators.maxLength(20),
    ]),
    firstName: this.fb.control('', [
      Validators.required,
      Validators.maxLength(60),
    ]),
    lastName: new FormControl<string | null>(null, Validators.maxLength(60)),
    mobile: new FormControl<string | null>(null, TrishulValidators.mobile),
    email: new FormControl<string | null>(null, Validators.email),
    companyId: new FormControl<number | null>(null, Validators.required),
    branchId: new FormControl<number | null>(null, Validators.required),
    departmentId: this.fb.control<number>(NONE),
    designationId: this.fb.control<number>(NONE),
    manager: new FormControl<ManagerValue>('', {
      nonNullable: true,
      validators: pickedOrEmpty,
    }),
    employeeType: this.fb.control<EmployeeType>('Permanent'),
    status: this.fb.control<HrStatus>('Active'),
    dateOfJoining: new FormControl<string | null>(null),
    dateOfExit: new FormControl<string | null>(null),
    mobilePlatform: this.fb.control<string>(''),
  });

  /** Employees matching the manager search, excluding the employee being edited. */
  protected readonly managerOptions = toSignal(
    this.canManage
      ? this.form.controls.manager.valueChanges.pipe(
          filter((v): v is string => typeof v === 'string'),
          debounceTime(250),
          distinctUntilChanged(),
          switchMap((term): Observable<EmployeeListItem[]> =>
            this.api
              .list({ page: 1, pageSize: 20, status: 'active', search: term })
              .pipe(
                map((page) => page.items),
                catchError(() => of<EmployeeListItem[]>([])),
              ),
          ),
        )
      : of<EmployeeListItem[]>([]),
    { initialValue: [] as EmployeeListItem[] },
  );

  protected readonly managerList = computed(() =>
    (this.managerOptions() ?? []).filter((e) => e.id !== this.employee()?.id),
  );

  constructor() {
    if (!this.canManage) this.form.disable();
    effect(() => {
      const id = this.employeeId();
      untracked(() => (id ? this.load(Number(id)) : this.startNew()));
    });
  }

  protected readonly managerText = (value: ManagerValue | null): string =>
    !value ? '' : typeof value === 'string' ? value : managerLabel(value);

  protected onManagerPicked(_: EmployeeListItem): void {
    // nothing extra; the value is stored by the autocomplete
  }

  protected clearManager(): void {
    this.form.controls.manager.setValue('');
    this.form.markAsDirty();
  }

  protected save(): void {
    this.form.markAllAsTouched();
    if (this.form.invalid || this.saving()) return;
    const v = this.form.getRawValue();
    const managerId = typeof v.manager === 'string' ? null : v.manager.id;
    const body = {
      employeeCode: v.employeeCode.trim(),
      firstName: v.firstName.trim(),
      lastName: v.lastName?.trim() || null,
      mobile: v.mobile || null,
      email: v.email?.trim() || null,
      companyId: v.companyId as number,
      branchId: v.branchId as number,
      departmentId: orNull(v.departmentId),
      designationId: orNull(v.designationId),
      reportingManagerId: managerId,
      employeeType: v.employeeType,
      status: v.status,
      dateOfJoining: v.dateOfJoining || null,
      dateOfExit: v.dateOfExit || null,
      mobilePlatform: (v.mobilePlatform || null) as 'Android' | 'iOS' | null,
    };
    this.saving.set(true);
    const current = this.employee();
    const request = current
      ? this.api.update(current.id, current.rowVersion, body)
      : this.api.create(body);
    request
      .pipe(
        finalize(() => this.saving.set(false)),
        catchError(() => EMPTY), // the error toast has been shown
      )
      .subscribe((saved) => {
        this.actions.notify(
          current ? 'Changes saved' : `${saved.fullName} added`,
        );
        if (current) this.show(saved);
        else void this.router.navigate(['/admin/employees', saved.id]);
      });
  }

  protected deactivate(): void {
    const e = this.employee();
    if (e)
      this.actions.deactivate(e).subscribe((updated) => this.show(updated));
  }

  protected activate(): void {
    const e = this.employee();
    if (e) this.actions.activate(e).subscribe((updated) => this.show(updated));
  }

  private startNew(): void {
    this.employee.set(null);
    this.form.reset({
      employeeCode: '',
      firstName: '',
      lastName: null,
      mobile: null,
      email: null,
      companyId: this.companies().length === 1 ? this.companies()[0].id : null,
      branchId: this.auth.branchId() ?? null,
      departmentId: NONE,
      designationId: NONE,
      manager: '',
      employeeType: 'Permanent',
      status: 'Active',
      dateOfJoining: null,
      dateOfExit: null,
      mobilePlatform: '',
    });
    this.form.markAsPristine();
  }

  private load(id: number): void {
    this.loading.set(true);
    this.api
      .get(id)
      .pipe(
        finalize(() => this.loading.set(false)),
        catchError(() => {
          void this.router.navigate(['/admin/employees']);
          return EMPTY;
        }),
      )
      .subscribe((employee) => this.show(employee));
  }

  private show(employee: EmployeeDetail): void {
    this.employee.set(employee);
    this.form.reset({
      employeeCode: employee.employeeCode,
      firstName: employee.firstName,
      lastName: employee.lastName,
      mobile: employee.mobile,
      email: employee.email,
      companyId: employee.companyId,
      branchId: employee.branchId,
      departmentId: employee.departmentId ?? NONE,
      designationId: employee.designationId ?? NONE,
      manager:
        employee.reportingManagerId && employee.reportingManagerName
          ? {
              id: employee.reportingManagerId,
              employeeCode: '',
              firstName: employee.reportingManagerName,
              lastName: null,
              designation: null,
            }
          : '',
      employeeType: employee.employeeType,
      status: employee.status,
      dateOfJoining: employee.dateOfJoining,
      dateOfExit: employee.dateOfExit,
      mobilePlatform: employee.mobilePlatform ?? '',
    });
    if (!this.canManage) this.form.disable();
    this.form.markAsPristine();
  }
}
