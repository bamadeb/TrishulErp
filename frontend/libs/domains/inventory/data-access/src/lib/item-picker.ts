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
import { ApiClient, ItemListItem, listItems } from '@trishul/core-api';
import {
  Subject,
  catchError,
  debounceTime,
  distinctUntilChanged,
  of,
  switchMap,
} from 'rxjs';

export function itemLabel(
  item: Pick<ItemListItem, 'itemCode' | 'description'> | null,
): string {
  return item ? `${item.itemCode} · ${item.description}` : '';
}

/**
 * Pick an item by code, description or OEM part number. The form value is the chosen item
 * (ItemListItem) or null while nothing has been picked, so Validators.required covers "not picked".
 */
@Component({
  selector: 'trishul-item-picker',
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
        (blur)="onTouched()"
        autocomplete="off"
        placeholder="Code, description or part no"
      />
      <mat-autocomplete
        #auto="matAutocomplete"
        (optionSelected)="pick($event)"
        class="item-options"
      >
        @for (item of options(); track item.id) {
          <mat-option [value]="item">
            <strong>{{ item.itemCode }}</strong> · {{ item.description }}
            <span class="stock">{{ item.qtyOnHand }} {{ item.uomCode }}</span>
          </mat-option>
        } @empty {
          @if (text().length > 0) {
            <mat-option disabled>No stock item matches.</mat-option>
          }
        }
      </mat-autocomplete>
      <mat-error>Pick an item from the list.</mat-error>
    </mat-form-field>
  `,
  styles: `
    :host {
      display: block;
    }
    mat-form-field {
      width: 100%;
    }
    .stock {
      margin-left: 0.5rem;
      font-size: 0.8em;
      color: var(--mat-sys-on-surface-variant);
    }
  `,
})
export class ItemPicker implements ControlValueAccessor {
  private readonly api = inject(ApiClient);
  /** The form control this picker is bound to; its errors show on the inner field. */
  private readonly ngControl = inject(NgControl, {
    self: true,
    optional: true,
  });
  protected readonly matcher: ErrorStateMatcher = {
    isErrorState: () => !!this.ngControl?.invalid && !!this.ngControl?.touched,
  };
  readonly label = input('Item');
  /** Only items kept in stock (default), or every item. */
  readonly stockOnly = input(true);

  protected readonly text = signal('');
  protected readonly options = signal<ItemListItem[]>([]);
  protected readonly disabled = signal(false);
  private readonly search$ = new Subject<string>();
  private onChange: (value: ItemListItem | null) => void = () => undefined;
  protected onTouched: () => void = () => undefined;

  constructor() {
    if (this.ngControl) this.ngControl.valueAccessor = this;
    this.search$
      .pipe(
        debounceTime(250),
        distinctUntilChanged(),
        switchMap((search) =>
          this.api
            .call(listItems, {
              search: search || null,
              pageSize: 20,
              ...(this.stockOnly() ? { itemType: 'Stock' as const } : {}),
            })
            .pipe(catchError(() => of({ items: [] as ItemListItem[] }))),
        ),
        takeUntilDestroyed(inject(DestroyRef)),
      )
      .subscribe((page) => this.options.set(page.items));
  }

  protected onType(value: string): void {
    this.text.set(value);
    this.onChange(null);
    this.search$.next(value.trim());
  }

  protected pick(event: MatAutocompleteSelectedEvent): void {
    const item = event.option.value as ItemListItem;
    this.text.set(itemLabel(item));
    this.onChange(item);
  }

  writeValue(value: ItemListItem | null): void {
    this.text.set(itemLabel(value));
    if (!value) this.search$.next('');
  }

  registerOnChange(fn: (value: ItemListItem | null) => void): void {
    this.onChange = fn;
  }

  registerOnTouched(fn: () => void): void {
    this.onTouched = fn;
  }

  setDisabledState(disabled: boolean): void {
    this.disabled.set(disabled);
  }
}
