import {
  ChangeDetectionStrategy,
  Component,
  DestroyRef,
  inject,
  input,
  signal,
} from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { ControlValueAccessor, NgControl } from '@angular/forms';
import {
  MatAutocomplete,
  MatAutocompleteSelectedEvent,
  MatAutocompleteTrigger,
} from '@angular/material/autocomplete';
import { ErrorStateMatcher, MatOption } from '@angular/material/core';
import { MatError, MatFormField, MatLabel } from '@angular/material/form-field';
import { MatInput } from '@angular/material/input';
import {
  ApiClient,
  CustomerAccount,
  listCustomerAccounts,
} from '@trishul/core-api';
import {
  Subject,
  catchError,
  debounceTime,
  distinctUntilChanged,
  of,
  switchMap,
} from 'rxjs';

/** The fields a picked customer needs (a list row or an account detail both fit). */
export type PickedCustomer = Pick<
  CustomerAccount,
  'id' | 'code' | 'name' | 'balance' | 'creditLimit'
>;

export function customerLabel(customer: PickedCustomer | null): string {
  return customer ? `${customer.name} (${customer.code})` : '';
}

/**
 * Pick a customer by name, code, GSTIN or phone. The form value is the chosen customer or null while
 * nothing has been picked, so Validators.required covers "not picked".
 */
@Component({
  selector: 'trishul-customer-picker',
  imports: [
    MatFormField,
    MatLabel,
    MatError,
    MatInput,
    MatAutocomplete,
    MatAutocompleteTrigger,
    MatOption,
  ],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <mat-form-field appearance="outline" subscriptSizing="dynamic">
      <mat-label>{{ label() }}</mat-label>
      <input
        matInput
        [value]="text()"
        [disabled]="disabled()"
        [errorStateMatcher]="matcher"
        [matAutocomplete]="auto"
        (input)="onType($any($event.target).value)"
        (focus)="onFocus()"
        (blur)="onTouched()"
        autocomplete="off"
        placeholder="Name, code, GSTIN or phone"
      />
      <mat-autocomplete #auto="matAutocomplete" (optionSelected)="pick($event)">
        @for (c of options(); track c.id) {
          <mat-option [value]="c">
            <strong>{{ c.name }}</strong> · {{ c.code }}
            <span class="balance">{{ c.balance }}</span>
          </mat-option>
        } @empty {
          @if (text().length > 0) {
            <mat-option disabled>No customer matches.</mat-option>
          }
        }
      </mat-autocomplete>
      <mat-error>Pick a customer from the list.</mat-error>
    </mat-form-field>
  `,
  styles: `
    :host {
      display: block;
    }
    mat-form-field {
      width: 100%;
    }
    .balance {
      margin-left: 0.5rem;
      font-size: 0.8em;
      color: var(--mat-sys-on-surface-variant);
    }
  `,
})
export class CustomerPicker implements ControlValueAccessor {
  private readonly api = inject(ApiClient);
  private readonly ngControl = inject(NgControl, {
    self: true,
    optional: true,
  });
  protected readonly matcher: ErrorStateMatcher = {
    isErrorState: () => !!this.ngControl?.invalid && !!this.ngControl?.touched,
  };
  readonly label = input('Customer');

  protected readonly text = signal('');
  protected readonly options = signal<CustomerAccount[]>([]);
  protected readonly disabled = signal(false);
  private readonly search$ = new Subject<string>();
  private onChange: (value: PickedCustomer | null) => void = () => undefined;
  protected onTouched: () => void = () => undefined;

  constructor() {
    if (this.ngControl) this.ngControl.valueAccessor = this;
    this.search$
      .pipe(
        debounceTime(250),
        distinctUntilChanged(),
        switchMap((search) =>
          this.api
            .call(listCustomerAccounts, {
              search: search || null,
              pageSize: 20,
              status: 'active',
            })
            .pipe(catchError(() => of({ items: [] as CustomerAccount[] }))),
        ),
        takeUntilDestroyed(inject(DestroyRef)),
      )
      .subscribe((page) => this.options.set(page.items));
  }

  protected onFocus(): void {
    if (!this.options().length) this.search$.next(this.text().trim());
  }

  protected onType(value: string): void {
    this.text.set(value);
    this.onChange(null);
    this.search$.next(value.trim());
  }

  protected pick(event: MatAutocompleteSelectedEvent): void {
    const customer = event.option.value as CustomerAccount;
    this.text.set(customerLabel(customer));
    this.onChange(customer);
  }

  writeValue(value: PickedCustomer | null): void {
    this.text.set(customerLabel(value));
  }

  registerOnChange(fn: (value: PickedCustomer | null) => void): void {
    this.onChange = fn;
  }

  registerOnTouched(fn: () => void): void {
    this.onTouched = fn;
  }

  setDisabledState(disabled: boolean): void {
    this.disabled.set(disabled);
  }
}
