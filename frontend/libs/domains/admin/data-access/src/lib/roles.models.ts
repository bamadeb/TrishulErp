import {
  ListRoles$Params,
  PermissionItem,
  RoleListItem,
} from '@trishul/core-api';
import { allOf } from '@trishul/shared-util';

export type {
  PermissionItem,
  RoleCreate,
  RoleDetail,
  RoleListItem,
  RoleUpdate,
} from '@trishul/core-api';

export type RoleStatusFilter = NonNullable<ListRoles$Params['status']>;
export type RoleQuery = ListRoles$Params;

export const ROLE_STATUS_FILTERS = allOf<RoleStatusFilter>()([
  'active',
  'inactive',
  'all',
]);

/** Open the role screens / change roles. The API checks the same codes (modules/core/roles/router.py). */
export const ROLE_VIEW_PERMISSIONS = [
  'core.role.view',
  'core.role.manage',
] as const;
export const ROLE_MANAGE_PERMISSION = 'core.role.manage';

/** The role code the API never lets lose ROLE_MANAGE_PERMISSION (modules/core/roles/service.py). */
export const ADMIN_ROLE_CODE = 'ADMIN';

/** Same pattern as the API: upper-case letters, digits and _, starting with a letter. */
export const ROLE_CODE_PATTERN = /^[A-Z][A-Z0-9_]{1,39}$/;

export type RoleRow = RoleListItem;

export interface PermissionGroup {
  module: string;
  permissions: PermissionItem[];
}

/** Permissions grouped by module, in the API's order (module, then code). */
export function groupPermissions(
  permissions: readonly PermissionItem[],
): PermissionGroup[] {
  const groups = new Map<string, PermissionItem[]>();
  for (const permission of permissions) {
    const group = groups.get(permission.module) ?? [];
    group.push(permission);
    groups.set(permission.module, group);
  }
  return [...groups].map(([module, items]) => ({
    module,
    permissions: items,
  }));
}
