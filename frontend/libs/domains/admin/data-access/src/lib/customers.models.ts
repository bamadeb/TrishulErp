import {
  CustomerDetail,
  CustomerListItem,
  ListCustomers$Params,
} from '@trishul/core-api';
import { allOf } from '@trishul/shared-util';

export type {
  CompanyOption,
  CustomerCreate,
  CustomerDetail,
  CustomerFormOptions,
  CustomerListItem,
  CustomerUpdate,
  StateOption,
} from '@trishul/core-api';

export type CustomerStatusFilter = NonNullable<ListCustomers$Params['status']>;
export type CustomerType = CustomerDetail['customerType'];
export type GstRegistrationType = CustomerDetail['gstRegistrationType'];
export type PriorityTier = NonNullable<CustomerDetail['priorityTier']>;

/** Query of the customer list; page and page size are always set. */
export type CustomerQuery = ListCustomers$Params &
  Required<Pick<ListCustomers$Params, 'page' | 'pageSize'>>;

export const CUSTOMER_STATUS_FILTERS = allOf<CustomerStatusFilter>()([
  'active',
  'inactive',
  'all',
]);

/** Stops compiling if the API adds a value, so the dropdowns stay in sync. */
export const CUSTOMER_TYPES = allOf<CustomerType>()([
  'Individual',
  'Contractor',
  'Company',
  'Government',
  'Rental',
  'Dealer',
]);

export const GST_REGISTRATION_TYPES = allOf<GstRegistrationType>()([
  'Regular',
  'Composition',
  'Unregistered',
  'SEZ',
]);

export const PRIORITY_TIERS = allOf<PriorityTier>()(['Key', 'Normal', 'Low']);

/** Open the customer screens / change customers. The API checks the same codes. */
export const CUSTOMER_VIEW_PERMISSIONS = [
  'core.customer.view',
  'core.customer.manage',
] as const;
export const CUSTOMER_MANAGE_PERMISSION = 'core.customer.manage';

/** Same row shape whether it came from the list or the detail endpoint. */
export type CustomerRow = CustomerListItem;
