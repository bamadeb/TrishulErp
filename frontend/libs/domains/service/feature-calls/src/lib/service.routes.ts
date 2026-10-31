import { Route } from '@angular/router';
import { permissionGuard } from '@trishul/core-auth';
import {
  MY_TRIPS_PERMISSION,
  SERVICE_CALL_CREATE_PERMISSION,
  SERVICE_CALL_IMPORT_PERMISSION,
  SERVICE_CALL_OPEN_PERMISSIONS,
  SERVICE_CALL_VIEW_PERMISSIONS,
  TRIP_HISTORY_VIEW_PERMISSIONS,
} from '@trishul/service-data-access';
import { BydImportPage } from './byd-import.page';
import { CallDetailPage } from './call-detail.page';
import { CallFormPage } from './call-form.page';
import { CallListPage } from './call-list.page';
import { MyTripsPage } from './my-trips.page';
import { TripHistoryPage } from './trip-history.page';

/** Lazy-loaded under /service. */
export const serviceRoutes: Route[] = [
  { path: '', pathMatch: 'full', redirectTo: 'calls' },
  {
    path: 'calls',
    title: 'Service calls',
    canActivate: [permissionGuard(...SERVICE_CALL_VIEW_PERMISSIONS)],
    component: CallListPage,
  },
  {
    path: 'calls/new',
    title: 'New service call',
    canActivate: [permissionGuard(SERVICE_CALL_CREATE_PERMISSION)],
    component: CallFormPage,
  },
  {
    path: 'calls/import',
    title: 'Import service calls',
    canActivate: [permissionGuard(SERVICE_CALL_IMPORT_PERMISSION)],
    component: BydImportPage,
  },
  {
    path: 'my-trips',
    title: 'My trips',
    canActivate: [permissionGuard(MY_TRIPS_PERMISSION)],
    component: MyTripsPage,
  },
  {
    path: 'calls/:callId/trips',
    title: 'Trip history',
    canActivate: [permissionGuard(...TRIP_HISTORY_VIEW_PERMISSIONS)],
    component: TripHistoryPage,
  },
  {
    path: 'calls/:callId',
    title: 'Service call',
    canActivate: [permissionGuard(...SERVICE_CALL_OPEN_PERMISSIONS)],
    component: CallDetailPage,
  },
];
