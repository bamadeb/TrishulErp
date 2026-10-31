import { computed, inject } from '@angular/core';
import {
  patchState,
  signalStore,
  withComputed,
  withHooks,
  withMethods,
  withState,
} from '@ngrx/signals';
import { rxMethod } from '@ngrx/signals/rxjs-interop';
import { EMPTY, catchError, pipe, switchMap, tap } from 'rxjs';
import { TripApi } from './trip.api';
import { MyTripsQuery, TripAdjustmentItem, TripListItem } from './trip.models';

interface MyTripsState {
  query: MyTripsQuery;
  items: TripListItem[];
  total: number;
  loading: boolean;
  selectedTripId: number | null;
  adjustments: TripAdjustmentItem[];
  adjustmentsLoading: boolean;
}

const initialState: MyTripsState = {
  query: { page: 1, pageSize: 20, sort: '-startAt' },
  items: [],
  total: 0,
  loading: false,
  selectedTripId: null,
  adjustments: [],
  adjustmentsLoading: false,
};

/**
 * State of the engineer's "My trips" page. Provide it in the page component, not in root.
 * Own trips span every branch, so unlike the team lists it does not reload on a branch switch.
 */
export const MyTripsStore = signalStore(
  withState(initialState),
  withComputed((store) => ({
    selectedTrip: computed(
      () => store.items().find((t) => t.id === store.selectedTripId()) ?? null,
    ),
  })),
  withMethods((store, api = inject(TripApi)) => {
    const loadAdjustments = rxMethod<number | null>(
      pipe(
        tap(() => patchState(store, { adjustmentsLoading: true })),
        switchMap((tripId) => {
          if (tripId === null) {
            patchState(store, { adjustments: [], adjustmentsLoading: false });
            return EMPTY;
          }
          return api.adjustments(tripId).pipe(
            tap((rows) =>
              patchState(store, {
                adjustments: rows,
                adjustmentsLoading: false,
              }),
            ),
            catchError(() => {
              patchState(store, { adjustmentsLoading: false });
              return EMPTY;
            }),
          );
        }),
      ),
    );

    const select = (tripId: number | null): void => {
      patchState(store, { selectedTripId: tripId });
      loadAdjustments(tripId);
    };

    // switchMap drops the response of a superseded query (fast typing, quick paging).
    const load = rxMethod<MyTripsQuery>(
      pipe(
        tap(() => patchState(store, { loading: true })),
        switchMap((query) =>
          api.myTrips(query).pipe(
            tap((page) => {
              patchState(store, {
                items: page.items,
                total: page.total,
                loading: false,
              });
              // Keep the selection if the trip is still on the page, else show the newest.
              const keep = page.items.some(
                (t) => t.id === store.selectedTripId(),
              );
              select(
                keep ? store.selectedTripId() : (page.items[0]?.id ?? null),
              );
            }),
            catchError(() => {
              patchState(store, { items: [], total: 0, loading: false });
              select(null);
              return EMPTY;
            }),
          ),
        ),
      ),
    );

    return {
      select,
      /** Merge filter / paging changes into the query and reload. Filter changes go back to page 1. */
      updateQuery(change: Partial<MyTripsQuery>): void {
        const resetPage = !('page' in change);
        patchState(store, {
          query: {
            ...store.query(),
            ...change,
            ...(resetPage ? { page: 1 } : {}),
          },
        });
        load(store.query());
      },
      reload(): void {
        load(store.query());
      },
    };
  }),
  withHooks({
    onInit(store) {
      store.reload();
    },
  }),
);
