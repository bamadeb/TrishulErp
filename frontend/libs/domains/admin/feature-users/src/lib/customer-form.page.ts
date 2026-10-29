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
} from '@angular/material/form-field';
import { MatIcon } from '@angular/material/icon';
import { MatInput } from '@angular/material/input';
import { MatProgressBar } from '@angular/material/progress-bar';
import { MatOption, MatSelect } from '@angular/material/select';
import { Router, RouterLink } from '@angular/router';
import { EMPTY, catchError, finalize, of } from 'rxjs';
import {
  CUSTOMER_MANAGE_PERMISSION,
  CUSTOMER_TYPES,
  CustomerDetail,
  CustomerType,
  CustomersApi,
  GST_REGISTRATION_TYPES,
  GstRegistrationType,
  PRIORITY_TIERS,
  PriorityTier,
} from '@trishul/admin-data-access';
import { AuthStore } from '@trishul/core-auth';
import { PageHeader, StatusBadge, StatusSeverity } from '@trishul/shared-ui';
import { CustomerActions } from './customer-actions';

const NONE = 0; // sentinel for the optional state select (mat-select shows null as blank)
const PHONE_PATTERN = /^[0-9+\-() ]{6,15}$/;
const ACTIVE_SEVERITY: Record<string, StatusSeverity> = {
  Active: 'success',
  Inactive: 'neutral',
};

function orNull(id: number): number | null {
  return id === NONE ? null : id;
}

/** Add a customer (/admin/customers/new) or view and edit one (/admin/customers/:customerId). */
@Component({
  selector: 'trishul-customer-form-page',
  imports: [
    ReactiveFormsModule,
    RouterLink,
    MatFormField,
    MatLabel,
    MatHint,
    MatError,
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
  templateUrl: './customer-form.page.html',
  styleUrl: './customer-form.page.scss',
})
export class CustomerFormPage {
  private readonly api = inject(CustomersApi);
  private readonly actions = inject(CustomerActions);
  private readonly router = inject(Router);
  private readonly fb = inject(NonNullableFormBuilder);
  private readonly auth = inject(AuthStore);

  readonly customerId = input<string>();

  protected readonly isNew = computed(() => !this.customerId());
  protected readonly canManage = this.auth.hasPermission(
    CUSTOMER_MANAGE_PERMISSION,
  );
  protected readonly customer = signal<CustomerDetail | null>(null);
  protected readonly loading = signal(false);
  protected readonly saving = signal(false);
  protected readonly activeSeverity = ACTIVE_SEVERITY;
  protected readonly customerTypes = CUSTOMER_TYPES;
  protected readonly gstTypes = GST_REGISTRATION_TYPES;
  protected readonly priorityTiers = PRIORITY_TIERS;
  protected readonly NONE = NONE;

  private readonly options = toSignal(
    this.api.formOptions().pipe(catchError(() => of(null))),
    { initialValue: null },
  );
  protected readonly companies = computed(() => this.options()?.companies ?? []);
  protected readonly states = computed(() => this.options()?.states ?? []);

  protected readonly form = this.fb.group({
    code: this.fb.control('', [Validators.required, Validators.maxLength(20)]),
    name: this.fb.control('', [Validators.required, Validators.maxLength(200)]),
    customerType: this.fb.control<CustomerType>('Company'),
    companyId: new FormControl<number | null>(null, Validators.required),
    primaryPhone: this.fb.control('', [
      Validators.required,
      Validators.pattern(PHONE_PATTERN),
    ]),
    alternatePhone: new FormControl<string | null>(
      null,
      Validators.pattern(PHONE_PATTERN),
    ),
    email: new FormControl<string | null>(null, Validators.email),
    pan: new FormControl<string | null>(null, Validators.maxLength(10)),
    gstin: new FormControl<string | null>(null, Validators.maxLength(15)),
    gstRegistrationType:
      this.fb.control<GstRegistrationType>('Unregistered'),
    billingAddress: new FormControl<string | null>(
      null,
      Validators.maxLength(500),
    ),
    billingStateId: this.fb.control<number>(NONE),
    priorityTier: this.fb.control<PriorityTier>('Normal'),
    isAscCustomer: this.fb.control(false),
  });

  constructor() {
    if (!this.canManage) this.form.disable();
    effect(() => {
      const id = this.customerId();
      untracked(() => (id ? this.load(Number(id)) : this.startNew()));
    });
  }

  protected save(): void {
    this.form.markAllAsTouched();
    if (this.form.invalid || this.saving()) return;
    const v = this.form.getRawValue();
    const body = {
      code: v.code.trim(),
      name: v.name.trim(),
      customerType: v.customerType,
      companyId: v.companyId as number,
      primaryPhone: v.primaryPhone.trim(),
      alternatePhone: v.alternatePhone?.trim() || null,
      email: v.email?.trim() || null,
      pan: v.pan?.trim() || null,
      gstin: v.gstin?.trim() || null,
      gstRegistrationType: v.gstRegistrationType,
      billingAddress: v.billingAddress?.trim() || null,
      billingStateId: orNull(v.billingStateId),
      priorityTier: v.priorityTier,
      isAscCustomer: v.isAscCustomer,
    };
    this.saving.set(true);
    const current = this.customer();
    const request = current
      ? this.api.update(current.id, current.rowVersion, body)
      : this.api.create(body);
    request
      .pipe(
        finalize(() => this.saving.set(false)),
        catchError(() => EMPTY), // the error toast has been shown
      )
      .subscribe((saved) => {
        this.actions.notify(current ? 'Changes saved' : `${saved.name} added`);
        if (current) this.show(saved);
        else void this.router.navigate(['/admin/customers', saved.id]);
      });
  }

  protected deactivate(): void {
    const c = this.customer();
    if (c)
      this.actions.deactivate(c).subscribe((updated) => this.show(updated));
  }

  protected activate(): void {
    const c = this.customer();
    if (c) this.actions.activate(c).subscribe((updated) => this.show(updated));
  }

  private startNew(): void {
    this.customer.set(null);
    this.form.reset({
      code: '',
      name: '',
      customerType: 'Company',
      companyId: this.companies().length === 1 ? this.companies()[0].id : null,
      primaryPhone: '',
      alternatePhone: null,
      email: null,
      pan: null,
      gstin: null,
      gstRegistrationType: 'Unregistered',
      billingAddress: null,
      billingStateId: NONE,
      priorityTier: 'Normal',
      isAscCustomer: false,
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
          void this.router.navigate(['/admin/customers']);
          return EMPTY;
        }),
      )
      .subscribe((customer) => this.show(customer));
  }

  private show(customer: CustomerDetail): void {
    this.customer.set(customer);
    this.form.reset({
      code: customer.code,
      name: customer.name,
      customerType: customer.customerType,
      companyId: customer.companyId,
      primaryPhone: customer.primaryPhone,
      alternatePhone: customer.alternatePhone,
      email: customer.email,
      pan: customer.pan,
      gstin: customer.gstin,
      gstRegistrationType: customer.gstRegistrationType,
      billingAddress: customer.billingAddress,
      billingStateId: customer.billingStateId ?? NONE,
      priorityTier: customer.priorityTier ?? 'Normal',
      isAscCustomer: customer.isAscCustomer,
    });
    if (!this.canManage) this.form.disable();
    this.form.markAsPristine();
  }
}
