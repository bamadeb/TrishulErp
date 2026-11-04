import { DatePipe, DecimalPipe } from '@angular/common';
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
import { takeUntilDestroyed, toSignal } from '@angular/core/rxjs-interop';
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
import { MatCheckbox } from '@angular/material/checkbox';
import { MatDialog } from '@angular/material/dialog';
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
  startWith,
  switchMap,
} from 'rxjs';
import { AuthStore } from '@trishul/core-auth';
import {
  ASC_MANAGE_PERMISSION,
  AscApi,
  ContractPlanItem,
  MachineUnitOption,
  ServiceCallApi,
  ServiceContractDetail,
} from '@trishul/service-data-access';
import {
  PageHeader,
  StatusBadge,
  confirmAction,
} from '@trishul/shared-ui';
import { AscBadge } from './asc-badge';
import { ASC_STATE_SEVERITY } from './asc-list.page';

type MachineValue = MachineUnitOption | string;

function machineLabel(m: MachineUnitOption): string {
  return [m.serialNumber, m.modelName, m.customerName]
    .filter(Boolean)
    .join(' · ');
}

/** The machine must be picked from the list, not just typed. */
function pickedMachine(control: AbstractControl): ValidationErrors | null {
  const v = control.value;
  if (!v) return { required: true };
  return typeof v === 'string' ? { notPicked: true } : null;
}

/** yyyy-mm-dd of the last day of a plan of `months` starting on `start` (as the API works it out). */
export function planEndDate(start: string, months: number): string {
  const [y, m, d] = start.split('-').map(Number);
  const index = m - 1 + months;
  const year = y + Math.floor(index / 12);
  const month = (index % 12) + 1;
  const lastDay = new Date(Date.UTC(year, month, 0)).getUTCDate();
  const end = new Date(Date.UTC(year, month - 1, Math.min(d, lastDay)));
  end.setUTCDate(end.getUTCDate() - 1);
  return end.toISOString().slice(0, 10);
}

function text(value: string | null): string | null {
  return value?.trim() || null;
}

/** Amounts come from the API as decimal strings ("33040.00"). */
export function amount(value: string | null): number | null {
  return value === null ? null : Number(value);
}

/** Add an ASC (/service/asc/new) or view, edit, renew and cancel one (/service/asc/:contractId). */
@Component({
  selector: 'trishul-asc-form-page',
  imports: [
    DatePipe,
    DecimalPipe,
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
    MatCheckbox,
    MatButton,
    MatIcon,
    MatProgressBar,
    PageHeader,
    StatusBadge,
    AscBadge,
  ],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './asc-form.page.html',
  styleUrl: './machine-form.page.scss',
})
export class AscFormPage {
  private readonly api = inject(AscApi);
  private readonly callApi = inject(ServiceCallApi);
  private readonly router = inject(Router);
  private readonly fb = inject(NonNullableFormBuilder);
  private readonly auth = inject(AuthStore);
  private readonly dialog = inject(MatDialog);
  private readonly snackBar = inject(MatSnackBar);

  readonly contractId = input<string>();

  protected readonly isNew = computed(() => !this.contractId());
  protected readonly canManage = this.auth.hasPermission(ASC_MANAGE_PERMISSION);
  protected readonly contract = signal<ServiceContractDetail | null>(null);
  protected readonly loading = signal(false);
  protected readonly saving = signal(false);
  protected readonly stateSeverity = ASC_STATE_SEVERITY;
  protected readonly machineLabel = machineLabel;
  protected readonly branches = computed(
    () => this.auth.user()?.branches ?? [],
  );

  protected readonly form = this.fb.group({
    machine: new FormControl<MachineValue>('', {
      nonNullable: true,
      validators: pickedMachine,
    }),
    contractPlanId: new FormControl<number | null>(null),
    startDate: new FormControl<string | null>(null, Validators.required),
    endDate: new FormControl<string | null>(null, Validators.required),
    visitsIncluded: new FormControl<number | null>(null, [
      Validators.min(0),
      Validators.max(200),
    ]),
    visitsUsed: this.fb.control(0, [Validators.min(0), Validators.max(200)]),
    contractValue: new FormControl<number | null>(null, Validators.min(0)),
    branchId: new FormControl<number | null>(
      this.auth.branchId(),
      Validators.required,
    ),
    engineerEmployeeId: new FormControl<number | null>(null),
    bookNo: new FormControl<string | null>(null, Validators.maxLength(20)),
    oemContractId: new FormControl<string | null>(null, Validators.maxLength(40)),
    receiptNo: new FormControl<string | null>(null, Validators.maxLength(60)),
    invoiceRef: new FormControl<string | null>(null, Validators.maxLength(60)),
    isRenewal: this.fb.control(false),
    terms: new FormControl<string | null>(null, Validators.maxLength(2000)),
  });

