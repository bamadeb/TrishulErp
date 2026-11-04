import { Route } from '@angular/router';
import { permissionGuard } from '@trishul/core-auth';
import {
  ASC_IMPORT_PERMISSION,
  ASC_MANAGE_PERMISSION,
  ASC_VIEW_PERMISSIONS,
  MACHINE_MANAGE_PERMISSION,
  MACHINE_VIEW_PERMISSIONS,
  MY_TRIPS_PERMISSION,
  SERVICE_CALL_CREATE_PERMISSION,
  SERVICE_CALL_IMPORT_LOG_PERMISSIONS,
  SERVICE_CALL_IMPORT_PERMISSION,
  SERVICE_CALL_OPEN_PERMISSIONS,
  SERVICE_CALL_VIEW_PERMISSIONS,
  TRIP_HISTORY_VIEW_PERMISSIONS,
} from '@trishul/service-data-access';
import { AscFormPage } from './asc-form.page';
import { AscImportPage } from './asc-import.page';
import { AscListPage } from './asc-list.page';
import { AscPlansPage } from './asc-plans.page';
import { BydImportPage } from './byd-import.page';
import { CallDetailPage } from './call-detail.page';
import { CallFormPage } from './call-form.page';
import { CallListPage } from './call-list.page';
import { ImportLogDetailPage } from './import-log-detail.page';
import { ImportLogPage } from './import-log.page';
import { MachineFormPage } from './machine-form.page';
import { MachineListPage } from './machine-list.page';
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
    path: 'imports',
    title: 'Import log',
    canActivate: [permissionGuard(...SERVICE_CALL_IMPORT_LOG_PERMISSIONS)],
    component: ImportLogPage,
  },
  {
    path: 'imports/:importId',
    title: 'Import',
    canActivate: [permissionGuard(...SERVICE_CALL_IMPORT_LOG_PERMISSIONS)],
    component: ImportLogDetailPage,
  },
  {
    path: 'machines',
    title: 'Machines',
    canActivate: [permissionGuard(...MACHINE_VIEW_PERMISSIONS)],
    component: MachineListPage,
  },
  {
    path: 'machines/new',
    title: 'Add machine',
    canActivate: [permissionGuard(MACHINE_MANAGE_PERMISSION)],
    component: MachineFormPage,
  },
  {
    path: 'machines/:machineId',
    title: 'Machine',
    canActivate: [permissionGuard(...MACHINE_VIEW_PERMISSIONS)],
    component: MachineFormPage,
  },
  {
    path: 'asc',
    title: 'ASC contracts',
    canActivate: [permissionGuard(...ASC_VIEW_PERMISSIONS)],
    component: AscListPage,
  },
  {
    path: 'asc/new',
    title: 'Add ASC',
    canActivate: [permissionGuard(ASC_MANAGE_PERMISSION)],
    component: AscFormPage,
  },
  {
    path: 'asc/plans',
    title: 'ASC plans',
    canActivate: [permissionGuard(...ASC_VIEW_PERMISSIONS)],
    component: AscPlansPage,
  },
  {
    path: 'asc/import',
    title: 'Import ASC register',
    canActivate: [permissionGuard(ASC_IMPORT_PERMISSION)],
    component: AscImportPage,
  },
  {
    path: 'asc/:contractId',
    title: 'ASC',
    canActivate: [permissionGuard(...ASC_VIEW_PERMISSIONS)],
    component: AscFormPage,
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
