/** Permission codes of the sales module (backend: modules/sal/common.py). */
export const SAL_CUSTOMER_VIEW = 'sal.customer.view';
export const SAL_CUSTOMER_MANAGE = 'sal.customer.manage';
export const SAL_QUOTATION_VIEW = 'sal.quotation.view';
export const SAL_QUOTATION_MANAGE = 'sal.quotation.manage';
export const SAL_QUOTATION_APPROVE = 'sal.quotation.approve';
export const SAL_ORDER_VIEW = 'sal.order.view';
export const SAL_ORDER_MANAGE = 'sal.order.manage';
export const SAL_ORDER_APPROVE = 'sal.order.approve';
export const SAL_ORDER_CLOSE = 'sal.order.close';
export const SAL_DELIVERY_MANAGE = 'sal.delivery.manage';
export const SAL_DELIVERY_OVER_ORDER = 'sal.delivery.over_order';
export const SAL_ACCOUNT_VIEW = 'sal.account.view';
export const SAL_INVOICE_MANAGE = 'sal.invoice.manage';
export const SAL_INVOICE_DIRECT = 'sal.invoice.direct';
export const SAL_INVOICE_CANCEL = 'sal.invoice.cancel';
export const SAL_RECEIPT_MANAGE = 'sal.receipt.manage';
export const SAL_ALLOCATION_MANAGE = 'sal.allocation.manage';
export const SAL_ALLOCATION_REVERSE = 'sal.allocation.reverse';
export const SAL_CREDIT_OVERRIDE = 'sal.credit.override';
/** Engineers' parts requests: see them all, quote or reject them (backend: modules/service/parts). */
export const SVC_PART_REQUEST_REVIEW = 'svc.part_request.review';

/** Customer money: invoices, receipts, allocations, statements. */
export const SAL_ACCOUNT_PERMISSIONS = [
  SAL_ACCOUNT_VIEW,
  SAL_INVOICE_MANAGE,
  SAL_INVOICE_DIRECT,
  SAL_INVOICE_CANCEL,
  SAL_RECEIPT_MANAGE,
  SAL_ALLOCATION_MANAGE,
] as const;
export const SAL_QUOTATION_PERMISSIONS = [
  SAL_QUOTATION_VIEW,
  SAL_QUOTATION_MANAGE,
  SAL_QUOTATION_APPROVE,
  SAL_ORDER_MANAGE,
] as const;
export const SAL_ORDER_PERMISSIONS = [
  SAL_ORDER_VIEW,
  SAL_ORDER_MANAGE,
  SAL_ORDER_APPROVE,
  SAL_ORDER_CLOSE,
  SAL_DELIVERY_MANAGE,
  ...SAL_ACCOUNT_PERMISSIONS,
] as const;
export const SAL_DELIVERY_PERMISSIONS = [
  SAL_DELIVERY_MANAGE,
  SAL_ORDER_VIEW,
  SAL_ORDER_MANAGE,
  ...SAL_ACCOUNT_PERMISSIONS,
] as const;
export const SAL_INVOICE_CREATE_PERMISSIONS = [
  SAL_INVOICE_MANAGE,
  SAL_INVOICE_DIRECT,
] as const;
/** Anyone working in sales: customer accounts and the shared dropdowns. */
export const SAL_USER_PERMISSIONS = [
  SAL_CUSTOMER_VIEW,
  SAL_CUSTOMER_MANAGE,
  SAL_QUOTATION_VIEW,
  SAL_QUOTATION_MANAGE,
  SAL_QUOTATION_APPROVE,
  SAL_ORDER_VIEW,
  SAL_ORDER_MANAGE,
  SAL_ORDER_APPROVE,
  SAL_ORDER_CLOSE,
  SAL_DELIVERY_MANAGE,
  ...SAL_ACCOUNT_PERMISSIONS,
] as const;
