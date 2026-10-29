import {
  EmployeeDetail,
  EmployeeListItem,
  ListEmployees$Params,
} from '@trishul/core-api';
import { allOf } from '@trishul/shared-util';

export type {
  CompanyOption,
  DepartmentOption,
  DesignationOption,
  EmployeeCreate,
  EmployeeDetail,
  EmployeeListItem,
  EmployeeUpdate,
} from '@trishul/core-api';

export type EmployeeStatusFilter = NonNullable<ListEmployees$Params['status']>;
export type EmployeeType = EmployeeDetail['employeeType'];
export type HrStatus = EmployeeDetail['status'];

/** Query of the employee list; page and page size are always set. */
export type EmployeeQuery = ListEmployees$Params &
  Required<Pick<ListEmployees$Params, 'page' | 'pageSize'>>;

export const EMPLOYEE_STATUS_FILTERS = allOf<EmployeeStatusFilter>()([
  'active',
  'inactive',
  'all',
]);

/** Stops compiling if the API adds a type or status, so the dropdowns stay in sync. */
export const EMPLOYEE_TYPES = allOf<EmployeeType>()([
  'Permanent',
  'Contract',
  'Trainee',
  'Consultant',
]);

export const HR_STATUSES = allOf<HrStatus>()(['Active', 'Notice', 'Exited']);

/** Open the employee screens / change employees. The API checks the same codes. */
export const EMPLOYEE_VIEW_PERMISSIONS = [
  'core.employee.view',
  'core.employee.manage',
] as const;
export const EMPLOYEE_MANAGE_PERMISSION = 'core.employee.manage';

/** Same row shape whether it came from the list or the detail endpoint. */
export type EmployeeRow = EmployeeListItem;
