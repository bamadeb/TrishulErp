import { DatePipe } from '@angular/common';
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
  FormRecord,
  NonNullableFormBuilder,
  ReactiveFormsModule,
  ValidationErrors,
  Validators,
} from '@angular/forms';
import { MatButton, MatIconButton } from '@angular/material/button';
import { MatCheckbox } from '@angular/material/checkbox';
import {
  MatError,
  MatFormField,
  MatHint,
  MatLabel,
  MatSuffix,
} from '@angular/material/form-field';
import { MatIcon } from '@angular/material/icon';
import { MatInput } from '@angular/material/input';
import { MatProgressBar } from '@angular/material/progress-bar';
import { MatOption, MatSelect } from '@angular/material/select';
import { MatSnackBar } from '@angular/material/snack-bar';
import { Router, RouterLink } from '@angular/router';
import { EMPTY, catchError, finalize, map, of, startWith } from 'rxjs';
import {
  ALERT_RULE_MANAGE_PERMISSION,
  ALERT_SEVERITIES,
  AlertParamDef,
  AlertRuleDetail,
  AlertRuleTestResult,
  AlertRulesApi,
  AlertSeverity,
  AlertType,
  AlertTypeItem,
  RERAISE_POLICIES,
  RecipientType,
  ReraisePolicy,
} from '@trishul/admin-data-access';
import { AuthStore } from '@trishul/core-auth';
import { PageHeader, StatusBadge } from '@trishul/shared-ui';
import { ACTIVE_SEVERITY, ALERT_SEVERITY } from './alert-rule-list.page';

const NONE = 0; // "all brands" / "all branches" (mat-select shows null as blank)
type ParamValue = number | boolean | string[] | null;
type RecipientGroup = FormGroup<{
  recipientType: FormControl<RecipientType>;
  roleId: FormControl<number | null>;
  appUserId: FormControl<number | null>;
}>;

/** A Role row needs a role, a User row a user; record-based rows need nothing. */
function recipientComplete(group: AbstractControl): ValidationErrors | null {
  const { recipientType, roleId, appUserId } = group.value as {
    recipientType: RecipientType;
    roleId: number | null;
    appUserId: number | null;
  };
  if (recipientType === 'Role' && !roleId) return { role: true };
  if (recipientType === 'User' && !appUserId) return { user: true };
  return null;
}

const RECIPIENT_LABELS: Record<RecipientType, string> = {
  Role: 'Everyone with a role',
  User: 'A named user',
  'Assigned engineer': "The call's assigned engineer",
  'Call logged by': 'Whoever logged the call',
};

/** Add an alert rule (/admin/alert-rules/new) or view and edit one (/admin/alert-rules/:alertRuleId). */
@Component({
  selector: 'trishul-alert-rule-form-page',
  imports: [
    DatePipe,
    ReactiveFormsModule,
    RouterLink,
    MatFormField,
    MatLabel,
    MatHint,
    MatError,
    MatSuffix,
    MatInput,
    MatSelect,
    MatOption,
    MatCheckbox,
    MatButton,
    MatIconButton,
    MatIcon,
    MatProgressBar,
    PageHeader,
    StatusBadge,
  ],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './alert-rule-form.page.html',
  styleUrl: './alert-rule-form.page.scss',
})
export class AlertRuleFormPage {
  private readonly api = inject(AlertRulesApi);
  private readonly router = inject(Router);
  private readonly fb = inject(NonNullableFormBuilder);
  private readonly snackBar = inject(MatSnackBar);

  readonly alertRuleId = input<string>();

  protected readonly isNew = computed(() => !this.alertRuleId());
  protected readonly canManage = inject(AuthStore).hasPermission(
    ALERT_RULE_MANAGE_PERMISSION,
  );
  protected readonly rule = signal<AlertRuleDetail | null>(null);
  protected readonly loading = signal(false);
  protected readonly saving = signal(false);
  protected readonly testing = signal(false);
  protected readonly testResult = signal<AlertRuleTestResult | null>(null);
  protected readonly severities = ALERT_SEVERITIES;
  protected readonly policies = RERAISE_POLICIES;
  protected readonly activeSeverity = ACTIVE_SEVERITY;
  protected readonly alertSeverity = ALERT_SEVERITY;
  protected readonly recipientLabels = RECIPIENT_LABELS;
  protected readonly policyLabels: Record<ReraisePolicy, string> = {
    'After resolution': 'After it was resolved',
    Never: 'Never (once per record)',
  };
  protected readonly triggerText: Record<AlertTypeItem['trigger'], string> = {
    Event: 'Raised the moment it happens.',
    Scheduled: 'Checked every minute by the alert service.',
  };
  protected readonly NONE = NONE;
  protected readonly dateTimeFormat = 'dd MMM yyyy, HH:mm';

