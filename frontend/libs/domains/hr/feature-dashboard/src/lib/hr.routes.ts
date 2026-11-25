import { inject } from '@angular/core';
import { Route } from '@angular/router';
import { AuthStore, permissionGuard } from '@trishul/core-auth';
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
import { AttendanceMinePage } from './attendance/attendance-mine.page';
import { AttendanceMusterPage } from './attendance/attendance-muster.page';
import { AttendanceRegularizationPage } from './attendance/attendance-regularization.page';
import { AttendanceReportsPage } from './attendance/attendance-reports.page';
import { AttendanceRulesPage } from './attendance/attendance-rules.page';
import { biometricRoutes } from './biometric/biometric.routes';
import { faceAttendanceRoutes } from './face-attendance/face-attendance.routes';
import { leaveRoutes } from './leave/leave.routes';
import { payrollRoutes } from './payroll/payroll.routes';
import { EmployeeFormPage } from './employees/form/employee-form.page';
import { EmployeeListPage } from './employees/list/employee-list.page';

const hrManage = { canActivate: [permissionGuard(EMPLOYEE_MANAGE_PERMISSION)] };
const employeeView = { canActivate: [permissionGuard(...EMPLOYEE_VIEW_PERMISSIONS)] };

/** Admin/HR → org dashboard; employees → My Attendance only. */
function attendanceHomeRedirect(): string {
  return inject(AuthStore).hasPermission(EMPLOYEE_MANAGE_PERMISSION) ? 'dashboard' : 'mine';
}

/** Lazy-loaded under /hr. */
export const hrRoutes: Route[] = [
  { path: '', pathMatch: 'full', redirectTo: 'dashboard' },
  {
    path: 'dashboard',
    title: 'HR Dashboard',
    ...employeeView,
    component: HrDashboardPage,
  },
  {
    path: 'employees',
    title: 'Employees',
    ...employeeView,
    component: EmployeeListPage,
  },
  {
    path: 'employees/new',
    title: 'Add employee',
    ...hrManage,
    component: EmployeeFormPage,
  },
  {
    path: 'employees/:employeeId',
    title: 'Employee',
    ...employeeView,
    component: EmployeeFormPage,
  },
  {
    path: 'organization',
    title: 'Organization Management',
    data: { screenTitle: 'Organization Management' },
    ...employeeView,
    component: OrganizationPage,
  },
  {
    path: 'reporting',
    title: 'Reporting Structure',
    ...employeeView,
    component: ReportingStructurePage,
  },
  {
    path: 'attendance',
    ...employeeView,
    children: [
      { path: '', pathMatch: 'full', redirectTo: attendanceHomeRedirect },
      {
        path: 'dashboard',
        title: 'Attendance Dashboard',
        ...hrManage,
        component: AttendanceDashboardPage,
      },
      {
        path: 'mine',
        title: 'My Attendance',
        ...employeeView,
        component: AttendanceMinePage,
      },
      {
        path: 'daily',
        title: 'Daily Attendance',
        ...hrManage,
        component: AttendanceDailyPage,
      },
      {
        path: 'monthly-muster',
        title: 'Monthly Muster',
        ...hrManage,
        component: AttendanceMusterPage,
      },
      {
        path: 'muster',
        pathMatch: 'full',
        redirectTo: 'monthly-muster',
      },
      {
        path: 'exceptions',
        title: 'Attendance Exceptions',
        ...hrManage,
        component: AttendanceExceptionsPage,
      },
      {
        path: 'regularization',
        title: 'Attendance Regularization',
        data: { screenTitle: 'Attendance Regularization' },
        ...hrManage,
        component: AttendanceRegularizationPage,
      },
      {
        path: 'rules',
        title: 'Shift & Attendance Rules',
        ...hrManage,
        component: AttendanceRulesPage,
      },
      {
        path: 'finalization',
        title: 'Attendance Finalization',
        ...hrManage,
        component: AttendanceFinalizationPage,
      },
      {
        path: 'reports',
        title: 'Attendance Reports',
        ...hrManage,
        component: AttendanceReportsPage,
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
