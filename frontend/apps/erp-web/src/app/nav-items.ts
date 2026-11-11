import {
  ALERT_RULE_VIEW_PERMISSIONS,
  CUSTOMER_VIEW_PERMISSIONS,
  DOCUMENT_VIEW_PERMISSIONS,
  ROLE_VIEW_PERMISSIONS,
  TEAM_VIEW_PERMISSIONS,
  USER_VIEW_PERMISSIONS,
  WAREHOUSE_VIEW_PERMISSIONS,
} from '@trishul/admin-data-access';
import { NavItem } from '@trishul/core-layout';
import { EMPLOYEE_VIEW_PERMISSIONS } from '@trishul/hr-data-access';
import {
  INV_ADJUSTMENT_VIEW_PERMISSIONS,
  INV_ANY_PERMISSIONS,
  INV_GRN_VIEW_PERMISSIONS,
  INV_ITEM_VIEW_PERMISSIONS,
  INV_STOCK_USER_PERMISSIONS,
  INV_STOCK_VIEW,
  INV_TRANSFER_VIEW_PERMISSIONS,
} from '@trishul/inventory-data-access';
import {
  PUR_ACCOUNT_PERMISSIONS,
  PUR_GRN_PERMISSIONS,
  PUR_PO_PERMISSIONS,
  PUR_SUPPLIER_PERMISSIONS,
} from '@trishul/purchases-data-access';
import {
  SAL_ACCOUNT_PERMISSIONS,
  SAL_DELIVERY_PERMISSIONS,
  SAL_ORDER_PERMISSIONS,
  SAL_QUOTATION_PERMISSIONS,
  SAL_USER_PERMISSIONS,
} from '@trishul/sales-data-access';
import {
  ASC_VIEW_PERMISSIONS,
  MACHINE_VIEW_PERMISSIONS,
  MY_TRIPS_PERMISSION,
  SERVICE_CALL_ASSIGN_PERMISSION,
  SERVICE_CALL_IMPORT_LOG_PERMISSIONS,
  CHECKLIST_VIEW_PERMISSIONS,
  SERVICE_CALL_OPEN_PERMISSIONS,
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
        label: 'Service reports',
        icon: 'assignment',
        route: '/service/reports',
        permissions: [...SERVICE_CALL_OPEN_PERMISSIONS],
      },
      {
        label: 'Inspection checklists',
        icon: 'checklist',
        route: '/service/checklists',
        permissions: [...CHECKLIST_VIEW_PERMISSIONS],
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
    label: 'Inventory',
    icon: 'inventory_2',
    children: [
      {
        label: 'Items',
        icon: 'category',
        route: '/inventory/items',
        permissions: [...INV_ANY_PERMISSIONS],
      },
      {
        label: 'Stock by batch',
        icon: 'inventory',
        route: '/inventory/stock',
        permissions: [...INV_STOCK_USER_PERMISSIONS],
      },
      {
        label: 'Ageing report',
        icon: 'hourglass_bottom',
        route: '/inventory/ageing',
        permissions: [INV_STOCK_VIEW],
      },
      {
        label: 'Opening stock',
        icon: 'playlist_add',
        route: '/inventory/opening-stock',
        permissions: [...INV_GRN_VIEW_PERMISSIONS],
      },
      {
        label: 'Transfers',
        icon: 'swap_horiz',
        route: '/inventory/transfers',
        permissions: [...INV_TRANSFER_VIEW_PERMISSIONS],
      },
      {
        label: 'Adjustments',
        icon: 'tune',
        route: '/inventory/adjustments',
        permissions: [...INV_ADJUSTMENT_VIEW_PERMISSIONS],
      },
      {
        label: 'Locations & racks',
        icon: 'shelves',
        route: '/inventory/locations',
        permissions: [...INV_ANY_PERMISSIONS],
      },
      {
        label: 'Item setup',
        icon: 'settings',
        route: '/inventory/setup',
        permissions: [...INV_ITEM_VIEW_PERMISSIONS],
      },
    ],
  },
  {
    label: 'Purchases',
    icon: 'shopping_cart',
    children: [
      {
        label: 'Purchase orders',
        icon: 'receipt',
        route: '/purchases/orders',
        permissions: [...PUR_PO_PERMISSIONS],
      },
      {
        label: 'Outstanding orders',
        icon: 'pending_actions',
        route: '/purchases/outstanding',
        permissions: [...PUR_PO_PERMISSIONS],
      },
      {
        label: 'Goods receipts (GRN)',
        icon: 'move_to_inbox',
        route: '/purchases/grns',
        permissions: [...PUR_GRN_PERMISSIONS],
      },
      {
        label: 'Supplier invoices',
        icon: 'receipt_long',
        route: '/purchases/invoices',
        permissions: [...PUR_ACCOUNT_PERMISSIONS],
      },
      {
        label: 'Payments',
        icon: 'payments',
        route: '/purchases/payments',
        permissions: [...PUR_ACCOUNT_PERMISSIONS],
      },
      {
        label: 'Credit notes',
        icon: 'assignment_return',
        route: '/purchases/credit-notes',
        permissions: [...PUR_ACCOUNT_PERMISSIONS],
      },
      {
        label: 'Allocations',
        icon: 'link',
        route: '/purchases/allocations',
        permissions: [...PUR_ACCOUNT_PERMISSIONS],
      },
      {
        label: 'Suppliers',
        icon: 'local_shipping',
        route: '/purchases/suppliers',
        permissions: [...PUR_SUPPLIER_PERMISSIONS],
      },
    ],
  },
  {
    label: 'Sales',
    icon: 'storefront',
    children: [
      {
        label: 'Quotations',
        icon: 'request_quote',
        route: '/sales/quotations',
        permissions: [...SAL_QUOTATION_PERMISSIONS],
      },
      {
        label: 'Sales orders',
        icon: 'shopping_bag',
        route: '/sales/orders',
        permissions: [...SAL_ORDER_PERMISSIONS],
      },
      {
        label: 'Orders to deliver',
        icon: 'pending_actions',
        route: '/sales/outstanding',
        permissions: [...SAL_ORDER_PERMISSIONS],
      },
      {
        label: 'Deliveries',
        icon: 'local_shipping',
        route: '/sales/deliveries',
        permissions: [...SAL_DELIVERY_PERMISSIONS],
      },
      {
        label: 'Sales invoices',
        icon: 'receipt_long',
        route: '/sales/invoices',
        permissions: [...SAL_ACCOUNT_PERMISSIONS],
      },
      {
        label: 'Receipts & advances',
        icon: 'payments',
        route: '/sales/receipts',
        permissions: [...SAL_ACCOUNT_PERMISSIONS],
      },
      {
        label: 'Allocations',
        icon: 'link',
        route: '/sales/allocations',
        permissions: [...SAL_ACCOUNT_PERMISSIONS],
      },
      {
        label: 'Customer accounts',
        icon: 'account_balance_wallet',
        route: '/sales/customers',
        permissions: [...SAL_USER_PERMISSIONS],
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
      {
        label: 'Documents',
        icon: 'folder_open',
        route: '/admin/documents',
        permissions: [...DOCUMENT_VIEW_PERMISSIONS],
      },
      {
        label: 'Warehouses',
        icon: 'warehouse',
        route: '/admin/warehouses',
        permissions: [...WAREHOUSE_VIEW_PERMISSIONS],
      },
    ],
  },
  {
    label: 'HR Management',
    icon: 'diversity_3',
    permissions: [...EMPLOYEE_VIEW_PERMISSIONS],
    children: [
      {
        label: 'HR Dashboard',
        icon: 'insights',
        route: '/hr/dashboard',
        permissions: [...EMPLOYEE_VIEW_PERMISSIONS],
      },
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
          { label: 'Salary Templates', icon: 'layers', route: '/hr/payroll/templates' },
          { label: 'Payroll Processing', icon: 'play_circle', route: '/hr/payroll/processing' },
          { label: 'Payroll Approvals', icon: 'fact_check', route: '/hr/payroll/approvals' },
          { label: 'Payslips', icon: 'receipt_long', route: '/hr/payroll/payslips' },
          { label: 'Reimbursements & Claims', icon: 'request_quote', route: '/hr/payroll/claims' },
          { label: 'Service Engineer TA/DA Management', icon: 'two_wheeler', route: '/hr/payroll/tada' },
          { label: 'TA/DA Import', icon: 'upload_file', route: '/hr/payroll/tada-import' },
          { label: 'Statutory Compliance', icon: 'gavel', route: '/hr/payroll/compliance' },
          { label: 'Payroll Reports', icon: 'assessment', route: '/hr/payroll/reports' },
          { label: 'Payroll Settings', icon: 'settings', route: '/hr/payroll/settings' },
        ],
      },
    ],
  },
];
