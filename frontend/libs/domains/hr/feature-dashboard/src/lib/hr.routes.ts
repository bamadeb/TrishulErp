import { Route } from '@angular/router';
import { permissionGuard } from '@trishul/core-auth';
import {
  EMPLOYEE_MANAGE_PERMISSION,
  EMPLOYEE_VIEW_PERMISSIONS,
} from '@trishul/hr-data-access';
import { HrDashboardPage } from './dashboard/hr-dashboard.page';
import { OrganizationPage } from './organization/organization.page';
import { ReportingStructurePage } from './reporting/reporting-structure.page';
import { AttendanceDailyPage } from './attendance/attendance-daily.page';
import { AttendanceDashboardPage } from './attendance/attendance-dashboard.page';
import { AttendanceExceptionsPage } from './attendance/attendance-exceptions.page';
import { AttendanceFinalizationPage } from './attendance/attendance-finalization.page';
import { AttendanceMusterPage } from './attendance/attendance-muster.page';
import { AttendanceRegularizationPage } from './attendance/attendance-regularization.page';
import { AttendanceRulesPage } from './attendance/attendance-rules.page';
import { biometricRoutes } from './biometric/biometric.routes';
import { faceAttendanceRoutes } from './face-attendance/face-attendance.routes';
import { leaveRoutes } from './leave/leave.routes';
import { payrollRoutes } from './payroll/payroll.routes';
import { EmployeeFormPage } from './employees/form/employee-form.page';
import { EmployeeListPage } from './employees/list/employee-list.page';

/** Lazy-loaded under /hr. */
export const hrRoutes: Route[] = [
  { path: '', pathMatch: 'full', redirectTo: 'dashboard' },
  {
    path: 'dashboard',
    title: 'HR Dashboard',
    canActivate: [permissionGuard(...EMPLOYEE_VIEW_PERMISSIONS)],
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
    path: 'reporting',
    title: 'Reporting Structure',
    canActivate: [permissionGuard(...EMPLOYEE_VIEW_PERMISSIONS)],
    component: ReportingStructurePage,
  },
  {
    path: 'attendance',
    canActivate: [permissionGuard(...EMPLOYEE_VIEW_PERMISSIONS)],
    children: [
      { path: '', pathMatch: 'full', redirectTo: 'dashboard' },
      {
        path: 'dashboard',
        title: 'Attendance Dashboard',
        canActivate: [permissionGuard(...EMPLOYEE_VIEW_PERMISSIONS)],
        component: AttendanceDashboardPage,
      },
      {
        path: 'daily',
        title: 'Daily Attendance',
        canActivate: [permissionGuard(...EMPLOYEE_VIEW_PERMISSIONS)],
        component: AttendanceDailyPage,
      },
      {
        path: 'monthly-muster',
        title: 'Monthly Muster',
        canActivate: [permissionGuard(...EMPLOYEE_VIEW_PERMISSIONS)],
        component: AttendanceMusterPage,
      },
      {
        path: 'exceptions',
        title: 'Attendance Exceptions',
        canActivate: [permissionGuard(...EMPLOYEE_VIEW_PERMISSIONS)],
        component: AttendanceExceptionsPage,
      },
      {
        path: 'regularization',
        title: 'Attendance Regularization',
        data: { screenTitle: 'Attendance Regularization' },
        canActivate: [permissionGuard(...EMPLOYEE_VIEW_PERMISSIONS)],
        component: AttendanceRegularizationPage,
      },
      {
        path: 'rules',
        title: 'Shift & Attendance Rules',
        canActivate: [permissionGuard(...EMPLOYEE_VIEW_PERMISSIONS)],
        component: AttendanceRulesPage,
      },
      {
        path: 'finalization',
        title: 'Attendance Finalization',
        canActivate: [permissionGuard(...EMPLOYEE_VIEW_PERMISSIONS)],
        component: AttendanceFinalizationPage,
      },
    ],
  },
  {
    path: 'biometric',
    children: biometricRoutes,
  },
  {
    path: 'face-attendance',
    children: faceAttendanceRoutes,
  },
  {
    path: 'leave',
    children: leaveRoutes,
  },
  {
    path: 'payroll',
    children: payrollRoutes,
  },
];
