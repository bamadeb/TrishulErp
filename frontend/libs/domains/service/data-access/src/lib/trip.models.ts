import { CallTripHistoryItem, ListMyTrips$Params } from '@trishul/core-api';

// API types come from the generated client; only what the UI adds is defined here.
export type {
  CallTripHistoryItem,
  TripAdjustmentItem,
  AdjustDistanceInput,
  TripOut,
  TripListItem,
} from '@trishul/core-api';

export type TripStatus = CallTripHistoryItem['status'];
export type TripType = CallTripHistoryItem['tripType'];

/** Manually adjust a trip's distance. The API checks the same code. */
export const TRIP_ADJUST_PERMISSION = 'trk.trip.adjust';

/**
 * Any of these may open a call's trip history. Used by the route guard and the menu.
 * The API checks the same codes: backend service/router.py (CAN_VIEW_CALL_TRIPS).
 */
export const TRIP_HISTORY_VIEW_PERMISSIONS = [
  'svc.call.view',
  'svc.call.create',
  'svc.call.assign',
  'svc.call.view.assigned',
  'trk.trip.view.team',
] as const;

/** An engineer's own trip list. The API checks the same code (trk/router.py list_my_trips). */
export const MY_TRIPS_PERMISSION = 'trk.trip.manage';

export type MyTripsQuery = ListMyTrips$Params &
  Required<Pick<ListMyTrips$Params, 'page' | 'pageSize'>>;

/** Status filter options for the trip lists. Stops compiling if the API adds a status. */
export const TRIP_STATUSES = [
  'In progress',
  'Completed',
  'Auto closed',
] as const satisfies readonly TripStatus[];
