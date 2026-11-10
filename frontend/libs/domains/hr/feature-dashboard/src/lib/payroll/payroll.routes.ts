import { Route } from '@angular/router';
import { permissionGuard } from '@trishul/core-auth';
import { EMPLOYEE_VIEW_PERMISSIONS } from '@trishul/hr-data-access';
import { PayrollApprovalsPage } from './approvals/payroll-approvals.page';
import { ClaimsPage } from './claims/claims.page';
import { SalaryComponentsPage } from './components/salary-components.page';
import { SalaryTemplatesPage } from './salary-templates.page';
import { StatutoryPage } from './compliance/statutory.page';
import { PayrollDashboardPage } from './dashboard/payroll-dashboard.page';
import { PayslipsPage } from './payslips/payslips.page';
import { PayrollProcessingPage } from './processing/payroll-processing.page';
import { PayrollReportsPage } from './reports/payroll-reports.page';
import { SalaryStructurePage } from './salary-structure/salary-structure.page';
import { PayrollSettingsPage } from './settings/payroll-settings.page';
import { TadaImportPage } from './tada-import/tada-import.page';
import { TadaReportPage } from './tada/tada-report.page';

/** Hardcoded payroll prototype under /hr/payroll. */
export const payrollRoutes: Route[] = [
  { path: '', pathMatch: 'full', redirectTo: 'dashboard' },
  {
    path: 'dashboard',
    title: 'Payroll Dashboard',
    canActivate: [permissionGuard(...EMPLOYEE_VIEW_PERMISSIONS)],
    component: PayrollDashboardPage,
  },
  {
    path: 'salary-structure',
    title: 'Employee Salary Structure',
    canActivate: [permissionGuard(...EMPLOYEE_VIEW_PERMISSIONS)],
    component: SalaryStructurePage,
  },
  {
    path: 'components',
    title: 'Salary Components',
    canActivate: [permissionGuard(...EMPLOYEE_VIEW_PERMISSIONS)],
    component: SalaryComponentsPage,
  },
  {
    path: 'templates',
    title: 'Salary Templates',
    canActivate: [permissionGuard(...EMPLOYEE_VIEW_PERMISSIONS)],
    component: SalaryTemplatesPage,
  },
  {
    path: 'processing',
    title: 'Payroll Processing',
    canActivate: [permissionGuard(...EMPLOYEE_VIEW_PERMISSIONS)],
    component: PayrollProcessingPage,
  },
  {
    path: 'approvals',
    title: 'Payroll Approvals',
    canActivate: [permissionGuard(...EMPLOYEE_VIEW_PERMISSIONS)],
    component: PayrollApprovalsPage,
  },
  {
    path: 'payslips',
    title: 'Payslips',
    canActivate: [permissionGuard(...EMPLOYEE_VIEW_PERMISSIONS)],
    component: PayslipsPage,
  },
  {
    path: 'claims',
    title: 'Reimbursements and claims',
    canActivate: [permissionGuard(...EMPLOYEE_VIEW_PERMISSIONS)],
    component: ClaimsPage,
  },
  {
    path: 'tada',
    title: 'Service Engineer TA/DA Management',
    canActivate: [permissionGuard(...EMPLOYEE_VIEW_PERMISSIONS)],
    component: TadaReportPage,
  },
  {
    path: 'tada-import',
    title: 'TA/DA Import',
    canActivate: [permissionGuard(...EMPLOYEE_VIEW_PERMISSIONS)],
    component: TadaImportPage,
  },
  {
    path: 'compliance',
    title: 'Statutory Compliance',
    canActivate: [permissionGuard(...EMPLOYEE_VIEW_PERMISSIONS)],
    component: StatutoryPage,
  },
  {
    path: 'reports',
    title: 'Payroll Reports',
    canActivate: [permissionGuard(...EMPLOYEE_VIEW_PERMISSIONS)],
    component: PayrollReportsPage,
  },
  {
    path: 'settings',
    title: 'Payroll Settings',
    canActivate: [permissionGuard(...EMPLOYEE_VIEW_PERMISSIONS)],
    component: PayrollSettingsPage,
  },
];
