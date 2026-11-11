import { Route } from '@angular/router';
import { permissionGuard } from '@trishul/core-auth';
import {
  PUR_ACCOUNT_PERMISSIONS,
  PUR_CREDIT_NOTE_MANAGE,
  PUR_GRN_MANAGE,
  PUR_GRN_PERMISSIONS,
  PUR_INVOICE_CREATE_PERMISSIONS,
  PUR_PAYMENT_MANAGE,
  PUR_PO_MANAGE,
  PUR_PO_PERMISSIONS,
  PUR_SUPPLIER_PERMISSIONS,
} from '@trishul/purchases-data-access';
import { AllocationsPage } from './allocations.page';
import { CreditNoteFormPage } from './credit-note-form.page';
import { DocumentDetailPage } from './document-detail.page';
import { DocumentsPage } from './documents.page';
import { GrnFormPage } from './grn-form.page';
import { InvoiceFormPage } from './invoice-form.page';
import { OutstandingPage } from './outstanding.page';
import { PaymentFormPage } from './payment-form.page';
import { PoDetailPage } from './po-detail.page';
import { PoFormPage } from './po-form.page';
import { PoListPage } from './po-list.page';
import { PaymentVoucherPage, PoPrintPage } from './print.pages';
import { SupplierDetailPage } from './supplier-detail.page';
import { SuppliersPage } from './suppliers.page';

const PO = permissionGuard(...PUR_PO_PERMISSIONS);
const GRN = permissionGuard(...PUR_GRN_PERMISSIONS);
const ACCOUNTS = permissionGuard(...PUR_ACCOUNT_PERMISSIONS);

/** Lazy-loaded under /purchases. */
export const purchasesRoutes: Route[] = [
  { path: '', pathMatch: 'full', redirectTo: 'orders' },
  {
    path: 'suppliers',
    title: 'Suppliers',
    canActivate: [permissionGuard(...PUR_SUPPLIER_PERMISSIONS)],
    component: SuppliersPage,
  },
  {
    path: 'suppliers/:supplierId',
    title: 'Supplier',
    canActivate: [permissionGuard(...PUR_SUPPLIER_PERMISSIONS)],
    component: SupplierDetailPage,
  },
  {
    path: 'orders',
    title: 'Purchase orders',
    canActivate: [PO],
    component: PoListPage,
  },
  {
    path: 'orders/new',
    title: 'New purchase order',
    canActivate: [permissionGuard(PUR_PO_MANAGE)],
    component: PoFormPage,
  },
  {
    path: 'orders/:poId',
    title: 'Purchase order',
    canActivate: [PO],
    component: PoDetailPage,
  },
  {
    path: 'orders/:poId/edit',
    title: 'Edit purchase order',
    canActivate: [permissionGuard(PUR_PO_MANAGE)],
    component: PoFormPage,
  },
  {
    path: 'outstanding',
    title: 'Outstanding orders',
    canActivate: [PO],
    component: OutstandingPage,
  },
  {
    path: 'grns',
    title: 'Goods receipts',
    canActivate: [GRN],
    component: DocumentsPage,
    data: { kind: 'grn' },
  },
  {
    path: 'grns/new',
    title: 'Receive goods',
    canActivate: [permissionGuard(PUR_GRN_MANAGE)],
    component: GrnFormPage,
  },
  {
    path: 'grns/:documentId',
    title: 'GRN',
    canActivate: [GRN],
    component: DocumentDetailPage,
    data: { kind: 'grn' },
  },
  {
    path: 'invoices',
    title: 'Supplier invoices',
    canActivate: [ACCOUNTS],
    component: DocumentsPage,
    data: { kind: 'invoice' },
  },
  {
    path: 'invoices/new',
    title: 'Record supplier invoice',
    canActivate: [permissionGuard(...PUR_INVOICE_CREATE_PERMISSIONS)],
    component: InvoiceFormPage,
  },
  {
    path: 'invoices/:documentId',
    title: 'Supplier invoice',
    canActivate: [ACCOUNTS],
    component: DocumentDetailPage,
    data: { kind: 'invoice' },
  },
  {
    path: 'payments',
    title: 'Supplier payments',
    canActivate: [ACCOUNTS],
    component: DocumentsPage,
    data: { kind: 'payment' },
  },
  {
    path: 'payments/new',
    title: 'Record payment',
    canActivate: [permissionGuard(PUR_PAYMENT_MANAGE)],
    component: PaymentFormPage,
  },
  {
    path: 'payments/:documentId',
    title: 'Supplier payment',
    canActivate: [ACCOUNTS],
    component: DocumentDetailPage,
    data: { kind: 'payment' },
  },
  {
    path: 'credit-notes',
    title: 'Supplier credit notes',
    canActivate: [ACCOUNTS],
    component: DocumentsPage,
    data: { kind: 'credit' },
  },
  {
    path: 'credit-notes/new',
    title: 'Record credit note',
    canActivate: [permissionGuard(PUR_CREDIT_NOTE_MANAGE)],
    component: CreditNoteFormPage,
  },
  {
    path: 'credit-notes/:documentId',
    title: 'Supplier credit note',
    canActivate: [ACCOUNTS],
    component: DocumentDetailPage,
    data: { kind: 'credit' },
  },
  {
    path: 'allocations',
    title: 'Supplier allocations',
    canActivate: [ACCOUNTS],
    component: AllocationsPage,
  },
];

/** Print views, outside the app shell (no menus on paper). Lazy-loaded under /print. */
export const purchasesPrintRoutes: Route[] = [
  {
    path: 'purchase-orders/:poId',
    title: 'Purchase order',
    canActivate: [PO],
    component: PoPrintPage,
  },
  {
    path: 'supplier-payments/:paymentId',
    title: 'Payment voucher',
    canActivate: [ACCOUNTS],
    component: PaymentVoucherPage,
  },
];
