import { Route } from '@angular/router';
import { permissionGuard } from '@trishul/core-auth';
import {
  EMPLOYEE_MANAGE_PERMISSION,
  EMPLOYEE_VIEW_PERMISSIONS,
} from '@trishul/hr-data-access';
import { HrDashboardPage } from './dashboard/hr-dashboard.page';
import { HrPlaceholderPage } from './dashboard/hr-placeholder.page';
import { OrganizationPage } from './organization/organization.page';
import { payrollRoutes } from './payroll/payroll.routes';
import { EmployeeFormPage } from './employees/form/employee-form.page';
import { EmployeeListPage } from './employees/list/employee-list.page';

/** Lazy-loaded under /hr. */
export const hrRoutes: Route[] = [
  { path: '', pathMatch: 'full', redirectTo: 'dashboard' },
  {
    path: 'dashboard',
    title: 'HR Dashboard',
    component: HrDashboardPage,
  },
  {
    path: 'employees',
    title: 'Employees',
    canActivate: [permissionGuard(...EMPLOYEE_VIEW_PERMISSIONS)],
    component: EmployeeListPage,
  },
  {
    path: 'employees/new',
    title: 'Add employee',
    canActivate: [permissionGuard(EMPLOYEE_MANAGE_PERMISSION)],
    component: EmployeeFormPage,
  },
  {
    path: 'employees/:employeeId',
    title: 'Employee',
    canActivate: [permissionGuard(...EMPLOYEE_VIEW_PERMISSIONS)],
    component: EmployeeFormPage,
  },
  {
    path: 'organization',
    title: 'Organization Management',
    data: { screenTitle: 'Organization Management' },
    canActivate: [permissionGuard(...EMPLOYEE_VIEW_PERMISSIONS)],
    component: OrganizationPage,
  },
  {
    path: 'attendance',
    title: 'Attendance',
    data: { screenTitle: 'Attendance' },
    component: HrPlaceholderPage,
  },
  {
    path: 'leave',
    title: 'Leave requests',
    data: { screenTitle: 'Leave requests' },
    component: HrPlaceholderPage,
  },
  {
    path: 'payroll',
    children: payrollRoutes,
  },
];
