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
  FormControl,
  NonNullableFormBuilder,
  ReactiveFormsModule,
  Validators,
} from '@angular/forms';
import { MatButton } from '@angular/material/button';
import { MatCheckbox } from '@angular/material/checkbox';
import {
  MatError,
  MatFormField,
  MatHint,
  MatLabel,
  MatPrefix,
} from '@angular/material/form-field';
import { MatIcon } from '@angular/material/icon';
import { MatInput } from '@angular/material/input';
import { MatProgressBar } from '@angular/material/progress-bar';
import { Router, RouterLink } from '@angular/router';
import { EMPTY, catchError, finalize, of } from 'rxjs';
import {
  ADMIN_ROLE_CODE,
  PermissionGroup,
  ROLE_CODE_PATTERN,
  ROLE_MANAGE_PERMISSION,
  RoleDetail,
  RolesApi,
  USER_VIEW_PERMISSIONS,
  groupPermissions,
} from '@trishul/admin-data-access';
import { AuthStore } from '@trishul/core-auth';
import { PageHeader, StatusBadge } from '@trishul/shared-ui';
import { ACTIVE_SEVERITY } from './alert-rule-list.page';
import { RoleActions } from './role-actions';

/** Add a role (/admin/roles/new) or view and edit one and its permissions (/admin/roles/:roleId). */
@Component({
  selector: 'trishul-role-form-page',
  imports: [
    ReactiveFormsModule,
    RouterLink,
    MatFormField,
    MatLabel,
    MatHint,
    MatError,
    MatPrefix,
    MatInput,
    MatCheckbox,
    MatButton,
    MatIcon,
    MatProgressBar,
    PageHeader,
    StatusBadge,
  ],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './role-form.page.html',
  styleUrls: ['./customer-form.page.scss', './role-form.page.scss'],
})
export class RoleFormPage {
  private readonly api = inject(RolesApi);
  private readonly actions = inject(RoleActions);
  private readonly router = inject(Router);
  private readonly fb = inject(NonNullableFormBuilder);
  private readonly auth = inject(AuthStore);

  readonly roleId = input<string>();

  protected readonly isNew = computed(() => !this.roleId());
  protected readonly canManage = this.auth.hasPermission(
    ROLE_MANAGE_PERMISSION,
  );
  protected readonly canSeeUsers = this.auth.hasAnyPermission([
    ...USER_VIEW_PERMISSIONS,
  ]);
  protected readonly role = signal<RoleDetail | null>(null);
  protected readonly loading = signal(false);
  protected readonly saving = signal(false);
  protected readonly activeSeverity = ACTIVE_SEVERITY;
  protected readonly filter = signal('');

  private readonly permissions = toSignal(
    this.api.permissions().pipe(catchError(() => of([]))),
    { initialValue: [] },
  );
  protected readonly totalPermissions = computed(
    () => this.permissions().length,
  );

  protected readonly form = this.fb.group({
    code: this.fb.control('', [
      Validators.required,
      Validators.pattern(ROLE_CODE_PATTERN),
    ]),
    name: this.fb.control('', [Validators.required, Validators.maxLength(80)]),
    description: new FormControl<string | null>(null, Validators.maxLength(300)),
    permissionCodes: this.fb.control<string[]>([]),
  });

  private readonly selectedCodes = toSignal(
    this.form.controls.permissionCodes.valueChanges,
    { initialValue: [] as string[] },
  );
  protected readonly selected = computed(
    () => new Set<string>(this.selectedCodes()),
  );

  /** Groups narrowed by the filter box (code, description or module). */
  protected readonly groups = computed<PermissionGroup[]>(() => {
    const term = this.filter().trim().toLowerCase();
    const all = groupPermissions(this.permissions());
    if (!term) return all;
    return all
      .map((group) => ({
        module: group.module,
        permissions: group.module.toLowerCase().includes(term)
          ? group.permissions
          : group.permissions.filter(
              (p) =>
                p.code.toLowerCase().includes(term) ||
                (p.description ?? '').toLowerCase().includes(term),
            ),
      }))
      .filter((group) => group.permissions.length > 0);
  });

  constructor() {
    if (!this.canManage) this.form.disable();
    effect(() => {
      const id = this.roleId();
      untracked(() => (id ? this.load(Number(id)) : this.startNew()));
    });
  }

  /** ADMIN never loses role management; the API refuses it too. */
  protected isLocked(code: string): boolean {
    return (
      this.role()?.code === ADMIN_ROLE_CODE && code === ROLE_MANAGE_PERMISSION
    );
  }

  protected selectedIn(group: PermissionGroup): number {
    const selected = this.selected();
    return group.permissions.filter((p) => selected.has(p.code)).length;
  }

  protected toggle(code: string, checked: boolean): void {
    if (this.isLocked(code)) return;
    const next = new Set(this.selected());
    if (checked) next.add(code);
    else next.delete(code);
    this.setSelection(next);
  }

  protected toggleGroup(group: PermissionGroup, checked: boolean): void {
    const next = new Set(this.selected());
    for (const { code } of group.permissions) {
      if (this.isLocked(code)) continue;
      if (checked) next.add(code);
      else next.delete(code);
    }
    this.setSelection(next);
  }

  protected save(): void {
    this.form.markAllAsTouched();
    if (this.form.invalid || this.saving()) return;
    const v = this.form.getRawValue();
    const common = {
      name: v.name.trim(),
      description: v.description?.trim() || null,
      permissionCodes: v.permissionCodes,
    };
    this.saving.set(true);
    const current = this.role();
    const request = current
      ? this.api.update(current.id, current.rowVersion, common)
      : this.api.create({ code: v.code.trim(), ...common });
    request
      .pipe(
        finalize(() => this.saving.set(false)),
        catchError(() => EMPTY), // the error toast has been shown
      )
      .subscribe((saved) => {
        this.actions.notify(
          current
            ? 'Changes saved. Users with this role get them on their next page load.'
            : `${saved.name} added`,
        );
        if (current) this.show(saved);
        else void this.router.navigate(['/admin/roles', saved.id]);
      });
  }

  protected deactivate(): void {
    const r = this.role();
    if (r) this.actions.deactivate(r).subscribe((updated) => this.show(updated));
  }

  protected activate(): void {
    const r = this.role();
    if (r) this.actions.activate(r).subscribe((updated) => this.show(updated));
  }

  private setSelection(codes: Set<string>): void {
    const control = this.form.controls.permissionCodes;
    control.setValue([...codes].sort());
    control.markAsDirty();
  }

  private startNew(): void {
    this.role.set(null);
    this.form.reset({
      code: '',
      name: '',
      description: null,
      permissionCodes: [],
    });
    if (this.canManage) this.form.controls.code.enable();
    this.form.markAsPristine();
  }

  private load(id: number): void {
    this.loading.set(true);
    this.api
      .get(id)
      .pipe(
        finalize(() => this.loading.set(false)),
        catchError(() => {
          void this.router.navigate(['/admin/roles']);
          return EMPTY;
        }),
      )
      .subscribe((role) => this.show(role));
  }

  private show(role: RoleDetail): void {
    this.role.set(role);
    this.form.reset({
      code: role.code,
      name: role.name,
      description: role.description,
      permissionCodes: [...role.permissionCodes].sort(),
    });
    this.form.controls.code.disable(); // a role's code never changes
    if (!this.canManage) this.form.disable();
    this.form.markAsPristine();
  }
}
