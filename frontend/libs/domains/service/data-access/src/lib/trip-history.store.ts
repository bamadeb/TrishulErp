import { computed, inject } from '@angular/core';
import {
  patchState,
  signalStore,
  withComputed,
  withMethods,
  withState,
} from '@ngrx/signals';
import { rxMethod } from '@ngrx/signals/rxjs-interop';
import { EMPTY, catchError, forkJoin, of, pipe, switchMap, tap } from 'rxjs';
import { TripApi } from './trip.api';
import {
  CallTripHistoryItem,
  GpsDiagnosticItem,
  ManualTravelOut,
  TripAdjustmentItem,
  TripOut,
  TripRoute,
  TripSyncStatus,
} from './trip.models';

interface TripHistoryState {
  callId: number | null;
  items: CallTripHistoryItem[];
  loading: boolean;
  selectedTripId: number | null;
  adjustments: TripAdjustmentItem[];
  adjustmentsLoading: boolean;
  /** GPS evidence of the selected trip; each part fails independently. */
  route: TripRoute | null;
  diagnostics: GpsDiagnosticItem[];
  syncStatus: TripSyncStatus | null;
  evidenceLoading: boolean;
  evidenceFailed: boolean;
  /** Bus / Train / Other travel entered by hand for this call. */
  manualTravel: ManualTravelOut[];
  manualTravelLoading: boolean;
}

const initialState: TripHistoryState = {
  callId: null,
  items: [],
  loading: false,
  selectedTripId: null,
  adjustments: [],
  adjustmentsLoading: false,
  route: null,
  diagnostics: [],
  syncStatus: null,
  evidenceLoading: false,
  evidenceFailed: false,
  manualTravel: [],
  manualTravelLoading: false,
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

    const loadEvidence = rxMethod<number | null>(
      pipe(
        tap(() =>
          patchState(store, {
            route: null,
            diagnostics: [],
            syncStatus: null,
            evidenceFailed: false,
            evidenceLoading: true,
          }),
        ),
        switchMap((tripId) => {
          if (tripId === null) {
            patchState(store, { evidenceLoading: false });
            return EMPTY;
          }
          // A failed part must not hide the others, so each falls back to null.
          return forkJoin({
            route: api.route(tripId).pipe(catchError(() => of(null))),
            diagnostics: api
              .diagnostics(tripId)
              .pipe(catchError(() => of(null))),
            syncStatus: api.syncStatus(tripId).pipe(catchError(() => of(null))),
          }).pipe(
            tap((r) =>
              patchState(store, {
                route: r.route,
                diagnostics: r.diagnostics ?? [],
                syncStatus: r.syncStatus,
                evidenceFailed: !r.route && !r.diagnostics && !r.syncStatus,
                evidenceLoading: false,
              }),
            ),
          );
        }),
      ),
    );

    const select = (tripId: number | null): void => {
      patchState(store, { selectedTripId: tripId });
      loadAdjustments(tripId);
      loadEvidence(tripId);
    };

    const loadManualTravel = rxMethod<number>(
      pipe(
        tap(() => patchState(store, { manualTravelLoading: true })),
        switchMap((callId) =>
          api.manualTravel(callId).pipe(
            tap((manualTravel) =>
              patchState(store, { manualTravel, manualTravelLoading: false }),
            ),
            catchError(() => {
              patchState(store, { manualTravelLoading: false });
              return EMPTY;
            }),
          ),
        ),
      ),
    );

    const load = rxMethod<number>(
      pipe(
        tap((callId) => {
          patchState(store, { callId, loading: true });
          loadManualTravel(callId);
        }),
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
      reloadManualTravel(): void {
        const callId = store.callId();
        if (callId !== null) loadManualTravel(callId);
      },
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