  private readonly options = toSignal(
    this.canManage
      ? this.api.formOptions().pipe(catchError(() => of(null)))
      : of(null),
    { initialValue: null },
  );
  protected readonly alertTypes = computed(
    () => this.options()?.alertTypes ?? [],
  );
  protected readonly roles = computed(() => this.options()?.roles ?? []);
  protected readonly users = computed(() => this.options()?.users ?? []);
  protected readonly principals = computed(
    () => this.options()?.principals ?? [],
  );
  protected readonly branches = computed(() => this.options()?.branches ?? []);

  /** The chosen type's settings; one control per catalogue parameter. */
  private readonly paramsRecord = new FormRecord<FormControl<ParamValue>>({});

  protected readonly form = this.fb.group({
    code: this.fb.control('', [Validators.required, Validators.maxLength(40)]),
    name: this.fb.control('', [Validators.required, Validators.maxLength(150)]),
    description: new FormControl<string | null>(
      null,
      Validators.maxLength(500),
    ),
    alertType: new FormControl<AlertType | null>(null, Validators.required),
    severity: this.fb.control<AlertSeverity>('Warning'),
    principalId: this.fb.control<number>(NONE),
    branchId: this.fb.control<number>(NONE),
    reraisePolicy: this.fb.control<ReraisePolicy>('After resolution'),
    cooldownMinutes: this.fb.control(0, [
      Validators.min(0),
      Validators.max(43200),
    ]),
    params: this.paramsRecord,
    recipients: new FormArray<RecipientGroup>([], Validators.minLength(1)),
  });

  private readonly alertTypeCode = toSignal(
    this.form.controls.alertType.valueChanges.pipe(
      startWith(this.form.controls.alertType.value),
      map(() => this.form.controls.alertType.getRawValue()),
    ),
    { initialValue: null },
  );
  /** The catalogue entry of the chosen type: drives the settings fields and allowed recipients. */
  protected readonly selectedType = computed<AlertTypeItem | null>(
    () =>
      this.alertTypes().find((t) => t.code === this.alertTypeCode()) ?? null,
  );

  constructor() {
    if (!this.canManage) this.form.disable();
    effect(() => {
      const id = this.alertRuleId();
      untracked(() => (id ? this.load(Number(id)) : this.startNew()));
    });
    // A new rule: changing the type resets its settings to the type's defaults.
    this.form.controls.alertType.valueChanges.subscribe(() => {
      if (this.isNew()) this.buildParams(this.selectedTypeNow(), {});
    });
    // The catalogue arrives after the rule: build the settings once both are here.
    effect(() => {
      const type = this.selectedType();
      untracked(() => {
        if (type && !Object.keys(this.form.controls.params.controls).length) {
          this.buildParams(type, this.rule()?.parameters ?? {});
        }
      });
    });
  }

  protected get recipientRows(): RecipientGroup[] {
    return this.form.controls.recipients.controls;
  }

  protected addRecipient(type: RecipientType = 'Role'): void {
    this.form.controls.recipients.push(this.recipientGroup(type, null, null));
    this.form.markAsDirty();
  }

  protected removeRecipient(index: number): void {
    this.form.controls.recipients.removeAt(index);
    this.form.markAsDirty();
  }

  protected save(): void {
    this.form.markAllAsTouched();
    if (this.form.invalid || this.saving()) return;
    const v = this.form.getRawValue();
    const body = {
      code: v.code.trim(),
      name: v.name.trim(),
      description: v.description?.trim() || null,
      severity: v.severity,
      principalId: v.principalId === NONE ? null : v.principalId,
      branchId: v.branchId === NONE ? null : v.branchId,
      reraisePolicy: v.reraisePolicy,
      cooldownMinutes: Number(v.cooldownMinutes) || 0,
      parameters: v.params,
      recipients: v.recipients.map((r) => ({
        recipientType: r.recipientType,
        roleId: r.recipientType === 'Role' ? r.roleId : null,
        appUserId: r.recipientType === 'User' ? r.appUserId : null,
      })),
    };
    this.saving.set(true);
    const current = this.rule();
    const request = current
      ? this.api.update(current.id, current.rowVersion, body)
      : this.api.create({ ...body, alertType: v.alertType as AlertType });
    request
      .pipe(
        finalize(() => this.saving.set(false)),
        catchError(() => EMPTY), // the error toast has been shown
      )
      .subscribe((saved) => {
        this.notify(current ? 'Changes saved' : `${saved.name} added`);
        if (current) this.show(saved);
        else void this.router.navigate(['/admin/alert-rules', saved.id]);
      });
  }

