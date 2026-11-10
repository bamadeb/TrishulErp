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
import { DashboardPage } from './dashboard.page';

export const appRoutes: Route[] = [
  // ?returnUrl=/service/calls brings the user back after signing in.
  {
    path: 'login',
    title: 'Sign in',
    canActivate: [guestGuard],
    component: LoginPage,
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
        loadChildren: () =>
          import('@trishul/hr-feature-dashboard').then((m) => m.hrRoutes),
      },
      {
        path: 'inventory',
        loadChildren: () =>
          import('@trishul/inventory-feature').then((m) => m.inventoryRoutes),
      },
      // Phase 1+: purchase, sales, presales, accounts, integration, reports.
      { path: 'forbidden', title: 'Access denied', component: ForbiddenPage },
      { path: '**', title: 'Not found', component: NotFoundPage },
    ],
  },
];
