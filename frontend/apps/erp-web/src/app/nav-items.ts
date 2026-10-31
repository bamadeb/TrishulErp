import {
  CUSTOMER_VIEW_PERMISSIONS,
  EMPLOYEE_VIEW_PERMISSIONS,
  USER_VIEW_PERMISSIONS,
} from '@trishul/admin-data-access';
import { NavItem } from '@trishul/core-layout';
import {
  SERVICE_CALL_IMPORT_PERMISSION,
  SERVICE_CALL_VIEW_PERMISSIONS,
} from '@trishul/service-data-access';

/** Side menu. Add each module's entries as its routes are built. Icons are Material Symbols names. */
export const navItems: NavItem[] = [
  { label: 'Dashboard', icon: 'dashboard', route: '/' },
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
        label: 'Import calls',
        icon: 'upload_file',
        route: '/service/calls/import',
        permissions: [SERVICE_CALL_IMPORT_PERMISSION],
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
        label: 'Employees',
        icon: 'badge',
        route: '/admin/employees',
        permissions: [...EMPLOYEE_VIEW_PERMISSIONS],
      },
      {
        label: 'Users',
        icon: 'manage_accounts',
        route: '/admin/users',
        permissions: [...USER_VIEW_PERMISSIONS],
      },
    ],
  },
  {
    label: 'HR Management',
    icon: 'diversity_3',
    children: [
      { label: 'HR Dashboard', icon: 'insights', route: '/hr/dashboard' },
    ],
  },
];
