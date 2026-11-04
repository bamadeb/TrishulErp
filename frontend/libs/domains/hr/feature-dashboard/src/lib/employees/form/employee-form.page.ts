import {
  ChangeDetectionStrategy,
  Component,
  computed,
  effect,
  inject,
  input,
  NgZone,
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
import { MatCheckbox } from '@angular/material/checkbox';
import { provideNativeDateAdapter } from '@angular/material/core';
import {
  MatDatepicker,
  MatDatepickerInput,
  MatDatepickerToggle,
} from '@angular/material/datepicker';
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
} from '@trishul/hr-data-access';
import { AuthStore } from '@trishul/core-auth';
import { StatusBadge, StatusSeverity } from '@trishul/shared-ui';
import { TrishulValidators } from '@trishul/shared-util';
import { EmployeeActions } from '../employee-actions';

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
const STEP_FIELDS: readonly (readonly string[])[] = [
  ['employeeCode', 'firstName', 'lastName', 'mobile', 'email', 'personalEmail'],
  ['companyId', 'branchId', 'departmentId', 'designationId', 'manager'],
  ['employeeType', 'status', 'dateOfJoining', 'dateOfExit', 'mobilePlatform'],
  ['emergencyPhone'],
];

function orNull(id: number): number | null {
  return id === NONE ? null : id;
}

/** Calendar date from an API date string, without a timezone shift. */
function parseIsoDate(value: string | null): Date | null {
  const match = /^(\d{4})-(\d{2})-(\d{2})/.exec(value ?? '');
  return match
    ? new Date(Number(match[1]), Number(match[2]) - 1, Number(match[3]))
    : null;
}

