import { Route } from '@angular/router';
import { permissionGuard } from '@trishul/core-auth';
import { LEAVE_VIEW_PERMISSIONS } from '@trishul/hr-data-access';
import { HrPlaceholderPage } from '../dashboard/hr-placeholder.page';
import { LeaveBalancePage } from './leave-balance.page';
import { LeaveCalendarPage } from './leave-calendar.page';
import { LeaveDashboardPage } from './leave-dashboard.page';
import { LeaveEmployeesPage } from './leave-employees.page';
import { LeaveHolidaysPage } from './leave-holidays.page';
import { LeaveMinePage } from './leave-mine.page';
import { LeavePoliciesPage } from './leave-policies.page';
import { LeaveRequestsPage } from './leave-requests.page';
import { LeaveTypesPage } from './leave-types.page';

const view = { canActivate: [permissionGuard(...LEAVE_VIEW_PERMISSIONS)] };

function later(path: string, title: string): Route {
  return { path, title, ...view, data: { screenTitle: title }, component: HrPlaceholderPage };
}

/** Leave screens under /hr/leave. Dashboard, My Leave, employees, requests, balances, calendar, holidays, types and policies are live. */
export const leaveRoutes: Route[] = [
  { path: '', pathMatch: 'full', redirectTo: 'dashboard' },
  { path: 'dashboard', title: 'Leave Dashboard', ...view, component: LeaveDashboardPage },
  { path: 'mine', title: 'My Leave', ...view, component: LeaveMinePage },
  { path: 'employees', title: 'Employee Leaves', ...view, component: LeaveEmployeesPage },
  { path: 'requests', title: 'Leave Requests', ...view, component: LeaveRequestsPage },
  { path: 'balances', title: 'Leave Balance', ...view, component: LeaveBalancePage },
  { path: 'calendar', title: 'Leave Calendar', ...view, component: LeaveCalendarPage },
  { path: 'holidays', title: 'Holiday Calendar', ...view, component: LeaveHolidaysPage },
  {
    path: 'policies',
    title: 'Leave Policies',
    ...view,
    component: LeavePoliciesPage,
  },
  {
    path: 'types',
    title: 'Leave Types',
    ...view,
    component: LeaveTypesPage,
  },
  later('reports', 'Leave Reports'),
];
