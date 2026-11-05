import {
  ChangeDetectionStrategy,
  Component,
  computed,
  inject,
} from '@angular/core';
import { takeUntilDestroyed, toSignal } from '@angular/core/rxjs-interop';
import { FormControl, ReactiveFormsModule } from '@angular/forms';
import { MatAutocompleteModule } from '@angular/material/autocomplete';
import { MatButtonModule } from '@angular/material/button';
import {
  MAT_DIALOG_DATA,
  MatDialogModule,
  MatDialogRef,
} from '@angular/material/dialog';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatIconModule } from '@angular/material/icon';
import { MatInputModule } from '@angular/material/input';
import { MatSelectModule } from '@angular/material/select';
import { RouterLink } from '@angular/router';
import {
  Observable,
  catchError,
  debounceTime,
  distinctUntilChanged,
  filter,
  map,
  of,
  startWith,
  switchMap,
} from 'rxjs';
import { AuthStore } from '@trishul/core-auth';
import {
  CustomerListItem,
  MACHINE_MANAGE_PERMISSION,
  MachineUnitOption,
  ServiceCallApi,
  ServiceCallTriageUpdate,
} from '@trishul/service-data-access';
import { AscBadge } from './asc-badge';

/** The current customer has no code on the call list, so it's optional. */
type CustomerChoice = Pick<CustomerListItem, 'id' | 'name'> &
  Partial<Pick<CustomerListItem, 'code'>>;
type Value = CustomerChoice | string;

export interface CustomerLinkData {
  callNo: string;
  customerId: number;
  customerName: string;
  machineUnitId: number | null;
  machineLabel: string;
}
/** Only what changed. */
export type CustomerLinkResult = Pick<
  ServiceCallTriageUpdate,
  'customerId' | 'machineUnitId'
>;

