import { ChangeDetectionStrategy, Component, inject } from '@angular/core';
import { toSignal } from '@angular/core/rxjs-interop';
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
import {
  Observable,
  catchError,
  debounceTime,
  distinctUntilChanged,
  filter,
  of,
  switchMap,
} from 'rxjs';
import { CustomerListItem, ServiceCallApi } from '@trishul/service-data-access';

type CustomerChoice = Pick<CustomerListItem, 'id' | 'name' | 'code'>;
type Value = CustomerChoice | string;

export interface CustomerLinkData {
  callNo: string;
  customerName: string;
}
export interface CustomerLinkResult {
  id: number;
  name: string;
}

/** Search for and link the real customer to a call (e.g. a BYD placeholder). */
@Component({
  selector: 'trishul-customer-link-dialog',
  imports: [
    ReactiveFormsModule,
    MatDialogModule,
    MatFormFieldModule,
    MatInputModule,
    MatAutocompleteModule,
    MatButtonModule,
    MatIconModule,
  ],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <h2 mat-dialog-title>Link customer</h2>
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
    </mat-dialog-content>
    <mat-dialog-actions align="end">
      <button mat-button mat-dialog-close>Cancel</button>
      <button mat-flat-button [disabled]="!picked" (click)="link()">Link</button>
    </mat-dialog-actions>
  `,
  styles: `
    .sub {
      margin: 0 0 1rem;
      color: var(--mat-sys-on-surface-variant);
    }
    .full {
      width: 24rem;
      max-width: 100%;
    }
  `,
})
export class CustomerLinkDialog {
  private readonly api = inject(ServiceCallApi);
  private readonly ref =
    inject<MatDialogRef<CustomerLinkDialog, CustomerLinkResult>>(MatDialogRef);
  protected readonly data = inject<CustomerLinkData>(MAT_DIALOG_DATA);

  protected readonly control = new FormControl<Value>('', {
    nonNullable: true,
  });

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

  protected readonly display = (v: Value | null): string =>
    !v ? '' : typeof v === 'string' ? v : `${v.code} · ${v.name}`;

  protected get picked(): CustomerChoice | null {
    const v = this.control.value;
    return typeof v === 'string' ? null : v;
  }

  protected link(): void {
    const c = this.picked;
    if (c) this.ref.close({ id: c.id, name: c.name });
  }
}
