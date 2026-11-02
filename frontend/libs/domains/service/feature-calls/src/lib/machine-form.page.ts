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
import { MatButton } from '@angular/material/button';
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
import { AuthStore } from '@trishul/core-auth';
import {
  CustomerListItem,
  MACHINE_MANAGE_PERMISSION,
  MACHINE_STATUSES,
  MachineApi,
  MachineDetail,
  MachineStatus,
  ServiceCallApi,
} from '@trishul/service-data-access';
import { PageHeader, StatusBadge, StatusSeverity } from '@trishul/shared-ui';
import { MachineActions } from './machine-actions';

type CustomerChoice = Pick<CustomerListItem, 'id' | 'name' | 'code'>;
type CustomerValue = CustomerChoice | string;

const ACTIVE_SEVERITY: Record<string, StatusSeverity> = {
  Active: 'success',
  Inactive: 'neutral',
};

function customerLabel(c: CustomerChoice): string {
  return [c.code, c.name].filter(Boolean).join(' · ');
}

/** The owner must be picked from the customer list, not just typed. */
function pickedCustomer(control: AbstractControl): ValidationErrors | null {
  const v = control.value;
  if (!v) return { required: true };
  return typeof v === 'string' ? { notPicked: true } : null;
}

function text(value: string | null): string | null {
  return value?.trim() || null;
}

/** Add a machine (/service/machines/new) or view and edit one (/service/machines/:machineId). */
@Component({
  selector: 'trishul-machine-form-page',
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
    MatAutocomplete,
    MatAutocompleteTrigger,
    MatButton,
    MatIcon,
    MatProgressBar,
    PageHeader,
    StatusBadge,
  ],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './machine-form.page.html',
  styleUrl: './machine-form.page.scss',
})
export class MachineFormPage {
  private readonly api = inject(MachineApi);
  private readonly callApi = inject(ServiceCallApi);
  private readonly actions = inject(MachineActions);
  private readonly router = inject(Router);
  private readonly fb = inject(NonNullableFormBuilder);
  private readonly auth = inject(AuthStore);

  readonly machineId = input<string>();

  protected readonly isNew = computed(() => !this.machineId());
  protected readonly canManage = this.auth.hasPermission(
    MACHINE_MANAGE_PERMISSION,
  );
  protected readonly machine = signal<MachineDetail | null>(null);
  protected readonly loading = signal(false);
  protected readonly saving = signal(false);
  protected readonly activeSeverity = ACTIVE_SEVERITY;
  protected readonly statuses = MACHINE_STATUSES;
  protected readonly customerLabel = customerLabel;

  private readonly options = toSignal(
    this.api.formOptions().pipe(catchError(() => of(null))),
    { initialValue: null },
  );
  protected readonly models = computed(() => this.options()?.models ?? []);

  protected readonly form = this.fb.group({
    serialNumber: this.fb.control('', [
      Validators.required,
      Validators.maxLength(40),
    ]),
    modelId: new FormControl<number | null>(null, Validators.required),
    customer: new FormControl<CustomerValue>('', {
      nonNullable: true,
      validators: pickedCustomer,
    }),
    status: this.fb.control<MachineStatus>('Sold'),
    engineNumber: new FormControl<string | null>(null, Validators.maxLength(40)),
    registrationNumber: new FormControl<string | null>(
      null,
      Validators.maxLength(20),
    ),
    yearOfManufacture: new FormControl<number | null>(null, [
      Validators.min(1950),
      Validators.max(2100),
    ]),
    saleDate: new FormControl<string | null>(null),
    commissioningDate: new FormControl<string | null>(null),
    warrantyStartDate: new FormControl<string | null>(null),
    warrantyEndDate: new FormControl<string | null>(null),
    oemRegisteredProductId: new FormControl<string | null>(
      null,
      Validators.maxLength(40),
    ),
  });

  protected readonly customerOptions = toSignal(
    this.form.controls.customer.valueChanges.pipe(
      filter((v): v is string => typeof v === 'string'),
      debounceTime(250),
      distinctUntilChanged(),
      switchMap((term): Observable<CustomerListItem[]> =>
        term.trim().length < 2
          ? of<CustomerListItem[]>([])
          : this.callApi.customers(term).pipe(catchError(() => of([]))),
      ),
    ),
    { initialValue: [] as CustomerListItem[] },
  );

  constructor() {
    if (!this.canManage) this.form.disable();
    effect(() => {
      const id = this.machineId();
      untracked(() => (id ? this.load(Number(id)) : this.startNew()));
    });
  }

  protected readonly customerText = (v: CustomerValue | null): string =>
    !v ? '' : typeof v === 'string' ? v : customerLabel(v);

  protected save(): void {
    this.form.markAllAsTouched();
    if (this.form.invalid || this.saving()) return;
    const v = this.form.getRawValue();
    const customer = v.customer as CustomerChoice; // validator guarantees an object
    const body = {
      serialNumber: v.serialNumber.trim(),
      modelId: v.modelId as number,
      customerId: customer.id,
      status: v.status,
      engineNumber: text(v.engineNumber),
      registrationNumber: text(v.registrationNumber),
      yearOfManufacture: v.yearOfManufacture || null,
      saleDate: v.saleDate || null,
      commissioningDate: v.commissioningDate || null,
      warrantyStartDate: v.warrantyStartDate || null,
      warrantyEndDate: v.warrantyEndDate || null,
      oemRegisteredProductId: text(v.oemRegisteredProductId),
    };
    this.saving.set(true);
    const current = this.machine();
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
          current ? 'Changes saved' : `${saved.serialNumber} added`,
        );
        if (current) this.show(saved);
        else void this.router.navigate(['/service/machines', saved.id]);
      });
  }

  protected deactivate(): void {
    const m = this.machine();
    if (m) this.actions.deactivate(m).subscribe((updated) => this.show(updated));
  }

  protected activate(): void {
    const m = this.machine();
    if (m) this.actions.activate(m).subscribe((updated) => this.show(updated));
  }

  private startNew(): void {
    this.machine.set(null);
    this.form.reset({
      serialNumber: '',
      modelId: null,
      customer: '',
      status: 'Sold',
      engineNumber: null,
      registrationNumber: null,
      yearOfManufacture: null,
      saleDate: null,
      commissioningDate: null,
      warrantyStartDate: null,
      warrantyEndDate: null,
      oemRegisteredProductId: null,
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
          void this.router.navigate(['/service/machines']);
          return EMPTY;
        }),
      )
      .subscribe((machine) => this.show(machine));
  }

  private show(machine: MachineDetail): void {
    this.machine.set(machine);
    this.form.reset({
      serialNumber: machine.serialNumber,
      modelId: machine.modelId,
      // An existing machine not yet linked shows an empty owner, which must be picked before saving.
      customer:
        machine.customerId !== null
          ? {
              id: machine.customerId,
              code: machine.customerCode ?? '',
              name: machine.customerName ?? '',
            }
          : '',
      status: machine.status,
      engineNumber: machine.engineNumber,
      registrationNumber: machine.registrationNumber,
      yearOfManufacture: machine.yearOfManufacture,
      saleDate: machine.saleDate,
      commissioningDate: machine.commissioningDate,
      warrantyStartDate: machine.warrantyStartDate,
      warrantyEndDate: machine.warrantyEndDate,
      oemRegisteredProductId: machine.oemRegisteredProductId,
    });
    if (!this.canManage) this.form.disable();
    this.form.markAsPristine();
  }
}
