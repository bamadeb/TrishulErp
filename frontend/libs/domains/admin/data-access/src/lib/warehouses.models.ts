export type {
  WarehouseBranch,
  WarehouseMap,
  WarehouseOut,
} from '@trishul/core-api';

/** Open the Warehouses screen / change warehouses and branch mapping. The API checks the same codes. */
export const WAREHOUSE_VIEW_PERMISSIONS = [
  'core.warehouse.view',
  'core.warehouse.manage',
] as const;
export const WAREHOUSE_MANAGE_PERMISSION = 'core.warehouse.manage';
