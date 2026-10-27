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
  FormArray,
  FormControl,
  FormGroup,
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
import { MatDialog } from '@angular/material/dialog';
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
import { MatRadioButton, MatRadioGroup } from '@angular/material/radio';
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
  of,
  switchMap,
} from 'rxjs';
import {
  EmployeeOption,
  PasswordDelivery,
  SIGN_IN_STATUS_LABELS,
  USER_MANAGE_PERMISSION,
  UserDetail,
  UsersApi,
  employeeLabel,
} from '@trishul/admin-data-access';
import { AuthStore } from '@trishul/core-auth';
import { PageHeader, StatusBadge, StatusSeverity } from '@trishul/shared-ui';
import { TrishulValidators } from '@trishul/shared-util';
import { showTemporaryPassword } from './password-dialogs';
import { UserActions } from './user-actions';

type RoleRow = FormGroup<{
  roleId: FormControl<number | null>;
  branchId: FormControl<number>;
}>;

const ACTIVE_SEVERITY: Record<string, StatusSeverity> = {
  Active: 'success',
  Inactive: 'neutral',
};

/** The linked employee as the form needs it: from the picker, or from the loaded user. */
type EmployeeChoice = Pick<
  EmployeeOption,
  'id' | 'employeeCode' | 'firstName' | 'lastName' | 'designation'
>;

/** The employee box holds the search text while typing, and the employee once one is picked. */
type EmployeeValue = EmployeeChoice | string;

const NO_BRANCH = 0;

function orNull(branchId: number): number | null {
  return branchId === NO_BRANCH ? null : branchId;
}

function atLeastOne(array: AbstractControl): ValidationErrors | null {
  return (array as FormArray).length > 0 ? null : { required: true };
}

/** Empty, or an employee picked from the list (not just typed text). */
function pickedOrEmpty(control: AbstractControl): ValidationErrors | null {
  const value = control.value as EmployeeValue;
  return typeof value === 'string' && value.trim() ? { notPicked: true } : null;
}

function employeeOf(user: UserDetail): EmployeeChoice | string {
  return user.employeeId && user.employeeCode && user.firstName
    ? {
        id: user.employeeId,
        employeeCode: user.employeeCode,
        firstName: user.firstName,
        lastName: user.lastName,
        designation: user.designation,
      }
    : '';
}

/** Add a user (/admin/users/new) or view and edit one (/admin/users/:userId). */
@Component({
  selector: 'trishul-user-form-page',
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
    MatAutocomplete,
    MatAutocompleteTrigger,
    MatSelect,
    MatOption,
    MatRadioGroup,
    MatRadioButton,
    MatButton,
    MatIconButton,
    MatIcon,
    MatProgressBar,
    PageHeader,
    StatusBadge,
  ],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './user-form.page.html',
  styleUrl: './user-form.page.scss',
})
export class UserFormPage {
  private readonly api = inject(UsersApi);
  private readonly actions = inject(UserActions);
  private readonly dialog = inject(MatDialog);
  private readonly router = inject(Router);
  private readonly fb = inject(NonNullableFormBuilder);
  private readonly auth = inject(AuthStore);

  /** Route parameter; absent on /admin/users/new. */
  readonly userId = input<string>();

  protected readonly isNew = computed(() => !this.userId());
  protected readonly canManage = this.auth.hasPermission(
    USER_MANAGE_PERMISSION,
  );
  protected readonly user = signal<UserDetail | null>(null);
  protected readonly loading = signal(false);
  protected readonly saving = signal(false);
  protected readonly signInLabels = SIGN_IN_STATUS_LABELS;
  protected readonly activeSeverity = ACTIVE_SEVERITY;

  /** Undefined until loaded: the Roles section waits for it, because a select without options
   * ignores clicks. */
  protected readonly roleOptions = toSignal(
    this.api.roles().pipe(catchError(() => of([]))),
  );
  /** mat-select shows null as blank, so "All branches" / "None" use this id; null for the API. */
  protected readonly NO_BRANCH = NO_BRANCH;
  protected readonly branches = computed(
    () => this.auth.user()?.branches ?? [],
  );
  protected readonly principals = computed(
    () => this.auth.user()?.principals ?? [],
  );

  protected readonly employeeLabel = employeeLabel;

  protected readonly form = this.fb.group({
    employee: new FormControl<EmployeeValue>('', {
      nonNullable: true,
      validators: pickedOrEmpty,
    }),
    email: this.fb.control('', [Validators.required, Validators.email]),
    mobile: new FormControl<string | null>(null, TrishulValidators.mobile),
    defaultBranchId: new FormControl<number>(NO_BRANCH, { nonNullable: true }),
    roles: new FormArray<RoleRow>([], atLeastOne),
    principalIds: this.fb.control<number[]>([]),
    delivery: this.fb.control<PasswordDelivery>('email'),
  });

  /** Employees matching what is typed in the employee box (only managers may search). */
  protected readonly employeeOptions = toSignal(
    this.canManage
      ? this.form.controls.employee.valueChanges.pipe(
          filter((value): value is string => typeof value === 'string'),
          debounceTime(250),
          distinctUntilChanged(),
          switchMap((term): Observable<EmployeeOption[]> =>
            this.api.employees(term.trim()).pipe(catchError(() => of([]))),
          ),
        )
      : of([]),
    { initialValue: [] },
  );

