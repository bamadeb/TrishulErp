import { Route } from '@angular/router';
import { permissionGuard } from '@trishul/core-auth';
import { AdjustmentFormPage } from './adjustment-form.page';
import { AgeingPage } from './ageing.page';
import { BinMovesPage } from './bin-moves.page';
import { BinStockPage } from './bin-stock.page';
import { DocumentDetailPage } from './document-detail.page';
import { DocumentListPage } from './document-list.page';
import {
  INV_ADJUSTMENT_VIEW_PERMISSIONS,
  INV_ANY_PERMISSIONS,
  INV_BARCODE_MANAGE,
  INV_BINMOVE_MANAGE,
  INV_COUNT_APPROVE,
  INV_COUNT_MANAGE,
  INV_GRN_VIEW_PERMISSIONS,
  INV_ITEM_IMPORT_PERMISSIONS,
  INV_ITEM_MANAGE,
  INV_PRICE_IMPORT_PERMISSIONS,
  INV_ITEM_VIEW_PERMISSIONS,
  INV_LOCATION_MANAGE,
  INV_STOCK_ADJUST,
  INV_STOCK_USER_PERMISSIONS,
  INV_STOCK_VIEW,
  INV_TRANSFER_MANAGE,
  INV_TRANSFER_VIEW_PERMISSIONS,
} from '@trishul/inventory-data-access';
import { ItemDetailPage } from './item-detail.page';
import { ItemFormPage } from './item-form.page';
import { ItemImportDetailPage } from './item-import-detail.page';
import { ItemListImportPage } from './item-list-import.page';
import { LabelsPage } from './labels.page';
import { ItemListPage } from './item-list.page';
import { LocationsPage } from './locations.page';
import { OpeningStockPage } from './opening-stock.page';
import { PriceImportDetailPage } from './price-import-detail.page';
import { PriceImportPage } from './price-import.page';
import { ScanPage } from './scan.page';
import { SetupPage } from './setup.page';
import { StockCountPage } from './stock-count.page';
import { StockCountsPage } from './stock-counts.page';
import { StockPage } from './stock.page';
import { TransferFormPage } from './transfer-form.page';

/** Lazy-loaded under /inventory. */
export const inventoryRoutes: Route[] = [
  { path: '', pathMatch: 'full', redirectTo: 'items' },
  {
    path: 'items',
    title: 'Items',
    canActivate: [permissionGuard(...INV_ANY_PERMISSIONS)],
    component: ItemListPage,
  },
  {
    path: 'items/new',
    title: 'Add item',
    canActivate: [permissionGuard(INV_ITEM_MANAGE)],
    component: ItemFormPage,
  },
  {
    path: 'items/import',
    title: 'Item price import',
    canActivate: [permissionGuard(...INV_PRICE_IMPORT_PERMISSIONS)],
    component: PriceImportPage,
  },
  {
    path: 'items/import/:importId',
    title: 'Price import',
    canActivate: [permissionGuard(...INV_PRICE_IMPORT_PERMISSIONS)],
    component: PriceImportDetailPage,
  },
  {
    path: 'item-imports',
    title: 'Item list import',
    canActivate: [permissionGuard(...INV_ITEM_IMPORT_PERMISSIONS)],
    component: ItemListImportPage,
  },
  {
    path: 'item-imports/:importId',
    title: 'Item import',
    canActivate: [permissionGuard(...INV_ITEM_IMPORT_PERMISSIONS)],
    component: ItemImportDetailPage,
  },
  {
    path: 'items/:itemId',
    title: 'Item',
    canActivate: [permissionGuard(...INV_ANY_PERMISSIONS)],
    component: ItemDetailPage,
  },
  {
    path: 'items/:itemId/edit',
    title: 'Edit item',
    canActivate: [permissionGuard(INV_ITEM_MANAGE)],
    component: ItemFormPage,
  },
  {
    path: 'setup',
    title: 'Item setup',
    canActivate: [permissionGuard(...INV_ITEM_VIEW_PERMISSIONS)],
    component: SetupPage,
  },
  {
    path: 'bin-stock',
    title: 'Rack-wise stock',
    canActivate: [permissionGuard(...INV_ANY_PERMISSIONS)],
    component: BinStockPage,
  },
  {
    path: 'bin-moves',
    title: 'Put-away & bin moves',
    canActivate: [permissionGuard(INV_BINMOVE_MANAGE)],
    component: BinMovesPage,
  },
  {
    path: 'stock-counts',
    title: 'Physical stock count',
    canActivate: [
      permissionGuard(INV_COUNT_MANAGE, INV_COUNT_APPROVE, INV_STOCK_VIEW),
    ],
    component: StockCountsPage,
  },
  {
    path: 'stock-counts/:countId',
    title: 'Stock count',
    canActivate: [
      permissionGuard(INV_COUNT_MANAGE, INV_COUNT_APPROVE, INV_STOCK_VIEW),
    ],
    component: StockCountPage,
  },
  {
    path: 'scan',
    title: 'Scan & find',
    canActivate: [permissionGuard(...INV_ANY_PERMISSIONS)],
    component: ScanPage,
  },
  {
    path: 'labels',
    title: 'Print labels',
    canActivate: [permissionGuard(INV_BARCODE_MANAGE, INV_LOCATION_MANAGE)],
    component: LabelsPage,
  },
  {
    path: 'locations',
    title: 'Locations & racks',
    canActivate: [permissionGuard(...INV_ANY_PERMISSIONS)],
    component: LocationsPage,
  },
  {
    path: 'stock',
    title: 'Stock by batch',
    canActivate: [permissionGuard(...INV_STOCK_USER_PERMISSIONS)],
    component: StockPage,
  },
  {
    path: 'ageing',
    title: 'Inventory ageing',
    canActivate: [permissionGuard(INV_STOCK_VIEW)],
    component: AgeingPage,
  },
  {
    path: 'opening-stock',
    title: 'Opening stock',
    canActivate: [permissionGuard(...INV_GRN_VIEW_PERMISSIONS)],
    component: OpeningStockPage,
  },
  {
    path: 'transfers',
    title: 'Stock transfers',
    canActivate: [permissionGuard(...INV_TRANSFER_VIEW_PERMISSIONS)],
    component: DocumentListPage,
    data: { kind: 'transfer' },
  },
  {
    path: 'transfers/new',
    title: 'New transfer',
    canActivate: [permissionGuard(INV_TRANSFER_MANAGE)],
    component: TransferFormPage,
  },
  {
    path: 'transfers/:documentId',
    title: 'Transfer',
    canActivate: [permissionGuard(...INV_TRANSFER_VIEW_PERMISSIONS)],
    component: DocumentDetailPage,
    data: { kind: 'transfer' },
  },
  {
    path: 'adjustments',
    title: 'Stock adjustments',
    canActivate: [permissionGuard(...INV_ADJUSTMENT_VIEW_PERMISSIONS)],
    component: DocumentListPage,
    data: { kind: 'adjustment' },
  },
  {
    path: 'adjustments/new',
    title: 'New adjustment',
    canActivate: [permissionGuard(INV_STOCK_ADJUST)],
    component: AdjustmentFormPage,
  },
  {
    path: 'adjustments/:documentId',
    title: 'Adjustment',
    canActivate: [permissionGuard(...INV_ADJUSTMENT_VIEW_PERMISSIONS)],
    component: DocumentDetailPage,
    data: { kind: 'adjustment' },
  },
];
