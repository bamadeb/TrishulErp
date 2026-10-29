import { Route } from '@angular/router';
import { LoginPage, authGuard, guestGuard } from '@trishul/core-auth';
import { ForbiddenPage, NotFoundPage, Shell } from '@trishul/core-layout';
import { DashboardPage } from './dashboard.page';
import { HrDashboardPage } from './hr/hr-dashboard.page';
import { HrPlaceholderPage } from './hr/hr-placeholder.page';

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
        path: 'hr/dashboard',
        title: 'HR Dashboard',
        component: HrDashboardPage,
      },
      {
        path: 'hr/attendance',
        title: 'Attendance',
        data: { screenTitle: 'Attendance' },
        component: HrPlaceholderPage,
      },
      {
        path: 'hr/leave',
        title: 'Leave requests',
        data: { screenTitle: 'Leave requests' },
        component: HrPlaceholderPage,
      },
      {
        path: 'hr/payroll',
        title: 'Payroll',
        data: { screenTitle: 'Payroll' },
        component: HrPlaceholderPage,
      },
      // Phase 1+: masters, inventory, purchase, sales, presales, accounts, integration, reports.
      { path: 'forbidden', title: 'Access denied', component: ForbiddenPage },
      { path: '**', title: 'Not found', component: NotFoundPage },
    ],
  },
];
