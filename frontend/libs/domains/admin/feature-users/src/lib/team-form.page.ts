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
import { toObservable, toSignal } from '@angular/core/rxjs-interop';
import {
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
import { MatOption, MatSelect } from '@angular/material/select';
import { Router, RouterLink } from '@angular/router';
import { EMPTY, catchError, finalize, of, startWith, switchMap } from 'rxjs';
import {
  TEAM_MANAGE_PERMISSION,
  TEAM_TYPES,
  TeamDetail,
  TeamEmployeeOption,
  TeamsApi,
} from '@trishul/admin-data-access';
import { AuthStore } from '@trishul/core-auth';
import { PageHeader, StatusBadge } from '@trishul/shared-ui';
import { ACTIVE_SEVERITY } from './alert-rule-list.page';
import { TeamActions } from './team-actions';

/** Designation code of the people a service team is made of; they are listed first. */
const SERVICE_ENGINEER = 'SERVICE_ENG';

/** Add a team (/admin/teams/new) or view and edit one, its lead and members (/admin/teams/:teamId). */
@Component({
  selector: 'trishul-team-form-page',
  imports: [
    ReactiveFormsModule,
    RouterLink,
    MatFormField,
    MatLabel,
    MatHint,
    MatError,
    MatPrefix,
    MatInput,
    MatSelect,
    MatOption,
    MatCheckbox,
    MatButton,
    MatIcon,
    MatProgressBar,
    PageHeader,
    StatusBadge,
  ],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './team-form.page.html',
  styleUrls: ['./customer-form.page.scss', './role-form.page.scss'],
})
export class TeamFormPage {
  private readonly api = inject(TeamsApi);
  private readonly actions = inject(TeamActions);
  private readonly router = inject(Router);
  private readonly fb = inject(NonNullableFormBuilder);
  private readonly auth = inject(AuthStore);

  readonly teamId = input<string>();

  protected readonly isNew = computed(() => !this.teamId());
  protected readonly canManage = this.auth.hasPermission(
    TEAM_MANAGE_PERMISSION,
  );
  protected readonly team = signal<TeamDetail | null>(null);
  protected readonly loading = signal(false);
  protected readonly saving = signal(false);
  protected readonly activeSeverity = ACTIVE_SEVERITY;
  protected readonly teamTypes = TEAM_TYPES;
  protected readonly filter = signal('');
  protected readonly branches = computed(
    () => this.auth.user()?.branches ?? [],
  );

  protected readonly form = this.fb.group({
    name: this.fb.control('', [Validators.required, Validators.maxLength(80)]),
    teamType: this.fb.control<TeamDetail['teamType']>('Service'),
    branchId: this.fb.control<number | null>(null, Validators.required),
    teamLeadEmployeeId: this.fb.control<number | null>(
      null,
      Validators.required,
    ),
    memberEmployeeIds: this.fb.control<number[]>([]),
  });

  private readonly branchId = toSignal(
    this.form.controls.branchId.valueChanges,
    { initialValue: null },
  );
  private readonly leadId = toSignal(
    this.form.controls.teamLeadEmployeeId.valueChanges,
    { initialValue: null },
  );
  private readonly memberIds = toSignal(
    this.form.controls.memberEmployeeIds.valueChanges,
    { initialValue: [] as number[] },
  );
  protected readonly selected = computed(() => new Set(this.memberIds()));

  /** Active employees of the chosen branch (the API checks the same); Service Engineers first. */
  protected readonly employees = toSignal(
    toObservable(this.branchId).pipe(
      switchMap((branchId) =>
        this.canManage && branchId
          ? this.api.employeeOptions(branchId).pipe(
              catchError(() => of([] as TeamEmployeeOption[])),
              startWith([] as TeamEmployeeOption[]),
            )
          : of([] as TeamEmployeeOption[]),
      ),
    ),
    { initialValue: [] as TeamEmployeeOption[] },
  );

  /** Member candidates: everyone but the lead, narrowed by the filter box. */
  protected readonly candidates = computed(() => {
    const term = this.filter().trim().toLowerCase();
    const lead = this.leadId();
    return this.employees()
      .filter((e) => e.id !== lead)
      .filter(
        (e) =>
          !term ||
          [e.name, e.employeeCode, e.designation ?? ''].some((v) =>
            v.toLowerCase().includes(term),
          ),
      )
      .sort(
        (a, b) =>
          Number(b.designationCode === SERVICE_ENGINEER) -
          Number(a.designationCode === SERVICE_ENGINEER),
      );
  });

  constructor() {
    if (!this.canManage) this.form.disable();
    effect(() => {
      const id = this.teamId();
      untracked(() => (id ? this.load(Number(id)) : this.startNew()));
    });
    // The lead can't be a member of their own team.
    effect(() => {
      const lead = this.leadId();
      untracked(() => {
        if (lead !== null && this.selected().has(lead)) this.toggle(lead, false);
      });
    });
  }

  protected toggle(employeeId: number, checked: boolean): void {
    const next = new Set(this.selected());
    if (checked) next.add(employeeId);
    else next.delete(employeeId);
    const control = this.form.controls.memberEmployeeIds;
    control.setValue([...next]);
    control.markAsDirty();
  }

  protected branchChanged(): void {
    // Lead and members are employees of one branch.
    this.form.patchValue({ teamLeadEmployeeId: null, memberEmployeeIds: [] });
  }

  protected save(): void {
    this.form.markAllAsTouched();
    if (this.form.invalid || this.saving()) return;
    const v = this.form.getRawValue();
    const common = {
      name: v.name.trim(),
      teamType: v.teamType,
      teamLeadEmployeeId: v.teamLeadEmployeeId as number,
      memberEmployeeIds: v.memberEmployeeIds,
    };
    this.saving.set(true);
    const current = this.team();
    const request = current
      ? this.api.update(current.id, current.rowVersion, common)
      : this.api.create({ ...common, branchId: v.branchId as number });
    request
      .pipe(
        finalize(() => this.saving.set(false)),
        catchError(() => EMPTY), // the error toast has been shown
      )
      .subscribe((saved) => {
        this.actions.notify(
          current ? 'Changes saved.' : `${saved.name} added`,
        );
        if (current) this.show(saved);
        else void this.router.navigate(['/admin/teams', saved.id]);
      });
  }

  protected deactivate(): void {
    const t = this.team();
    if (t) this.actions.deactivate(t).subscribe((updated) => this.show(updated));
  }

  protected activate(): void {
    const t = this.team();
    if (t) this.actions.activate(t).subscribe((updated) => this.show(updated));
  }

  private startNew(): void {
    this.team.set(null);
    this.form.reset({
      name: '',
      teamType: 'Service',
      branchId: this.auth.branchId() ?? this.branches()[0]?.id ?? null,
      teamLeadEmployeeId: null,
      memberEmployeeIds: [],
    });
    if (this.canManage) this.form.controls.branchId.enable();
    this.form.markAsPristine();
  }

  private load(id: number): void {
    this.loading.set(true);
    this.api
      .get(id)
      .pipe(
        finalize(() => this.loading.set(false)),
        catchError(() => {
          void this.router.navigate(['/admin/teams']);
          return EMPTY;
        }),
      )
      .subscribe((team) => this.show(team));
  }

  private show(team: TeamDetail): void {
    this.team.set(team);
    this.form.reset({
      name: team.name,
      teamType: team.teamType,
      branchId: team.branchId,
      teamLeadEmployeeId: team.teamLeadEmployeeId,
      memberEmployeeIds: team.members.map((m) => m.employeeId),
    });
    this.form.controls.branchId.disable(); // a team stays in its branch
    if (!this.canManage) this.form.disable();
    this.form.markAsPristine();
  }
}
