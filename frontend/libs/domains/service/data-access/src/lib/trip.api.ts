import { Injectable, inject } from '@angular/core';
import { Observable } from 'rxjs';
import {
  AdjustDistanceInput,
  ApiClient,
  CallTripHistoryItem,
  PageTripListItem,
  TripAdjustmentItem,
  TripOut,
  adjustTripDistance,
  listMyTrips,
  listServiceCallTrips,
  listTripAdjustments,
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

  /** The signed-in engineer's own trips; the API never returns anyone else's. */
  myTrips(query: MyTripsQuery): Observable<PageTripListItem> {
    return this.api.call(listMyTrips, query);
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
