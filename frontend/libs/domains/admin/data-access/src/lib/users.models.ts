import { ListUsers$Params, UserDetail, UserListItem } from '@trishul/core-api';
import { allOf } from '@trishul/shared-util';

export type {
  EmployeeOption,
  PasswordResetResult,
  RoleGrant,
  RoleOption,
  UserCreate,
  UserCreated,
  UserDetail,
  UserListItem,
  UserUpdate,
} from '@trishul/core-api';

export type SignInStatus = UserDetail['signInStatus'];
export type UserStatusFilter = NonNullable<ListUsers$Params['status']>;
export type PasswordDelivery = 'email' | 'show';

/** Query of the user list; page and page size are always set. */
export type UserQuery = ListUsers$Params &
  Required<Pick<ListUsers$Params, 'page' | 'pageSize'>>;

export const USER_STATUS_FILTERS = allOf<UserStatusFilter>()([
  'active',
  'inactive',
  'all',
]);

/** Plain-language sign-in status for screens. Stops compiling if the API adds a status. */
export const SIGN_IN_STATUS_LABELS: Record<SignInStatus, string> = {
  active: 'Signed in before',
  'password-change-required': 'Must set a password at next sign-in',
  'reset-required': 'Must reset the password (code sent by email)',
  disabled: 'Sign-in disabled',
  missing: 'No sign-in account',
  development: 'Development user (no password)',
  unknown: 'Unknown',
};

/** Open the user screens / change users. The API checks the same codes (modules/core/users/router.py). */
export const USER_VIEW_PERMISSIONS = [
  'core.user.view',
  'core.user.manage',
] as const;
export const USER_MANAGE_PERMISSION = 'core.user.manage';

export function roleLabel(grant: {
  roleName: string;
  branchName?: string | null;
}): string {
  return grant.branchName
    ? `${grant.roleName} · ${grant.branchName}`
    : grant.roleName;
}

/** "E010 · Rahul Patil · Team Lead": how screens name an employee. */
export function employeeLabel(employee: {
  employeeCode: string;
  firstName: string;
  lastName?: string | null;
  designation?: string | null;
}): string {
  const name = [employee.firstName, employee.lastName]
    .filter(Boolean)
    .join(' ');
  return [employee.employeeCode, name, employee.designation]
    .filter(Boolean)
    .join(' · ');
}

/** Same row shape for the list whether it came from the list or the detail endpoint. */
export type UserRow = UserListItem;
