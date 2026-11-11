import { Injectable, inject } from '@angular/core';
import {
  ApiClient,
  ItemSaleInfo,
  SalesFormOptions,
  getItemSaleInfo,
  getSalesFormOptions,
} from '@trishul/core-api';
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
  private options$?: Observable<SalesFormOptions>;

  options(): Observable<SalesFormOptions> {
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
