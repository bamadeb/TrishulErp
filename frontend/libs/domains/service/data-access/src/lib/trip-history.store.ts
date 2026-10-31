import { computed, inject } from '@angular/core';
import {
  patchState,
  signalStore,
  withComputed,
  withMethods,
  withState,
} from '@ngrx/signals';
import { rxMethod } from '@ngrx/signals/rxjs-interop';
import { EMPTY, catchError, pipe, switchMap, tap } from 'rxjs';
import { TripApi } from './trip.api';
import {
  CallTripHistoryItem,
  TripAdjustmentItem,
  TripOut,
} from './trip.models';

interface TripHistoryState {
  callId: number | null;
  items: CallTripHistoryItem[];
  loading: boolean;
  selectedTripId: number | null;
  adjustments: TripAdjustmentItem[];
  adjustmentsLoading: boolean;
}

const initialState: TripHistoryState = {
  callId: null,
  items: [],
  loading: false,
  selectedTripId: null,
  adjustments: [],
  adjustmentsLoading: false,
};

/** State of a service call's trip-history page. Provide it in the page component, not in root. */
export const TripHistoryStore = signalStore(
  withState(initialState),
  withComputed((store) => ({
    selectedTrip: computed(
      () =>
        store.items().find((t) => t.id === store.selectedTripId()) ?? null,
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

    const load = rxMethod<number>(
      pipe(
        tap((callId) => patchState(store, { callId, loading: true })),
        switchMap((callId) =>
          api.callTrips(callId).pipe(
            tap((items) => {
              patchState(store, { items, loading: false });
              // Default to the newest trip so the detail pane is never empty.
              select(items.length ? items[items.length - 1].id : null);
            }),
            catchError(() => {
              patchState(store, { items: [], loading: false });
              select(null);
              return EMPTY;
            }),
          ),
        ),
      ),
    );

    return {
      load,
      select,
      reload(): void {
        const callId = store.callId();
        if (callId !== null) load(callId);
      },
      /** After a successful adjustment: fold the server's new values into the row and refresh the trail. */
      onAdjusted(trip: TripOut): void {
        patchState(store, {
          items: store.items().map((t) =>
            t.id === trip.id
              ? {
                  ...t,
                  adjustedDistanceKm: trip.adjustedDistanceKm,
                  isDistanceAdjusted: trip.isDistanceAdjusted,
                  effectiveDistanceKm: trip.effectiveDistanceKm,
                  rowVersion: trip.rowVersion,
                  adjustmentCount: t.adjustmentCount + 1,
                }
              : t,
          ),
        });
        if (store.selectedTripId() === trip.id) loadAdjustments(trip.id);
      },
    };
  }),
);