  protected setActive(active: boolean): void {
    const r = this.rule();
    if (!r) return;
    (active ? this.api.activate(r.id) : this.api.deactivate(r.id))
      .pipe(catchError(() => EMPTY))
      .subscribe((updated) => {
        this.notify(
          active
            ? 'Rule switched on'
            : 'Rule switched off; its open alerts were resolved',
        );
        this.show(updated);
      });
  }

  protected test(): void {
    const r = this.rule();
    if (!r) return;
    this.testing.set(true);
    this.api
      .test(r.id)
      .pipe(
        finalize(() => this.testing.set(false)),
        catchError(() => EMPTY),
      )
      .subscribe((result) => this.testResult.set(result));
  }

  protected recipientsText(names: string[]): string {
    return names.length
      ? names.join(', ')
      : 'nobody (check recipients and their access)';
  }

  // ------------------------------------------------------------------ helpers

  private selectedTypeNow(): AlertTypeItem | null {
    const code = this.form.controls.alertType.getRawValue();
    return this.alertTypes().find((t) => t.code === code) ?? null;
  }

  private buildParams(
    type: AlertTypeItem | null,
    values: Record<string, unknown>,
  ): void {
    const group = this.paramsRecord;
    for (const key of Object.keys(group.controls)) group.removeControl(key);
    for (const p of type?.params ?? []) {
      group.addControl(p.key, this.paramFormControl(p, values[p.key]));
    }
    // Drop recipient rows the new type does not support (e.g. "assigned engineer" for warranty alerts).
    const allowed = new Set(type?.recipientTypes ?? []);
    const rows = this.form.controls.recipients;
    for (let i = rows.length - 1; i >= 0; i--) {
      if (type && !allowed.has(rows.at(i).controls.recipientType.value))
        rows.removeAt(i);
    }
    if (!this.canManage) this.form.disable();
  }

  private paramFormControl(
    p: AlertParamDef,
    value: unknown,
  ): FormControl<ParamValue> {
    if (p.kind === 'integer') {
      const validators = [Validators.pattern(/^\d+$/)];
      if (p.required) validators.push(Validators.required);
      if (p.min !== null) validators.push(Validators.min(p.min));
      if (p.max !== null) validators.push(Validators.max(p.max));
      return new FormControl<ParamValue>(
        (value ?? p.default ?? null) as number | null,
        validators,
      );
    }
    if (p.kind === 'boolean') {
      return new FormControl<ParamValue>(Boolean(value ?? p.default ?? false));
    }
    const list = (value ?? p.default ?? []) as string[];
    return new FormControl<ParamValue>(
      [...list],
      p.required ? Validators.required : [],
    );
  }

  private recipientGroup(
    type: RecipientType,
    roleId: number | null,
    appUserId: number | null,
  ): RecipientGroup {
    return new FormGroup(
      {
        recipientType: new FormControl<RecipientType>(type, {
          nonNullable: true,
        }),
        roleId: new FormControl<number | null>(roleId),
        appUserId: new FormControl<number | null>(appUserId),
      },
      { validators: recipientComplete },
    );
  }

  private startNew(): void {
    this.rule.set(null);
    this.testResult.set(null);
    this.form.reset({
      code: '',
      name: '',
      description: null,
      alertType: null,
      severity: 'Warning',
      principalId: NONE,
      branchId: NONE,
      reraisePolicy: 'After resolution',
      cooldownMinutes: 0,
    });
    this.form.controls.alertType.enable();
    this.buildParams(null, {});
    this.form.controls.recipients.clear();
    this.addRecipient('Role');
    if (!this.canManage) this.form.disable();
    this.form.markAsPristine();
  }

  private load(id: number): void {
    this.loading.set(true);
    this.api
      .get(id)
      .pipe(
        finalize(() => this.loading.set(false)),
        catchError(() => {
          void this.router.navigate(['/admin/alert-rules']);
          return EMPTY;
        }),
      )
      .subscribe((rule) => this.show(rule));
  }

  private show(rule: AlertRuleDetail): void {
    this.rule.set(rule);
    this.testResult.set(null);
    this.form.reset({
      code: rule.code,
      name: rule.name,
      description: rule.description,
      alertType: rule.alertType,
      severity: rule.severity,
      principalId: rule.principalId ?? NONE,
      branchId: rule.branchId ?? NONE,
      reraisePolicy: rule.reraisePolicy,
      cooldownMinutes: rule.cooldownMinutes,
    });
    this.form.controls.alertType.disable(); // a rule's type is fixed once created
    const rows = this.form.controls.recipients;
    rows.clear();
    for (const r of rule.recipients) {
      rows.push(this.recipientGroup(r.recipientType, r.roleId, r.appUserId));
    }
    this.buildParams(this.selectedTypeNow(), rule.parameters);
    if (!this.canManage) this.form.disable();
    this.form.markAsPristine();
  }

  private notify(message: string): void {
    this.snackBar.open(message, 'OK', { duration: 5000 });
  }
}
