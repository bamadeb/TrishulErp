import { Route } from '@angular/router';
import { permissionGuard } from '@trishul/core-auth';
import {
  SAL_ACCOUNT_PERMISSIONS,
  SAL_ALLOCATION_MANAGE,
  SAL_ALLOCATION_REVERSE,
  SAL_DELIVERY_MANAGE,
  SAL_DELIVERY_PERMISSIONS,
  SAL_INVOICE_CREATE_PERMISSIONS,
  SAL_ORDER_MANAGE,
  SAL_ORDER_PERMISSIONS,
  SAL_QUOTATION_MANAGE,
  SAL_QUOTATION_PERMISSIONS,
  SAL_RECEIPT_MANAGE,
  SAL_USER_PERMISSIONS,
  SVC_PART_REQUEST_REVIEW,
} from '@trishul/sales-data-access';
import { SalesAllocationsPage } from './allocations.page';
import { CustomerAccountPage } from './customer-detail.page';
import { CustomerAccountsPage } from './customers.page';
import { DeliveryFormPage } from './delivery-form.page';
import { SalesDocumentDetailPage } from './document-detail.page';
import { SalesDocumentsPage } from './documents.page';
import { SalesInvoiceFormPage } from './invoice-form.page';
import { OrderDetailPage } from './order-detail.page';
import { OrderFormPage } from './order-form.page';
import { OrderListPage } from './order-list.page';
import { SalesOutstandingPage } from './outstanding.page';
import { PartRequestsPage } from './part-requests.page';
import {
  DeliveryPrintPage,
  OrderPrintPage,
  ReceiptPrintPage,
  SalesInvoicePrintPage,
} from './print.pages';
import { QuotationPrintPage } from './quotation-print.page';
import { QuotationDetailPage } from './quotation-detail.page';
import { QuotationFormPage } from './quotation-form.page';
import { QuotationListPage } from './quotation-list.page';
import { ReceiptFormPage } from './receipt-form.page';

const QUOTES = permissionGuard(...SAL_QUOTATION_PERMISSIONS);
const ORDERS = permissionGuard(...SAL_ORDER_PERMISSIONS);
const DELIVERIES = permissionGuard(...SAL_DELIVERY_PERMISSIONS);
const ACCOUNTS = permissionGuard(...SAL_ACCOUNT_PERMISSIONS);

/** Lazy-loaded under /sales. */
export const salesRoutes: Route[] = [
  { path: '', pathMatch: 'full', redirectTo: 'orders' },
  {
    path: 'customers',
    title: 'Customer accounts',
    canActivate: [permissionGuard(...SAL_USER_PERMISSIONS)],
    component: CustomerAccountsPage,
  },
  {
    path: 'customers/:customerId',
    title: 'Customer account',
    canActivate: [permissionGuard(...SAL_USER_PERMISSIONS)],
    component: CustomerAccountPage,
  },
  {
    path: 'quotations',
    title: 'Quotations',
    canActivate: [QUOTES],
    component: QuotationListPage,
  },
  {
    path: 'part-requests',
    title: 'Parts requests',
    canActivate: [permissionGuard(SVC_PART_REQUEST_REVIEW)],
    component: PartRequestsPage,
  },
  {
    path: 'quotations/new',
    title: 'New quotation',
    canActivate: [permissionGuard(SAL_QUOTATION_MANAGE)],
    component: QuotationFormPage,
  },
  {
    path: 'quotations/:quotationId',
    title: 'Quotation',
    canActivate: [QUOTES],
    component: QuotationDetailPage,
  },
  {
    path: 'quotations/:quotationId/edit',
    title: 'Edit quotation',
    canActivate: [permissionGuard(SAL_QUOTATION_MANAGE)],
    component: QuotationFormPage,
  },
  {
    path: 'orders',
    title: 'Sales orders',
    canActivate: [ORDERS],
    component: OrderListPage,
  },
  {
    path: 'orders/new',
    title: 'New sales order',
    canActivate: [permissionGuard(SAL_ORDER_MANAGE)],
    component: OrderFormPage,
  },
  {
    path: 'orders/:orderId',
    title: 'Sales order',
    canActivate: [ORDERS],
    component: OrderDetailPage,
  },
  {
    path: 'orders/:orderId/edit',
    title: 'Edit sales order',
    canActivate: [permissionGuard(SAL_ORDER_MANAGE)],
    component: OrderFormPage,
  },
  {
    path: 'outstanding',
    title: 'Orders to deliver',
    canActivate: [ORDERS],
    component: SalesOutstandingPage,
  },
  {
    path: 'deliveries',
    title: 'Deliveries',
    canActivate: [DELIVERIES],
    component: SalesDocumentsPage,
    data: { kind: 'delivery' },
  },
  {
    path: 'deliveries/new',
    title: 'Deliver goods',
    canActivate: [permissionGuard(SAL_DELIVERY_MANAGE)],
    component: DeliveryFormPage,
  },
  {
    path: 'deliveries/:documentId',
    title: 'Delivery',
    canActivate: [DELIVERIES],
    component: SalesDocumentDetailPage,
    data: { kind: 'delivery' },
  },
  {
    path: 'invoices',
    title: 'Sales invoices',
    canActivate: [ACCOUNTS],
    component: SalesDocumentsPage,
    data: { kind: 'invoice' },
  },
  {
    path: 'invoices/new',
    title: 'New sales invoice',
    canActivate: [permissionGuard(...SAL_INVOICE_CREATE_PERMISSIONS)],
    component: SalesInvoiceFormPage,
  },
  {
    path: 'invoices/:documentId',
    title: 'Sales invoice',
    canActivate: [ACCOUNTS],
    component: SalesDocumentDetailPage,
    data: { kind: 'invoice' },
  },
  {
    path: 'receipts',
    title: 'Customer receipts',
    canActivate: [ACCOUNTS],
    component: SalesDocumentsPage,
    data: { kind: 'receipt' },
  },
  {
    path: 'receipts/new',
    title: 'Record receipt',
    canActivate: [permissionGuard(SAL_RECEIPT_MANAGE)],
    component: ReceiptFormPage,
  },
  {
    path: 'receipts/:documentId',
    title: 'Customer receipt',
    canActivate: [ACCOUNTS],
    component: SalesDocumentDetailPage,
    data: { kind: 'receipt' },
  },
  {
    path: 'allocations',
    title: 'Customer allocations',
    canActivate: [
      permissionGuard(
        ...SAL_ACCOUNT_PERMISSIONS,
        SAL_ALLOCATION_REVERSE,
        SAL_ALLOCATION_MANAGE,
      ),
    ],
    component: SalesAllocationsPage,
  },
];

/** Print views, outside the app shell. Lazy-loaded under /print/sales. */
export const salesPrintRoutes: Route[] = [
  {
    path: 'quotations/:quotationId',
    title: 'Quotation',
    canActivate: [QUOTES],
    component: QuotationPrintPage,
  },
  {
    path: 'orders/:orderId',
    title: 'Sales order',
    canActivate: [ORDERS],
    component: OrderPrintPage,
  },
  {
    path: 'deliveries/:deliveryId',
    title: 'Delivery challan',
    canActivate: [DELIVERIES],
    component: DeliveryPrintPage,
  },
  {
    path: 'invoices/:invoiceId',
    title: 'Tax invoice',
    canActivate: [ACCOUNTS],
    component: SalesInvoicePrintPage,
  },
  {
    path: 'receipts/:receiptId',
    title: 'Receipt',
    canActivate: [ACCOUNTS],
    component: ReceiptPrintPage,
  },
];
