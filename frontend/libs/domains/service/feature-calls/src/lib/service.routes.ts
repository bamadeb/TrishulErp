import { Route } from '@angular/router';
import { permissionGuard } from '@trishul/core-auth';
import {
  SERVICE_CALL_CREATE_PERMISSION,
  SERVICE_CALL_IMPORT_PERMISSION,
  SERVICE_CALL_OPEN_PERMISSIONS,
  SERVICE_CALL_VIEW_PERMISSIONS,
} from '@trishul/service-data-access';
import { BydImportPage } from './byd-import.page';
import { CallDetailPage } from './call-detail.page';
import { CallFormPage } from './call-form.page';
import { CallListPage } from './call-list.page';

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
    path: 'calls/:callId',
    title: 'Service call',
    canActivate: [permissionGuard(...SERVICE_CALL_OPEN_PERMISSIONS)],
    component: CallDetailPage,
  },
];
