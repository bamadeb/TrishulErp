import { Injectable, inject } from '@angular/core';
import { Observable, map } from 'rxjs';
import {
  AdjustDistanceInput,
  ApiClient,
  CallTripHistoryItem,
  GpsDiagnosticItem,
  ManualTravelInput,
  ManualTravelOut,
  ManualTravelUpdate,
  VehicleTypeItem,
  TripRoute,
  TripSyncStatus,
  PageTripListItem,
  TripAdjustmentItem,
  TripOut,
  adjustTripDistance,
  createManualTravel,
  deleteManualTravel,
  getTripRoute,
  getTripSyncStatus,
  listMyTrips,
  listServiceCallManualTravel,
  listTripVehicleTypes,
  listTripGpsDiagnostics,
  listServiceCallTrips,
  listTripAdjustments,
  updateManualTravel,
  withRowVersion,
} from '@trishul/core-api';
import { MyTripsQuery } from './trip.models';

@Injectable({ providedIn: 'root' })
export class TripApi {
  private readonly api = inject(ApiClient);

  /** Every trip of a service call, across all its visits, oldest first. */
  callTrips(callId: number): Observable<CallTripHistoryItem[]> {
    return this.api.call(listServiceCallTrips, { callId });
  }

  /** Vehicle types that have no GPS trip (Bus, Train, Other): their travel is entered by hand. */
  manualVehicleTypes(): Observable<VehicleTypeItem[]> {
    return this.api
      .call(listTripVehicleTypes, {})
      .pipe(map((types) => types.filter((t) => !t.isGpsTracked)));
  }

  /** Manual travel of a call; reviewers see everyone's, an engineer only their own. */
  manualTravel(callId: number): Observable<ManualTravelOut[]> {
    return this.api.call(listServiceCallManualTravel, { callId });
  }

  createManualTravel(body: ManualTravelInput): Observable<ManualTravelOut> {
    return this.api.call(createManualTravel, { body });
  }

  updateManualTravel(
    entry: ManualTravelOut,
    body: ManualTravelUpdate,
  ): Observable<ManualTravelOut> {
    return this.api.call(
      updateManualTravel,
      { travelId: entry.id, body },
      withRowVersion(entry.rowVersion),
    );
  }

  deleteManualTravel(entry: ManualTravelOut): Observable<void> {
    return this.api.call(
      deleteManualTravel,
      { travelId: entry.id },
      withRowVersion(entry.rowVersion),
    );
  }

  /** The signed-in engineer's own trips; the API never returns anyone else's. */
  myTrips(query: MyTripsQuery): Observable<PageTripListItem> {
    return this.api.call(listMyTrips, query);
  }

  /** The GPS trail of a trip (thinned for drawing) and the quality of the full trail. */
  route(tripId: number): Observable<TripRoute> {
    return this.api.call(getTripRoute, { tripId });
  }

  /** GPS diagnostic events of a trip (GPS off, permission lost, power saving ...), oldest first. */
  diagnostics(tripId: number): Observable<GpsDiagnosticItem[]> {
    return this.api
      .call(listTripGpsDiagnostics, { tripId, page: 1, pageSize: 200 })
      .pipe(map((page) => page.items));
  }

  /** What the server has stored for the trip so far. */
  syncStatus(tripId: number): Observable<TripSyncStatus> {
    return this.api.call(getTripSyncStatus, { tripId });
  }

  /** The manual-adjustment audit trail of a trip, newest first. */
  adjustments(tripId: number): Observable<TripAdjustmentItem[]> {
    return this.api.call(listTripAdjustments, { tripId });
  }

  /**
   * Override a trip's distance (Team Lead). `rowVersion` is the value loaded with the trip; a
   * newer change by someone else gives 409. The GPS value is never overwritten server-side.
   */
  adjustDistance(
    tripId: number,
    body: AdjustDistanceInput,
    rowVersion: string,
  ): Observable<TripOut> {
    return this.api.call(
      adjustTripDistance,
      { tripId, body },
      withRowVersion(rowVersion),
    );
  }
}
