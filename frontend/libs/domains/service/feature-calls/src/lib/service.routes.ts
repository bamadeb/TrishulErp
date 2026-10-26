import { Route } from '@angular/router';
import { permissionGuard } from '@trishul/core-auth';
import { SERVICE_CALL_VIEW_PERMISSIONS } from '@trishul/service-data-access';
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
];