/** Link the real customer and their machine to a call (e.g. a BYD placeholder). */
@Component({
  selector: 'trishul-customer-link-dialog',
  imports: [
    ReactiveFormsModule,
    RouterLink,
    MatDialogModule,
    MatFormFieldModule,
    MatInputModule,
    MatAutocompleteModule,
    MatSelectModule,
    MatButtonModule,
    MatIconModule,
    AscBadge,
  ],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <h2 mat-dialog-title>Link customer &amp; machine</h2>
    <mat-dialog-content>
      <p class="sub">
        Call {{ data.callNo }} — currently <b>{{ data.customerName }}</b>
      </p>
      <mat-form-field appearance="outline" class="full">
        <mat-label>Customer</mat-label>
        <mat-icon matPrefix>person_search</mat-icon>
        <input
          matInput
          [formControl]="control"
          [matAutocomplete]="auto"
          placeholder="Search by code or name"
        />
        <mat-autocomplete #auto="matAutocomplete" [displayWith]="display">
          @for (c of options(); track c.id) {
          <mat-option [value]="c">{{ c.code }} · {{ c.name }}</mat-option>
          }
        </mat-autocomplete>
      </mat-form-field>
      <mat-form-field appearance="outline" class="full">
        <mat-label>Machine</mat-label>
        <mat-icon matPrefix>precision_manufacturing</mat-icon>
        <mat-select [formControl]="machine">
          <mat-option [value]="null">No machine / not registered</mat-option>
          @if (currentOffered()) {
          <mat-option [value]="data.machineUnitId">
            {{ data.machineLabel }} (current)
          </mat-option>
          }
          @for (m of machines() ?? []; track m.id) {
          <mat-option [value]="m.id">{{ machineLabel(m) }}</mat-option>
          }
        </mat-select>
        <mat-hint>
          @if (customerId() === null) {
          Pick the customer first to see their machines.
          } @else if (machines() === null) {
          Loading the customer's machines…
          } @else if (notTheirs()) {
          The current machine isn't registered to this customer.
          } @else if (machines()?.length === 0) {
          This customer has no active registered machines.
          @if (canAddMachine) {
          <a routerLink="/service/machines/new" target="_blank">Add a machine</a>
          }
          } @else {
          {{ machines()?.length }} registered machine(s) of this customer.
          }
        </mat-hint>
      </mat-form-field>
      @if (selectedMachine(); as m) {
      <div class="asc-line"><trishul-asc-badge [asc]="m.asc" /></div>
      }
    </mat-dialog-content>
    <mat-dialog-actions align="end">
      <button mat-button mat-dialog-close>Cancel</button>
      <button mat-flat-button [disabled]="!canLink()" (click)="link()">
        Link
      </button>
    </mat-dialog-actions>
  `,
  styles: `
    .sub {
      margin: 0 0 1rem;
      color: var(--mat-sys-on-surface-variant);
    }
    .full {
      display: block;
      width: 24rem;
      max-width: 100%;
    }
    .full + .full {
      margin-top: 0.5rem;
    }
    .asc-line {
      margin-top: 1rem;
    }
  `,
})
export class CustomerLinkDialog {
  private readonly api = inject(ServiceCallApi);
  private readonly ref =
    inject<MatDialogRef<CustomerLinkDialog, CustomerLinkResult>>(MatDialogRef);
  protected readonly data = inject<CustomerLinkData>(MAT_DIALOG_DATA);

  protected readonly canAddMachine = inject(AuthStore).hasPermission(
    MACHINE_MANAGE_PERMISSION,
  );

  protected readonly control = new FormControl<Value>(
    { id: this.data.customerId, name: this.data.customerName },
    { nonNullable: true },
  );
  protected readonly machine = new FormControl<number | null>(
    this.data.machineUnitId,
  );

  protected readonly options = toSignal(
    this.control.valueChanges.pipe(
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

  private readonly customerId$ = this.control.valueChanges.pipe(
    map((v) => (typeof v === 'string' ? null : v.id)),
    startWith(this.data.customerId),
    distinctUntilChanged(),
  );
  protected readonly customerId = toSignal(this.customerId$, {
    initialValue: this.data.customerId,
  });

  /** The picked customer's active machines (null while loading). */
  protected readonly machines = toSignal(
    this.customerId$.pipe(
      switchMap((id): Observable<MachineUnitOption[] | null> =>
        id === null
          ? of([])
          : this.api.machineOptions('', id).pipe(
              catchError(() => of<MachineUnitOption[]>([])),
              startWith(null),
            ),
      ),
    ),
    { initialValue: null as MachineUnitOption[] | null },
  );

  private readonly machineId = toSignal(this.machine.valueChanges, {
    initialValue: this.data.machineUnitId,
  });

  /** The call's machine stays on offer: it can lack an owner yet, and Link must not drop it unseen. */
  protected readonly currentOffered = computed(
    () =>
      this.data.machineUnitId !== null &&
      !this.machines()?.some((m) => m.id === this.data.machineUnitId),
  );
  /** The customer changed and the call's machine isn't one of theirs. */
  protected readonly notTheirs = computed(
    () =>
      this.machines() !== null &&
      this.currentOffered() &&
      this.customerId() !== this.data.customerId,
  );
  protected readonly selectedMachine = computed(
    () => this.machines()?.find((m) => m.id === this.machineId()) ?? null,
  );
  protected readonly canLink = computed(() => {
    const customerId = this.customerId();
    return (
      customerId !== null &&
      (customerId !== this.data.customerId ||
        this.machineId() !== this.data.machineUnitId)
    );
  });

  constructor() {
    // A machine picked for one customer isn't on offer for the next: back to the call's own.
    this.customerId$
      .pipe(takeUntilDestroyed())
      .subscribe(() => this.machine.setValue(this.data.machineUnitId));
  }

  protected readonly display = (v: Value | null): string =>
    !v
      ? ''
      : typeof v === 'string'
        ? v
        : [v.code, v.name].filter(Boolean).join(' · ');

  protected machineLabel(m: MachineUnitOption): string {
    return [m.serialNumber, m.modelName].filter(Boolean).join(' · ');
  }

  protected link(): void {
    const result: CustomerLinkResult = {};
    const customerId = this.customerId();
    if (customerId !== null && customerId !== this.data.customerId) {
      result.customerId = customerId;
    }
    if (this.machineId() !== this.data.machineUnitId) {
      result.machineUnitId = this.machineId();
    }
    this.ref.close(result);
  }
}