  constructor() {
    if (!this.canManage) this.form.disable();
    effect(() => {
      const id = this.userId();
      untracked(() => (id ? this.load(Number(id)) : this.startNew()));
    });
  }

  protected get roleRows(): RoleRow[] {
    return this.form.controls.roles.controls;
  }

  protected addRole(
    roleId: number | null = null,
    branchId: number | null = null,
  ): void {
    this.form.controls.roles.push(
      new FormGroup({
        roleId: new FormControl<number | null>(roleId, Validators.required),
        branchId: new FormControl<number>(branchId ?? NO_BRANCH, {
          nonNullable: true,
        }),
      }),
    );
    this.form.markAsDirty();
  }

  protected removeRole(index: number): void {
    this.form.controls.roles.removeAt(index);
    this.form.markAsDirty();
  }

  protected readonly employeeText = (value: EmployeeValue | null): string =>
    !value ? '' : typeof value === 'string' ? value : employeeLabel(value);

  /** Linked to a different user than the one on screen: can't be picked. */
  protected linkedElsewhere(employee: EmployeeOption): boolean {
    return (
      employee.linkedUserId !== null &&
      employee.linkedUserId !== this.user()?.id
    );
  }

  /** A new user's email defaults to the employee's work email. */
  protected onEmployeePicked(employee: EmployeeOption): void {
    const email = this.form.controls.email;
    if (this.isNew() && !email.value && employee.email) {
      email.setValue(employee.email);
    }
  }

  protected clearEmployee(): void {
    this.form.controls.employee.setValue('');
    this.form.markAsDirty();
  }

  protected save(): void {
    this.form.markAllAsTouched();
    if (this.form.invalid || this.saving()) return;
    const value = this.form.getRawValue();
    const roles = value.roles.map((row) => ({
      roleId: Number(row.roleId),
      branchId: orNull(row.branchId),
    }));
    const defaultBranchId = orNull(value.defaultBranchId);
    const employeeId =
      typeof value.employee === 'string' ? null : value.employee.id;
    this.saving.set(true);
    const user = this.user();
    if (!user) {
      this.api
        .create({
          email: value.email.trim(),
          employeeId,
          mobile: value.mobile || null,
          defaultBranchId,
          roles,
          principalIds: value.principalIds,
          delivery: value.delivery,
        })
        .pipe(
          switchMap((created) => {
            this.actions.notify(
              created.temporaryPassword
                ? `${created.username} added`
                : `${created.username} added; Cognito has emailed an invitation`,
            );
            const done = created.temporaryPassword
              ? showTemporaryPassword(
                  this.dialog,
                  created.username,
                  created.temporaryPassword,
                )
              : of(undefined);
            return done.pipe(
              switchMap(() =>
                this.router.navigate(['/admin/users', created.id]),
              ),
            );
          }),
          finalize(() => this.saving.set(false)),
          catchError(() => EMPTY), // the error toast has been shown
        )
        .subscribe();
      return;
    }
    this.api
      .update(user.id, user.rowVersion, {
        employeeId,
        mobile: value.mobile || null,
        defaultBranchId,
        roles,
        principalIds: value.principalIds,
      })
      .pipe(
        finalize(() => this.saving.set(false)),
        catchError(() => EMPTY),
      )
      .subscribe((updated) => {
        this.show(updated);
        this.actions.notify('Changes saved');
      });
  }

  protected resetPassword(): void {
    const user = this.user();
    if (!user) return;
    this.actions
      .resetPassword(user)
      .subscribe({ complete: () => this.load(user.id, false) });
  }

  protected deactivate(): void {
    const user = this.user();
    if (user) this.actions.deactivate(user).subscribe((u) => this.show(u));
  }

  protected activate(): void {
    const user = this.user();
    if (user) this.actions.activate(user).subscribe((u) => this.show(u));
  }

  private startNew(): void {
    this.user.set(null);
    this.form.reset({
      employee: '',
      email: '',
      mobile: null,
      defaultBranchId: this.auth.branchId() ?? NO_BRANCH,
      principalIds: [],
      delivery: 'email',
    });
    this.form.controls.roles.clear();
    this.addRole();
    this.form.markAsPristine();
  }

  private load(id: number, showProgress = true): void {
    if (showProgress) this.loading.set(true);
    this.api
      .get(id)
      .pipe(
        finalize(() => this.loading.set(false)),
        catchError(() => {
          void this.router.navigate(['/admin/users']);
          return EMPTY;
        }),
      )
      .subscribe((user) => this.show(user));
  }

  private show(user: UserDetail): void {
    this.user.set(user);
    this.form.controls.roles.clear();
    for (const grant of user.roles) this.addRole(grant.roleId, grant.branchId);
    this.form.patchValue({
      employee: employeeOf(user),
      email: user.username,
      mobile: user.mobile ?? null,
      defaultBranchId: user.defaultBranchId ?? NO_BRANCH,
      principalIds: user.principalIds,
    });
    this.form.controls.email.disable(); // the sign-in name can't change
    if (!this.canManage) this.form.disable();
    this.form.markAsPristine();
  }
}
