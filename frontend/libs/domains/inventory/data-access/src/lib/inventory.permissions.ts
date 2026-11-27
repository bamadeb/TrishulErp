/** Permission codes of the inventory module (backend: modules/inv/common.py). */
export const INV_ITEM_VIEW = 'inv.item.view';
export const INV_ITEM_MANAGE = 'inv.item.manage';
export const INV_LOCATION_MANAGE = 'inv.location.manage';
export const INV_STOCK_VIEW = 'inv.stock.view';
export const INV_GRN_MANAGE = 'inv.grn.manage';
export const INV_TRANSFER_MANAGE = 'inv.transfer.manage';
export const INV_STOCK_ADJUST = 'inv.stock.adjust';
/** Item list import (backend: modules/inv/item_list_import.py). */
export const INV_ITEM_IMPORT = 'inv.item.import';
export const INV_ITEM_IMPORT_VIEW = 'inv.item.import.view';
export const INV_ITEM_IMPORT_OVERWRITE = 'inv.item.import.overwrite';
/** Bulk price import (backend: modules/inv/prices.py). */
export const INV_PRICE_IMPORT = 'inv.price.import';
export const INV_PRICE_IMPORT_VIEW = 'inv.price.import.view';
export const INV_PRICE_APPROVE = 'inv.price.approve';

export const INV_ITEM_VIEW_PERMISSIONS = [
  INV_ITEM_VIEW,
  INV_ITEM_MANAGE,
] as const;
/** Screens that show stock: anyone who looks at it or moves it. */
export const INV_STOCK_USER_PERMISSIONS = [
  INV_STOCK_VIEW,
  INV_GRN_MANAGE,
  INV_TRANSFER_MANAGE,
  INV_STOCK_ADJUST,
] as const;
export const INV_ANY_PERMISSIONS = [
  ...INV_ITEM_VIEW_PERMISSIONS,
  INV_LOCATION_MANAGE,
  ...INV_STOCK_USER_PERMISSIONS,
] as const;
export const INV_GRN_VIEW_PERMISSIONS = [
  INV_GRN_MANAGE,
  INV_STOCK_VIEW,
] as const;
export const INV_TRANSFER_VIEW_PERMISSIONS = [
  INV_TRANSFER_MANAGE,
  INV_STOCK_VIEW,
] as const;
export const INV_ADJUSTMENT_VIEW_PERMISSIONS = [
  INV_STOCK_ADJUST,
  INV_STOCK_VIEW,
] as const;
/** The item import screen: importers, and those who only read the history. */
export const INV_ITEM_IMPORT_PERMISSIONS = [
  INV_ITEM_IMPORT,
  INV_ITEM_IMPORT_VIEW,
] as const;
/** The price import screen: importers, history readers and approvers. */
export const INV_PRICE_IMPORT_PERMISSIONS = [
  INV_PRICE_IMPORT,
  INV_PRICE_IMPORT_VIEW,
  INV_PRICE_APPROVE,
] as const;