function formatIsoDate(value: Date | null): string | null {
  if (!value || Number.isNaN(value.getTime())) return null;
  const month = String(value.getMonth() + 1).padStart(2, '0');
  const day = String(value.getDate()).padStart(2, '0');
  return `${value.getFullYear()}-${month}-${day}`;
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

/** Add an employee (/hr/employees/new) or view and edit one (/hr/employees/:employeeId). */
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
    MatCheckbox,
    MatDatepicker,
    MatDatepickerInput,
    MatDatepickerToggle,
    MatIcon,
    MatProgressBar,
    StatusBadge,
  ],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './employee-form.page.html',
  styleUrl: './employee-form.page.scss',
  providers: [provideNativeDateAdapter()],
})
export class EmployeeFormPage {
  private readonly api = inject(EmployeesApi);
  private readonly actions = inject(EmployeeActions);
  private readonly router = inject(Router);
  private readonly fb = inject(NonNullableFormBuilder);
  private readonly auth = inject(AuthStore);
  private readonly zone = inject(NgZone);

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
  protected readonly steps = [
    { label: 'Personal Details' },
    { label: 'Organization' },
    { label: 'Employment' },
    { label: 'Additional Details' },
    { label: 'Documents & Onboarding' },
  ];
  protected readonly genders = ['Male', 'Female', 'Other'] as const;
  protected readonly bloodGroups = ['A+', 'A-', 'B+', 'B-', 'O+', 'O-', 'AB+', 'AB-'] as const;
  protected readonly step = signal(0);
  protected readonly sameAddress = signal(true);
  protected readonly photoUrl = signal<string | null>(null);
  protected readonly photoToSave = signal<string | null>(null);
  protected readonly photoError = signal<string | null>(null);
  protected readonly documents = signal<{ name: string }[]>([]);
  protected readonly today = new Date();

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
    dateOfJoining: new FormControl<Date | null>(null),
    dateOfExit: new FormControl<Date | null>(null),
    mobilePlatform: this.fb.control<string>(''),
    gender: this.fb.control(''),
    dateOfBirth: new FormControl<Date | null>(null),
    bloodGroup: this.fb.control(''),
    personalEmail: new FormControl<string | null>(null, Validators.email),
    currentAddress: this.fb.control('', Validators.maxLength(250)),
    permanentAddress: this.fb.control({ value: '', disabled: true }, Validators.maxLength(250)),
    maritalStatus: this.fb.control(''),
    nationality: this.fb.control(''),
    emergencyName: this.fb.control(''),
    emergencyPhone: new FormControl<string | null>(null, TrishulValidators.mobile),
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
    this.form.controls.currentAddress.valueChanges.subscribe((value) => {
      if (this.sameAddress()) {
        this.form.controls.permanentAddress.setValue(value, { emitEvent: false });
      }
    });
    effect(() => {
      const id = this.employeeId();
      untracked(() => (id ? this.load(Number(id)) : this.startNew()));
    });
  }

  protected goTo(index: number): void {
    this.step.set(index);
  }

  protected continue(): void {
    if (!this.markStep(this.step())) return;
    if (this.step() === this.steps.length - 1) this.save();
    else this.step.update((current) => current + 1);
  }

  protected toggleSameAddress(checked: boolean): void {
    if (!this.canManage) return;
    this.sameAddress.set(checked);
    this.applySameAddress();
  }

  protected onPhoto(event: Event): void {
    const input = event.target as HTMLInputElement;
    const file = input.files?.[0];
    input.value = '';
    if (!file) return;
    const looksLikeImage =
      file.type.startsWith('image/') || /\.(jpe?g|png|webp|gif|bmp)$/i.test(file.name);
    if (!looksLikeImage) {
      this.photoError.set('Choose a JPG or PNG picture.');
      return;
    }
    if (file.size > 15 * 1024 * 1024) {
      this.photoError.set('That picture is too large. Use one under 15 MB.');
      return;
    }
    this.photoError.set(null);
    const reader = new FileReader();
    reader.onload = () => this.zone.run(() => this.showPhoto(String(reader.result ?? '')));
    reader.onerror = () => this.zone.run(() => this.photoError.set('That picture could not be opened.'));
    reader.readAsDataURL(file);
  }

  private showPhoto(dataUrl: string): void {
    const image = new Image();
    image.onload = () =>
      this.zone.run(() => {
        const max = 480;
        const scale = Math.min(1, max / Math.max(image.width, image.height, 1));
        const canvas = document.createElement('canvas');
        canvas.width = Math.max(1, Math.round(image.width * scale));
        canvas.height = Math.max(1, Math.round(image.height * scale));
        const context = canvas.getContext('2d');
        const saved = context ? this.drawPhoto(context, image, canvas) : dataUrl;
        this.photoUrl.set(saved);
        this.photoToSave.set(saved);
      });
    image.onerror = () => this.zone.run(() => this.photoError.set('That picture could not be opened.'));
    image.src = dataUrl;
  }

  private drawPhoto(context: CanvasRenderingContext2D, image: HTMLImageElement, canvas: HTMLCanvasElement): string {
    context.drawImage(image, 0, 0, canvas.width, canvas.height);
    return canvas.toDataURL('image/jpeg', 0.92);
  }

  protected onDocuments(event: Event): void {
    const input = event.target as HTMLInputElement;
    const files = Array.from(input.files ?? []);
    input.value = '';
    if (!files.length) return;
    this.documents.update((current) => [
      ...current,
      ...files.map((file) => ({ name: file.name })),
    ]);
  }

  protected removeDocument(index: number): void {
    this.documents.update((current) => current.filter((_, i) => i !== index));
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
    if (this.form.invalid || this.saving()) {
      this.focusInvalidStep();
      return;
    }
    const v = this.form.getRawValue();
    const managerId = typeof v.manager === 'string' ? null : v.manager.id;
    const selectedGender = v.gender;
    const gender: 'Male' | 'Female' | 'Other' | null =
      selectedGender === 'Male' || selectedGender === 'Female' || selectedGender === 'Other'
        ? selectedGender
        : null;
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
      dateOfJoining: formatIsoDate(v.dateOfJoining),
      dateOfExit: formatIsoDate(v.dateOfExit),
      mobilePlatform: (v.mobilePlatform || null) as 'Android' | 'iOS' | null,
      dateOfBirth: formatIsoDate(v.dateOfBirth),
      gender,
      personalEmail: v.personalEmail?.trim() || null,
      currentAddress: v.currentAddress.trim() || null,
      permanentAddress:
        (this.sameAddress() ? v.currentAddress : v.permanentAddress).trim() || null,
      emergencyContactName: v.emergencyName.trim() || null,
      emergencyContactPhone: v.emergencyPhone || null,
      ...(this.photoToSave() ? { photo: this.photoToSave() } : {}),
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
        else void this.router.navigate(['/hr/employees', saved.id]);
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
      gender: '',
      dateOfBirth: null,
      bloodGroup: '',
      personalEmail: null,
      currentAddress: '',
      permanentAddress: '',
      maritalStatus: '',
      nationality: '',
      emergencyName: '',
      emergencyPhone: null,
    });
    this.sameAddress.set(true);
    this.clearScreenOnly();
    this.finishEditState();
  }

  private load(id: number): void {
    this.loading.set(true);
    this.api
      .get(id)
      .pipe(
        finalize(() => this.loading.set(false)),
        catchError(() => {
          void this.router.navigate(['/hr/employees']);
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
      dateOfJoining: parseIsoDate(employee.dateOfJoining),
      dateOfExit: parseIsoDate(employee.dateOfExit),
      mobilePlatform: employee.mobilePlatform ?? '',
      gender: employee.gender ?? '',
      dateOfBirth: parseIsoDate(employee.dateOfBirth),
      bloodGroup: '',
      personalEmail: employee.personalEmail,
      currentAddress: employee.currentAddress ?? '',
      permanentAddress: employee.permanentAddress ?? '',
      maritalStatus: '',
      nationality: '',
      emergencyName: employee.emergencyContactName ?? '',
      emergencyPhone: employee.emergencyContactPhone,
    });
    this.sameAddress.set((employee.currentAddress ?? '') === (employee.permanentAddress ?? ''));
    this.clearScreenOnly();
    this.photoUrl.set(employee.photo);
    this.photoToSave.set(null);
    this.finishEditState();
  }

  private markStep(index: number): boolean {
    const names = STEP_FIELDS[index] ?? [];
    let valid = true;
    for (const name of names) {
      const control = this.form.get(name);
      control?.markAsTouched();
      control?.updateValueAndValidity();
      if (control?.invalid) valid = false;
    }
    return valid;
  }

  private focusInvalidStep(): void {
    for (let index = 0; index < STEP_FIELDS.length; index += 1) {
      if (STEP_FIELDS[index].some((name) => this.form.get(name)?.invalid)) {
        this.step.set(index);
        return;
      }
    }
  }

  private applySameAddress(): void {
    const permanent = this.form.controls.permanentAddress;
    if (this.sameAddress()) {
      permanent.setValue(this.form.controls.currentAddress.value, { emitEvent: false });
      permanent.disable({ emitEvent: false });
    } else if (this.canManage) {
      permanent.enable({ emitEvent: false });
    }
  }

  private clearScreenOnly(): void {
    const previous = this.photoUrl();
    if (previous?.startsWith('blob:')) URL.revokeObjectURL(previous);
    this.photoUrl.set(null);
    this.photoToSave.set(null);
    this.photoError.set(null);
    this.documents.set([]);
    this.step.set(0);
  }

  private finishEditState(): void {
    this.applySameAddress();
    if (!this.canManage) this.form.disable({ emitEvent: false });
    this.form.markAsPristine();
  }
}
