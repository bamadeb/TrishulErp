import {
  ALERT_RULE_VIEW_PERMISSIONS,
  CUSTOMER_VIEW_PERMISSIONS,
  ROLE_VIEW_PERMISSIONS,
  TEAM_VIEW_PERMISSIONS,
  USER_VIEW_PERMISSIONS,
} from '@trishul/admin-data-access';
import { NavItem } from '@trishul/core-layout';
import { EMPLOYEE_VIEW_PERMISSIONS } from '@trishul/hr-data-access';
import {
  ASC_VIEW_PERMISSIONS,
  MACHINE_VIEW_PERMISSIONS,
  MY_TRIPS_PERMISSION,
  SERVICE_CALL_ASSIGN_PERMISSION,
  SERVICE_CALL_IMPORT_LOG_PERMISSIONS,
  SERVICE_CALL_IMPORT_PERMISSION,
  SERVICE_CALL_VIEW_PERMISSIONS,
} from '@trishul/service-data-access';

/** Side menu. Add each module's entries as its routes are built. Icons are Material Symbols names. */
export const navItems: NavItem[] = [
  { label: 'Dashboard', icon: 'dashboard', route: '/' },
  {
    label: 'My alerts',
    icon: 'notifications',
    route: '/alerts',
    permissions: ['core.alert.view'],
  },
  {
    label: 'Service',
    icon: 'build',
    children: [
      {
        label: 'Service calls',
        icon: 'support_agent',
        route: '/service/calls',
        permissions: [...SERVICE_CALL_VIEW_PERMISSIONS],
      },
      {
        label: 'Assign engineers',
        icon: 'assignment_ind',
        route: '/service/assign',
        permissions: [SERVICE_CALL_ASSIGN_PERMISSION],
      },
      {
        label: 'Machines',
        icon: 'precision_manufacturing',
        route: '/service/machines',
        permissions: [...MACHINE_VIEW_PERMISSIONS],
      },
      {
        label: 'ASC contracts',
        icon: 'verified',
        route: '/service/asc',
        permissions: [...ASC_VIEW_PERMISSIONS],
      },
      {
        label: 'My trips',
        icon: 'route',
        route: '/service/my-trips',
        permissions: [MY_TRIPS_PERMISSION],
      },
      {
        label: 'Import calls',
        icon: 'upload_file',
        route: '/service/calls/import',
        permissions: [SERVICE_CALL_IMPORT_PERMISSION],
      },
      {
        label: 'Import log',
        icon: 'history',
        route: '/service/imports',
        permissions: [...SERVICE_CALL_IMPORT_LOG_PERMISSIONS],
      },
    ],
  },
  {
    label: 'Administration',
    icon: 'admin_panel_settings',
    children: [
      {
        label: 'Customers',
        icon: 'groups',
        route: '/admin/customers',
        permissions: [...CUSTOMER_VIEW_PERMISSIONS],
      },
      {
        label: 'Users',
        icon: 'manage_accounts',
        route: '/admin/users',
        permissions: [...USER_VIEW_PERMISSIONS],
      },
      {
        label: 'Roles & permissions',
        icon: 'admin_panel_settings',
        route: '/admin/roles',
        permissions: [...ROLE_VIEW_PERMISSIONS],
      },
      {
        label: 'Teams',
        icon: 'groups',
        route: '/admin/teams',
        permissions: [...TEAM_VIEW_PERMISSIONS],
      },
      {
        label: 'Alert rules',
        icon: 'rule',
        route: '/admin/alert-rules',
        permissions: [...ALERT_RULE_VIEW_PERMISSIONS],
      },
    ],
  },
  {
    label: 'HR Management',
    icon: 'diversity_3',
    children: [
      { label: 'HR Dashboard', icon: 'insights', route: '/hr/dashboard' },
      {
        label: 'Employee Management',
        icon: 'badge',
        route: '/hr/employees',
        permissions: [...EMPLOYEE_VIEW_PERMISSIONS],
      },
      {
        label: 'Organization Management',
        icon: 'account_tree',
        route: '/hr/organization',
        permissions: [...EMPLOYEE_VIEW_PERMISSIONS],
      },
      {
        label: 'Payroll Management',
        icon: 'payments',
        permissions: [...EMPLOYEE_VIEW_PERMISSIONS],
        children: [
          { label: 'Payroll Dashboard', icon: 'insights', route: '/hr/payroll/dashboard' },
          { label: 'Employee Salary Structure', icon: 'account_balance', route: '/hr/payroll/salary-structure' },
          { label: 'Salary Components', icon: 'category', route: '/hr/payroll/components' },
          { label: 'Payroll Processing', icon: 'play_circle', route: '/hr/payroll/processing' },
          { label: 'Payroll Approvals', icon: 'fact_check', route: '/hr/payroll/approvals' },
          { label: 'Payslips', icon: 'receipt_long', route: '/hr/payroll/payslips' },
          { label: 'Reimbursements & Claims', icon: 'request_quote', route: '/hr/payroll/claims' },
          { label: 'Service Engineer TA/DA Report', icon: 'two_wheeler', route: '/hr/payroll/tada' },
          { label: 'TA/DA Import', icon: 'upload_file', route: '/hr/payroll/tada-import' },
          { label: 'Statutory Compliance', icon: 'gavel', route: '/hr/payroll/compliance' },
          { label: 'Payroll Reports', icon: 'assessment', route: '/hr/payroll/reports' },
          { label: 'Payroll Settings', icon: 'settings', route: '/hr/payroll/settings' },
        ],
      },
    ],
  },
];
