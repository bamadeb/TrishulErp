import { Route } from '@angular/router';
import { LoginPage, authGuard, guestGuard } from '@trishul/core-auth';
import { ForbiddenPage, NotFoundPage, Shell } from '@trishul/core-layout';
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
      // Phase 1+: masters, admin, inventory, purchase, sales, presales, hr, accounts, integration, reports.
      { path: 'forbidden', title: 'Access denied', component: ForbiddenPage },
      { path: '**', title: 'Not found', component: NotFoundPage },
    ],
  },
];
