import { Route } from '@angular/router';
import {
  LoginPage,
  authGuard,
  guestGuard,
  permissionGuard,
} from '@trishul/core-auth';
import {
  AlertsPage,
  ForbiddenPage,
  NotFoundPage,
  Shell,
} from '@trishul/core-layout';
import { EMPLOYEE_VIEW_PERMISSIONS } from '@trishul/hr-data-access';
import { DashboardPage } from './dashboard.page';

export const appRoutes: Route[] = [
  // ?returnUrl=/service/calls brings the user back after signing in.
  {
    path: 'login',
    title: 'Sign in',
    canActivate: [guestGuard],
    component: LoginPage,
  },
  // Printable documents (purchase order, payment voucher), without the app's menus.
  {
    path: 'print',
    canActivate: [authGuard],
    loadChildren: () =>
      import('@trishul/purchases-feature').then((m) => m.purchasesPrintRoutes),
  },
  {
    path: '',
    component: Shell,
    canActivate: [authGuard],
    children: [
      { path: '', title: 'Dashboard', component: DashboardPage },
      {
        path: 'service',
        loadChildren: () =>
          import('@trishul/service-feature-calls').then((m) => m.serviceRoutes),
      },
      {
        path: 'admin',
        loadChildren: () =>
          import('@trishul/admin-feature-users').then((m) => m.adminRoutes),
      },
      {
        path: 'alerts',
        title: 'My alerts',
        canActivate: [permissionGuard('core.alert.view')],
        component: AlertsPage,
      },
      {
        path: 'hr',
        canActivate: [permissionGuard(...EMPLOYEE_VIEW_PERMISSIONS)],
        loadChildren: () =>
          import('@trishul/hr-feature-dashboard').then((m) => m.hrRoutes),
      },
      {
        path: 'inventory',
        loadChildren: () =>
          import('@trishul/inventory-feature').then((m) => m.inventoryRoutes),
      },
      {
        path: 'purchases',
        loadChildren: () =>
          import('@trishul/purchases-feature').then((m) => m.purchasesRoutes),
      },
      // Phase 1+: sales, presales, accounts, integration, reports.
      { path: 'forbidden', title: 'Access denied', component: ForbiddenPage },
      { path: '**', title: 'Not found', component: NotFoundPage },
    ],
  },
];
