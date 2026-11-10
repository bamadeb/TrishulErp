import { Injectable, Signal, computed, inject, signal } from '@angular/core';
import { toObservable, toSignal } from '@angular/core/rxjs-interop';
import {
  ApiClient,
  BranchOption,
  LocationOut,
  RackOut,
  SupplierOut,
  UomOut,
  listInventoryBranches,
  listLocations,
  listRacks,
  listSuppliers,
  listUoms,
} from '@trishul/core-api';
import {
  Observable,
  catchError,
  combineLatest,
  debounceTime,
  finalize,
  map,
  of,
  shareReplay,
  switchMap,
} from 'rxjs';

interface PageOf<T> {
  items: T[];
  total: number;
}

/** A paged list that reloads whenever the query signal changes (or reload() is called). */
export interface PagedList<T> {
  readonly items: Signal<T[]>;
  readonly total: Signal<number>;
  readonly loading: Signal<boolean>;
  reload(): void;
}

/** Call in an injection context (a component field initialiser). */
export function pagedList<Q, T>(
  query: Signal<Q>,
  fetch: (query: Q) => Observable<PageOf<T>>,
): PagedList<T> {
  const loading = signal(false);
  const reloads = signal(0);
  const page = toSignal(
    combineLatest([toObservable(query), toObservable(reloads)]).pipe(
      debounceTime(0),
      switchMap(([q]) => {
        loading.set(true);
        return fetch(q).pipe(
          catchError(() => of({ items: [] as T[], total: 0 })),
          finalize(() => loading.set(false)),
        );
      }),
    ),
    { initialValue: { items: [] as T[], total: 0 } },
  );
  return {
    items: computed(() => page().items),
    total: computed(() => page().total),
    loading,
    reload: () => reloads.update((n) => n + 1),
  };
}

/** API decimals arrive as strings ("12.500"); null / empty stays null. */
export function num(value: string | number | null | undefined): number | null {
  if (value === null || value === undefined || value === '') return null;
  const parsed = typeof value === 'number' ? value : Number(value);
  return Number.isFinite(parsed) ? parsed : null;
}

/** 0 when missing: for sums and comparisons. */
export function n0(value: string | number | null | undefined): number {
  return num(value) ?? 0;
}

/** yyyy-mm-dd in the user's own time zone. */
export function isoDate(day: Date): string {
  return day.toLocaleDateString('en-CA');
}

/** A yyyy-mm-dd string as a local Date (midnight), for the date pickers. */
export function fromIso(value: string | null | undefined): Date | null {
  if (!value) return null;
  const [year, month, date] = value.split('-').map(Number);
  return new Date(year, month - 1, date);
}

export const AGE_BUCKETS = [
  '0-30 days',
  '31-60 days',
  '61-90 days',
  '91-180 days',
  'Above 180 days',
];

/** CSS class of an age badge (b0 fresh ... b4 over 180 days). */
export function ageClass(ageDays: number): string {
  if (ageDays <= 30) return 'b0';
  if (ageDays <= 60) return 'b1';
  if (ageDays <= 90) return 'b2';
  if (ageDays <= 180) return 'b3';
  return 'b4';
}

/** Downloads rows as a CSV file (opens in Excel). */
export function downloadCsv(
  fileName: string,
  header: string[],
  rows: (string | number | null)[][],
): void {
  const cell = (value: string | number | null): string => {
    const text = value === null ? '' : String(value);
    return /[",\n]/.test(text) ? `"${text.replace(/"/g, '""')}"` : text;
  };
  const csv = [header, ...rows]
    .map((row) => row.map(cell).join(','))
    .join('\r\n');
  const blob = new Blob(['﻿' + csv], { type: 'text/csv;charset=utf-8' });
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = fileName;
  link.click();
  URL.revokeObjectURL(url);
}

/**
 * Dropdown values the inventory screens share (branches, locations, racks, units, suppliers),
 * loaded once per visit and reloaded after a change on the setup screens.
 */
@Injectable({ providedIn: 'root' })
export class InventoryLookups {
  private readonly api = inject(ApiClient);
  private readonly racksByLocation = new Map<number, Observable<RackOut[]>>();
  private branches$?: Observable<BranchOption[]>;
  private locations$?: Observable<LocationOut[]>;
  private uoms$?: Observable<UomOut[]>;
  private suppliers$?: Observable<SupplierOut[]>;

  branches(): Observable<BranchOption[]> {
    this.branches$ ??= this.cached(this.api.call(listInventoryBranches));
    return this.branches$;
  }

  /** Active stock locations of the user's branches. */
  locations(): Observable<LocationOut[]> {
    this.locations$ ??= this.cached(
      this.api
        .call(listLocations, { status: 'active' })
        .pipe(map((rows) => rows.filter((l) => l.isStockLocation))),
    );
    return this.locations$;
  }

  racks(locationId: number | null | undefined): Observable<RackOut[]> {
    if (!locationId) return of([]);
    let racks = this.racksByLocation.get(locationId);
    if (!racks) {
      racks = this.cached(
        this.api.call(listRacks, { locationId, status: 'active' }),
      );
      this.racksByLocation.set(locationId, racks);
    }
    return racks;
  }

  uoms(): Observable<UomOut[]> {
    this.uoms$ ??= this.cached(this.api.call(listUoms, { status: 'active' }));
    return this.uoms$;
  }

  /** Active suppliers (first 200 by name) for the GRN and opening-stock forms. */
  suppliers(): Observable<SupplierOut[]> {
    this.suppliers$ ??= this.cached(
      this.api
        .call(listSuppliers, { status: 'active', pageSize: 200, sort: 'name' })
        .pipe(map((page) => page.items)),
    );
    return this.suppliers$;
  }

  /** Forget cached values after a master changes. */
  reset(): void {
    this.branches$ = undefined;
    this.locations$ = undefined;
    this.uoms$ = undefined;
    this.suppliers$ = undefined;
    this.racksByLocation.clear();
  }

  private cached<T>(source: Observable<T[]>): Observable<T[]> {
    return source.pipe(
      catchError(() => of([] as T[])),
      shareReplay({ bufferSize: 1, refCount: false }),
    );
  }
}

/** "BBSR · Main store" style label of a location. */
export function locationLabel(
  location: Pick<LocationOut, 'branchName' | 'name'>,
): string {
  return `${location.branchName} · ${location.name}`;
}
