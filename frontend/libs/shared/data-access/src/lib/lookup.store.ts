import { Injectable, Signal, inject, signal } from '@angular/core';
import { ApiClient, LookupValueOut, lookupValues } from '@trishul/core-api';

/** An editable dropdown value (core.lookup_value), e.g. a CALL_SOURCE. */
export type LookupValue = LookupValueOut;

/** Loads each lookup type once per session and shares it between screens. */
@Injectable({ providedIn: 'root' })
export class LookupStore {
  private readonly api = inject(ApiClient);
  private readonly cache = new Map<string, Signal<LookupValue[]>>();

  /** Values of a lookup type, e.g. 'CALL_SOURCE', in display order. Empty until loaded. */
  values(typeCode: string): Signal<LookupValue[]> {
    let values = this.cache.get(typeCode);
    if (!values) {
      const state = signal<LookupValue[]>([]);
      // The API returns them sorted (sort_order, label).
      this.api.call(lookupValues, { type_code: typeCode }).subscribe({
        next: (rows) => state.set(rows),
        // Forget failures so the next screen retries.
        error: () => this.cache.delete(typeCode),
      });
      values = state.asReadonly();
      this.cache.set(typeCode, values);
    }
    return values;
  }
}
