import {
  ListServiceCalls$Params,
  ServiceCallListItem,
} from '@trishul/core-api';
import { allOf } from '@trishul/shared-util';

// API types come from the generated client; only what the UI adds is defined here.
export type { ServiceCallListItem } from '@trishul/core-api';
export type CallStatus = ServiceCallListItem['currentStatus'];
export type CallPriority = ServiceCallListItem['priority'];

/** Query of the call register; page and page size are always set. */
export type ServiceCallQuery = ListServiceCalls$Params &
  Required<Pick<ListServiceCalls$Params, 'page' | 'pageSize'>>;

/** Status filter options, in workflow order. Stops compiling if the API adds a status. */
export const CALL_STATUSES = allOf<CallStatus>()([
  'Logged',
  'Assigned',
  'Call ID linked',
  'Customer contacted',
  'Trip started',
  'Reached site',
  'In progress',
  'Report submitted',
  'Awaiting parts',
  'Parts ready',
  'Revisit scheduled',
  'Closed',
  'Pending OEM closure',
  'Completed',
  'Reopened',
  'Cancelled',
]);

export const CALL_PRIORITIES = allOf<CallPriority>()([
  'Critical',
  'High',
  'Normal',
  'Low',
]);

/**
 * Any of these may open the call register. Used by the route guard and the menu.
 * The API checks the same codes: backend/src/trishul_api/modules/service/router.py (CAN_VIEW_CALLS).
 */
export const SERVICE_CALL_VIEW_PERMISSIONS = [
  'svc.call.view',
  'svc.call.create',
  'svc.call.assign',
] as const;
