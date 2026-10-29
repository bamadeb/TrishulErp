import { Route } from '@angular/router';
import {
  CUSTOMER_MANAGE_PERMISSION,
  CUSTOMER_VIEW_PERMISSIONS,
  EMPLOYEE_MANAGE_PERMISSION,
  EMPLOYEE_VIEW_PERMISSIONS,
  USER_MANAGE_PERMISSION,
  USER_VIEW_PERMISSIONS,
} from '@trishul/admin-data-access';
import { permissionGuard } from '@trishul/core-auth';
import { CustomerFormPage } from './customer-form.page';
import { CustomerListPage } from './customer-list.page';
import { EmployeeFormPage } from './employee-form.page';
import { EmployeeListPage } from './employee-list.page';
import { UserFormPage } from './user-form.page';
import { UserListPage } from './user-list.page';

/** Lazy-loaded under /admin. */
export const adminRoutes: Route[] = [
  { path: '', pathMatch: 'full', redirectTo: 'users' },
  {
    path: 'users',
    title: 'Users',
    canActivate: [permissionGuard(...USER_VIEW_PERMISSIONS)],
    component: UserListPage,
  },
  {
    path: 'users/new',
    title: 'Add user',
    canActivate: [permissionGuard(USER_MANAGE_PERMISSION)],
    component: UserFormPage,
  },
  {
    path: 'users/:userId',
    title: 'User',
    canActivate: [permissionGuard(...USER_VIEW_PERMISSIONS)],
    component: UserFormPage,
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
    path: 'customers',
    title: 'Customers',
    canActivate: [permissionGuard(...CUSTOMER_VIEW_PERMISSIONS)],
    component: CustomerListPage,
  },
  {
    path: 'customers/new',
    title: 'Add customer',
    canActivate: [permissionGuard(CUSTOMER_MANAGE_PERMISSION)],
    component: CustomerFormPage,
  },
  {
    path: 'customers/:customerId',
    title: 'Customer',
    canActivate: [permissionGuard(...CUSTOMER_VIEW_PERMISSIONS)],
    component: CustomerFormPage,
  },
];