  /** Plans of the selected brand and the chosen branch's engineers (reloaded when the branch changes). */
  private readonly options = toSignal(
    this.form.controls.branchId.valueChanges.pipe(
      startWith(this.form.controls.branchId.value),
      distinctUntilChanged(),
      switchMap((branchId) =>
        this.api
          .formOptions(branchId ?? undefined)
          .pipe(catchError(() => of(null))),
      ),
    ),
    { initialValue: null },
  );
  protected readonly plans = computed(() => this.options()?.plans ?? []);
  protected readonly engineers = computed(
    () => this.options()?.engineers ?? [],
  );

  protected readonly machineOptions = toSignal(
    this.form.controls.machine.valueChanges.pipe(
      filter((v): v is string => typeof v === 'string'),
      debounceTime(250),
      distinctUntilChanged(),
      switchMap((term): Observable<MachineUnitOption[]> =>
        term.trim().length < 2
          ? of<MachineUnitOption[]>([])
          : this.callApi.machineOptions(term).pipe(catchError(() => of([]))),
      ),
    ),
    { initialValue: [] as MachineUnitOption[] },
  );

  private readonly machineValue = toSignal(
    this.form.controls.machine.valueChanges,
    { initialValue: '' as MachineValue },
  );
  /** The picked machine (new ASC), for its current ASC. */
  protected readonly pickedMachine = computed(() => {
    const v = this.machineValue();
    return v && typeof v !== 'string' ? v : null;
  });

  constructor() {
    if (!this.canManage) this.form.disable();
    effect(() => {
      const id = this.contractId();
      untracked(() => (id ? this.load(Number(id)) : this.startNew()));
    });
    // Picking a plan (or changing the start) fills the end date, visits and value from the plan.
    this.form.controls.contractPlanId.valueChanges
      .pipe(takeUntilDestroyed())
      .subscribe((planId) => this.applyPlan(this.planById(planId), true));
    this.form.controls.startDate.valueChanges
      .pipe(takeUntilDestroyed())
      .subscribe(() =>
        this.applyPlan(
          this.planById(this.form.controls.contractPlanId.value),
          false,
        ),
      );
  }

  protected readonly machineText = (v: MachineValue | null): string =>
    !v ? '' : typeof v === 'string' ? v : machineLabel(v);

  protected planLabel(p: ContractPlanItem): string {
    const total = amount(p.totalPrice);
    return total !== null
      ? `${p.name} · ₹${total.toLocaleString('en-IN')}`
      : p.name;
  }

  protected save(): void {
    this.form.markAllAsTouched();
    if (this.form.invalid || this.saving()) return;
    const v = this.form.getRawValue();
    const fields = {
      contractPlanId: v.contractPlanId,
      startDate: v.startDate as string,
      endDate: v.endDate as string,
      visitsIncluded: v.visitsIncluded,
      visitsUsed: v.visitsUsed ?? 0,
      contractValue: v.contractValue,
      branchId: v.branchId as number,
      engineerEmployeeId: v.engineerEmployeeId,
      bookNo: text(v.bookNo),
      oemContractId: text(v.oemContractId),
      receiptNo: text(v.receiptNo),
      invoiceRef: text(v.invoiceRef),
      isRenewal: v.isRenewal,
      terms: text(v.terms),
    };
    this.saving.set(true);
    const current = this.contract();
    const request = current
      ? this.api.update(current.id, current.rowVersion, fields)
      : this.api.create({
          ...fields,
          machineUnitId: (v.machine as MachineUnitOption).id,
        });
    request
      .pipe(
        finalize(() => this.saving.set(false)),
        catchError(() => EMPTY), // the error toast has been shown
      )
      .subscribe((saved) => {
        this.notify(current ? 'Changes saved' : `ASC ${saved.contractNo} added`);
        if (current) this.show(saved);
        else void this.router.navigate(['/service/asc', saved.id]);
      });
  }

