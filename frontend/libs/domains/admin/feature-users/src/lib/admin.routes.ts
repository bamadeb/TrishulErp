import { Route } from '@angular/router';
import {
  ALERT_RULE_MANAGE_PERMISSION,
  ALERT_RULE_VIEW_PERMISSIONS,
  CUSTOMER_MANAGE_PERMISSION,
  CUSTOMER_VIEW_PERMISSIONS,
  DOCUMENT_VIEW_PERMISSIONS,
  ROLE_MANAGE_PERMISSION,
  ROLE_VIEW_PERMISSIONS,
  TEAM_MANAGE_PERMISSION,
  TEAM_VIEW_PERMISSIONS,
  USER_MANAGE_PERMISSION,
  USER_VIEW_PERMISSIONS,
} from '@trishul/admin-data-access';
import { permissionGuard } from '@trishul/core-auth';
import { AlertRuleFormPage } from './alert-rule-form.page';
import { AlertRuleListPage } from './alert-rule-list.page';
import { CustomerFormPage } from './customer-form.page';
import { CustomerListPage } from './customer-list.page';
import { DocumentListPage } from './document-list.page';
import { RoleFormPage } from './role-form.page';
import { RoleListPage } from './role-list.page';
import { TeamFormPage } from './team-form.page';
import { TeamListPage } from './team-list.page';
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
  {
    path: 'roles',
    title: 'Roles',
    canActivate: [permissionGuard(...ROLE_VIEW_PERMISSIONS)],
    component: RoleListPage,
  },
  {
    path: 'roles/new',
    title: 'Add role',
    canActivate: [permissionGuard(ROLE_MANAGE_PERMISSION)],
    component: RoleFormPage,
  },
  {
    path: 'roles/:roleId',
    title: 'Role',
    canActivate: [permissionGuard(...ROLE_VIEW_PERMISSIONS)],
    component: RoleFormPage,
  },
  {
    path: 'teams',
    title: 'Teams',
    canActivate: [permissionGuard(...TEAM_VIEW_PERMISSIONS)],
    component: TeamListPage,
  },
  {
    path: 'teams/new',
    title: 'Add team',
    canActivate: [permissionGuard(TEAM_MANAGE_PERMISSION)],
    component: TeamFormPage,
  },
  {
    path: 'teams/:teamId',
    title: 'Team',
    canActivate: [permissionGuard(...TEAM_VIEW_PERMISSIONS)],
    component: TeamFormPage,
  },
  {
    path: 'documents',
    title: 'Documents',
    canActivate: [permissionGuard(...DOCUMENT_VIEW_PERMISSIONS)],
    component: DocumentListPage,
  },
  {
    path: 'alert-rules',
    title: 'Alert rules',
    canActivate: [permissionGuard(...ALERT_RULE_VIEW_PERMISSIONS)],
    component: AlertRuleListPage,
  },
  {
    path: 'alert-rules/new',
    title: 'Add alert rule',
    canActivate: [permissionGuard(ALERT_RULE_MANAGE_PERMISSION)],
    component: AlertRuleFormPage,
  },
  {
    path: 'alert-rules/:alertRuleId',
    title: 'Alert rule',
    canActivate: [permissionGuard(...ALERT_RULE_VIEW_PERMISSIONS)],
    component: AlertRuleFormPage,
  },
];
