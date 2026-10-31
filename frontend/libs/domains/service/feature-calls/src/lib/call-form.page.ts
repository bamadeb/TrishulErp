import {
  ChangeDetectionStrategy,
  Component,
  computed,
  inject,
  signal,
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
import {
  MatError,
  MatFormField,
  MatLabel,
  MatPrefix,
  MatSuffix,
} from '@angular/material/form-field';
import { MatIcon } from '@angular/material/icon';
import { MatInput } from '@angular/material/input';
import { MatProgressBar } from '@angular/material/progress-bar';
import { MatOption, MatSelect } from '@angular/material/select';
import { MatSnackBar } from '@angular/material/snack-bar';
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
  CALL_PRIORITIES,
  CallPriority,
  CustomerListItem,
  MachineUnitOption,
  SERVICE_CALL_CREATE_PERMISSION,
  ServiceCallApi,
} from '@trishul/service-data-access';
import { AuthStore } from '@trishul/core-auth';
import { PageHeader } from '@trishul/shared-ui';

type CustomerChoice = Pick<CustomerListItem, 'id' | 'name' | 'code'>;
type CustomerValue = CustomerChoice | string;
type MachineValue = MachineUnitOption | string | null;

const PHONE = /^[0-9+\-() ]{6,15}$/;

function customerLabel(c: CustomerChoice): string {
  return [c.code, c.name].filter(Boolean).join(' · ');
}

function machineLabel(m: MachineUnitOption): string {
  return [m.serialNumber, m.modelName].filter(Boolean).join(' · ');
}

/** A customer must be picked from the list, not just typed. */
function pickedCustomer(control: AbstractControl): ValidationErrors | null {
  return typeof control.value === 'string' ? { notPicked: true } : null;
}

/** Log a new service call (/service/calls/new). */
@Component({
  selector: 'trishul-call-form-page',
  imports: [
    ReactiveFormsModule,
    RouterLink,
    MatFormField,
    MatLabel,
    MatError,
    MatPrefix,
    MatSuffix,
    MatInput,
    MatSelect,
    MatOption,
    MatAutocomplete,
    MatAutocompleteTrigger,
    MatCheckbox,
    MatButton,
    MatIconButton,
    MatIcon,
    MatProgressBar,
    PageHeader,
  ],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './call-form.page.html',
  styleUrl: './call-form.page.scss',
})
export class CallFormPage {
  private readonly api = inject(ServiceCallApi);
  private readonly router = inject(Router);
  private readonly fb = inject(NonNullableFormBuilder);
  private readonly snackBar = inject(MatSnackBar);
  private readonly auth = inject(AuthStore);

  protected readonly canCreate = this.auth.hasPermission(
    SERVICE_CALL_CREATE_PERMISSION,
  );
  protected readonly priorities = CALL_PRIORITIES;
  protected readonly branches = computed(
    () => this.auth.user()?.branches ?? [],
  );
  protected readonly principals = computed(
    () => this.auth.user()?.principals ?? [],
  );
  protected readonly customerLabel = customerLabel;
  protected readonly machineLabel = machineLabel;

  protected readonly callTypes = toSignal(
    this.api.lookups('CALL_TYPE').pipe(catchError(() => of([]))),
    { initialValue: [] },
  );
  protected readonly callSources = toSignal(
    this.api.lookups('CALL_SOURCE').pipe(catchError(() => of([]))),
    { initialValue: [] },
  );

  protected readonly form = this.fb.group({
    principalId: new FormControl<number | null>(this.auth.principalId(), {
      validators: Validators.required,
    }),
    branchId: new FormControl<number | null>(this.auth.branchId(), {
      validators: Validators.required,
    }),
    customer: new FormControl<CustomerValue>('', {
      nonNullable: true,
      validators: pickedCustomer,
    }),
    machine: new FormControl<MachineValue>(null),
    callTypeLookupId: new FormControl<number | null>(null, Validators.required),
    callSourceLookupId: new FormControl<number | null>(
      null,
      Validators.required,
    ),
    priority: this.fb.control<CallPriority>('Normal'),
    callerName: new FormControl<string | null>(null),
    callerPhone: this.fb.control('', [
      Validators.required,
      Validators.pattern(PHONE),
    ]),
    complaintDescription: this.fb.control('', [
      Validators.required,
      Validators.maxLength(2000),
    ]),
    isMachineDown: this.fb.control(false),
  });

  protected readonly isSaving = signal(false);

  protected readonly customerOptions = toSignal(
    this.form.controls.customer.valueChanges.pipe(
      filter((v): v is string => typeof v === 'string'),
      debounceTime(250),
      distinctUntilChanged(),
      switchMap((term): Observable<CustomerListItem[]> =>
        term.trim().length < 2
          ? of<CustomerListItem[]>([])
          : this.api.customers(term).pipe(catchError(() => of([]))),
      ),
    ),
    { initialValue: [] as CustomerListItem[] },
  );

  protected readonly machineOptions = toSignal(
    this.form.controls.machine.valueChanges.pipe(
      filter((v): v is string => typeof v === 'string'),
      debounceTime(250),
      distinctUntilChanged(),
      switchMap((term): Observable<MachineUnitOption[]> => {
        const customer = this.form.controls.customer.value;
        const customerId =
          customer && typeof customer !== 'string' ? customer.id : undefined;
        return this.api
          .machineOptions(term, customerId)
          .pipe(catchError(() => of<MachineUnitOption[]>([])));
      }),
    ),
    { initialValue: [] as MachineUnitOption[] },
  );

  constructor() {
    if (!this.canCreate) this.form.disable();
  }

  protected readonly customerText = (v: CustomerValue | null): string =>
    !v ? '' : typeof v === 'string' ? v : customerLabel(v);

  protected readonly machineText = (v: MachineValue): string =>
    !v ? '' : typeof v === 'string' ? v : machineLabel(v);

  protected clearMachine(): void {
    this.form.controls.machine.setValue(null);
  }

  protected save(): void {
    this.form.markAllAsTouched();
    if (this.form.invalid || this.isSaving()) return;
    const v = this.form.getRawValue();
    const customer = v.customer as CustomerChoice; // validator guarantees an object
    const machine = v.machine;
    const body = {
      customerId: customer.id,
      machineUnitId:
        machine && typeof machine !== 'string' ? machine.id : null,
      branchId: v.branchId as number,
      principalId: v.principalId as number,
      callTypeLookupId: v.callTypeLookupId as number,
      callSourceLookupId: v.callSourceLookupId as number,
      priority: v.priority,
      complaintDescription: v.complaintDescription.trim(),
      callerName: v.callerName?.trim() || null,
      callerPhone: v.callerPhone.trim(),
      isMachineDown: v.isMachineDown,
    };
    this.isSaving.set(true);
    this.api
      .create(body)
      .pipe(
        finalize(() => this.isSaving.set(false)),
        catchError(() => EMPTY), // the error toast has been shown
      )
      .subscribe((saved) => {
        this.snackBar.open(`Call ${saved.callNo} logged`, 'OK', {
          duration: 5000,
        });
        void this.router.navigate(['/service/calls']);
      });
  }
}