  protected renew(): void {
    const c = this.contract();
    if (!c) return;
    confirmAction(this.dialog, {
      title: 'Renew this ASC?',
      message: `A new ASC for ${c.machineSerialNo} starts the day after ${c.contractNo} ends, on the same plan. You can then enter the receipt and invoice on it.`,
      confirmText: 'Renew',
    })
      .pipe(
        filter(Boolean),
        switchMap(() => this.api.renew(c.id, {})),
        catchError(() => EMPTY),
      )
      .subscribe((renewed) => {
        this.notify(`Renewed as ${renewed.contractNo}`);
        void this.router.navigate(['/service/asc', renewed.id]);
      });
  }

  protected cancel(): void {
    const c = this.contract();
    if (!c) return;
    confirmAction(this.dialog, {
      title: 'Cancel this ASC?',
      message: `${c.contractNo} for ${c.machineSerialNo} will no longer count: new calls on the machine won't get ASC priority. The record is kept.`,
      confirmText: 'Cancel ASC',
      destructive: true,
    })
      .pipe(
        filter(Boolean),
        switchMap(() => this.api.cancel(c.id)),
        catchError(() => EMPTY),
      )
      .subscribe((updated) => {
        this.notify(`${updated.contractNo} cancelled`);
        this.show(updated);
      });
  }

  private planById(id: number | null): ContractPlanItem | null {
    return id === null ? null : (this.plans().find((p) => p.id === id) ?? null);
  }

  /** Fills end date (and, when the plan itself changed, visits and value) from the plan. */
  private applyPlan(plan: ContractPlanItem | null, planChanged: boolean): void {
    if (!plan || this.form.disabled) return;
    const start = this.form.controls.startDate.value;
    if (start)
      this.form.controls.endDate.setValue(
        planEndDate(start, plan.durationMonths),
      );
    if (planChanged) {
      this.form.controls.visitsIncluded.setValue(plan.visitsIncluded);
      this.form.controls.contractValue.setValue(amount(plan.totalPrice));
    }
  }

  private startNew(): void {
    this.contract.set(null);
    this.form.reset({
      machine: '',
      contractPlanId: null,
      startDate: new Date().toISOString().slice(0, 10),
      endDate: null,
      visitsIncluded: null,
      visitsUsed: 0,
      contractValue: null,
      branchId: this.auth.branchId(),
      engineerEmployeeId: null,
      bookNo: null,
      oemContractId: null,
      receiptNo: null,
      invoiceRef: null,
      isRenewal: false,
      terms: null,
    });
    if (this.canManage) this.form.enable({ emitEvent: false });
    this.form.markAsPristine();
  }

  private load(id: number): void {
    this.loading.set(true);
    this.api
      .get(id)
      .pipe(
        finalize(() => this.loading.set(false)),
        catchError(() => {
          void this.router.navigate(['/service/asc']);
          return EMPTY;
        }),
      )
      .subscribe((contract) => this.show(contract));
  }

  private show(c: ServiceContractDetail): void {
    this.contract.set(c);
    this.form.reset(
      {
        machine: c.machineSerialNo ?? '',
        contractPlanId: c.contractPlanId,
        startDate: c.startDate,
        endDate: c.endDate,
        visitsIncluded: c.visitsIncluded,
        visitsUsed: c.visitsUsed,
        contractValue: amount(c.contractValue),
        branchId: c.branchId,
        engineerEmployeeId: c.engineerEmployeeId,
        bookNo: c.bookNo,
        oemContractId: c.oemContractId,
        receiptNo: c.receiptNo,
        invoiceRef: c.invoiceRef,
        isRenewal: c.isRenewal,
        terms: c.terms,
      },
      { emitEvent: false },
    );
    // The machine of an existing ASC can't change; a cancelled ASC can't be edited.
    if (!this.canManage || c.state === 'Cancelled') {
      this.form.disable({ emitEvent: false });
    } else {
      this.form.enable({ emitEvent: false });
      this.form.controls.machine.disable({ emitEvent: false });
    }
    this.form.markAsPristine();
  }

  private notify(message: string): void {
    this.snackBar.open(message, 'OK', { duration: 5000 });
  }
}
