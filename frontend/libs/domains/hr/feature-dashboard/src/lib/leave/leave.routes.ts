import { Route } from '@angular/router';
import { permissionGuard } from '@trishul/core-auth';
import {
  EMPLOYEE_VIEW_PERMISSIONS,
  LEAVE_REQUEST_PERMISSIONS,
  LEAVE_VIEW_PERMISSIONS,
} from '@trishul/hr-data-access';
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

/** Every leave screen needs leave view. */
const view = { canActivate: [permissionGuard(...LEAVE_VIEW_PERMISSIONS)] };
/** HR screens: leave view and employee view (they were behind the employee-view HR menu before). */
const hr = {
  canActivate: [permissionGuard(...LEAVE_VIEW_PERMISSIONS), permissionGuard(...EMPLOYEE_VIEW_PERMISSIONS)],
};
/** The approval queue: leave view and an approver / HR permission. */
const approver = {
  canActivate: [permissionGuard(...LEAVE_VIEW_PERMISSIONS), permissionGuard(...LEAVE_REQUEST_PERMISSIONS)],
};

function later(path: string, title: string): Route {
  return { path, title, ...hr, data: { screenTitle: title }, component: HrPlaceholderPage };
}

/** Leave screens under /hr/leave. Dashboard, My Leave, employees, requests, balances, calendar, holidays, types and policies are live. */
export const leaveRoutes: Route[] = [
  // My Leave is the one screen every leave user has; HR lands on the dashboard from the menu.
  { path: '', pathMatch: 'full', redirectTo: 'mine' },
  { path: 'dashboard', title: 'Leave Dashboard', ...hr, component: LeaveDashboardPage },
  { path: 'mine', title: 'My Leave', ...view, component: LeaveMinePage },
  { path: 'employees', title: 'Employee Leaves', ...hr, component: LeaveEmployeesPage },
  { path: 'requests', title: 'Leave Requests', ...approver, component: LeaveRequestsPage },
  { path: 'balances', title: 'Leave Balance', ...hr, component: LeaveBalancePage },
  { path: 'calendar', title: 'Leave Calendar', ...hr, component: LeaveCalendarPage },
  { path: 'holidays', title: 'Holiday Calendar', ...view, component: LeaveHolidaysPage },
  {
    path: 'policies',
    title: 'Leave Policies',
    ...hr,
    component: LeavePoliciesPage,
  },
  {
    path: 'types',
    title: 'Leave Types',
    ...hr,
    component: LeaveTypesPage,
  },
  later('reports', 'Leave Reports'),
];
