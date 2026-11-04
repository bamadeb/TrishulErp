import {
  ListServiceContracts$Params,
  MachineAsc,
} from '@trishul/core-api';
import { allOf } from '@trishul/shared-util';

// API types come from the generated client; permission codes, filters and labels are added here.
export type {
  AscImportResult,
  AscImportRow,
  AscImportSummary,
  ContractEngineerOption,
  ContractFormOptions,
  ContractPlanCreate,
  ContractPlanItem,
  ContractPlanUpdate,
  MachineAsc,
  ServiceContractCreate,
  ServiceContractDetail,
  ServiceContractListItem,
  ServiceContractRenew,
  ServiceContractUpdate,
} from '@trishul/core-api';

export type AscState = MachineAsc['state'];
export type AscStatusFilter = NonNullable<ListServiceContracts$Params['status']>;

/** Query of the ASC list; page and page size are always set. */
export type AscQuery = ListServiceContracts$Params &
  Required<Pick<ListServiceContracts$Params, 'page' | 'pageSize'>>;

export const ASC_STATUS_FILTERS = allOf<AscStatusFilter>()([
  'live',
  'expiring',
  'expired',
  'cancelled',
  'all',
]);

export const ASC_STATUS_LABELS: Record<AscStatusFilter, string> = {
  live: 'Live',
  expiring: 'Expiring in 30 days',
  expired: 'Expired – renewal due',
  cancelled: 'Cancelled',
  all: 'All',
};

/**
 * Who may open the ASC screens / change contracts and plans / upload the register.
 * The API checks the same codes: backend/src/trishul_api/modules/service/contracts/router.py.
 */
export const ASC_VIEW_PERMISSIONS = [
  'svc.contract.view',
  'svc.contract.manage',
] as const;
export const ASC_MANAGE_PERMISSION = 'svc.contract.manage';
export const ASC_IMPORT_PERMISSION = 'svc.contract.import';
