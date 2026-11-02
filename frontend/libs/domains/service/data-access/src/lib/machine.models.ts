import {
  ListMachines$Params,
  MachineDetail,
  MachineListItem,
} from '@trishul/core-api';
import { allOf } from '@trishul/shared-util';

export type {
  MachineCreate,
  MachineDetail,
  MachineFormOptions,
  MachineListItem,
  MachineModelOption,
  MachineUpdate,
} from '@trishul/core-api';

export type MachineStatusFilter = NonNullable<ListMachines$Params['status']>;
export type MachineStatus = MachineDetail['status'];

/** Query of the machine list; page and page size are always set. */
export type MachineQuery = ListMachines$Params &
  Required<Pick<ListMachines$Params, 'page' | 'pageSize'>>;

export const MACHINE_STATUS_FILTERS = allOf<MachineStatusFilter>()([
  'active',
  'inactive',
  'all',
]);

/** Stops compiling if the API adds a value, so the dropdown stays in sync. */
export const MACHINE_STATUSES = allOf<MachineStatus>()([
  'Sold',
  'In stock',
  'Transferred',
  'Scrapped',
]);

/** Open the machine screens / change machines. The API checks the same codes. */
export const MACHINE_VIEW_PERMISSIONS = [
  'core.machine.view',
  'core.machine.manage',
] as const;
export const MACHINE_MANAGE_PERMISSION = 'core.machine.manage';

/** Same row shape whether it came from the list or the detail endpoint. */
export type MachineRow = MachineListItem;
