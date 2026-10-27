import { Route } from '@angular/router';
import {
  USER_MANAGE_PERMISSION,
  USER_VIEW_PERMISSIONS,
} from '@trishul/admin-data-access';
import { permissionGuard } from '@trishul/core-auth';
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
];
