import { Injectable, inject } from '@angular/core';
import {
  ApiClient,
  ItemSaleInfo,
  SalesFormOptions,
  getItemSaleInfo,
  getSalesFormOptions,
} from '@trishul/core-api';
import { AuthStore } from '@trishul/core-auth';
import { Observable, catchError, of, shareReplay } from 'rxjs';

const EMPTY_OPTIONS: SalesFormOptions = {
  brands: [],
  branches: [],
  locations: [],
  paymentTerms: [],
  states: [],
  defaultBranchId: null,
  defaultBrandId: null,
};

/** The dropdowns every sales screen shares (brands, branches, dispatch locations, terms), loaded once. */
@Injectable({ providedIn: 'root' })
export class SalesLookups {
  private readonly api = inject(ApiClient);
  private readonly auth = inject(AuthStore);
  private options$?: Observable<SalesFormOptions>;
  /** The header's branch and brand the options were loaded for (their defaults follow it). */
  private loadedFor?: string;

  options(): Observable<SalesFormOptions> {
    const scope = `${this.auth.branchId()}:${this.auth.principalId()}`;
    if (scope !== this.loadedFor) {
      this.loadedFor = scope;
      this.options$ = undefined;
    }
    this.options$ ??= this.api.call(getSalesFormOptions).pipe(
      catchError(() => of(EMPTY_OPTIONS)),
      shareReplay({ bufferSize: 1, refCount: false }),
    );
    return this.options$;
  }

  /** Unit, selling price and stock by location of an item (for defaulting a line). */
  itemInfo(
    itemId: number,
    principalId: number | null,
  ): Observable<ItemSaleInfo | null> {
    return this.api
      .call(getItemSaleInfo, { itemId, principalId })
      .pipe(catchError(() => of(null)));
  }

  reset(): void {
    this.options$ = undefined;
  }
}

export const NO_SALES_OPTIONS = EMPTY_OPTIONS;
