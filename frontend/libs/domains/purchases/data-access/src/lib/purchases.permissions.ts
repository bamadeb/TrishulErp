/** Permission codes of the purchases module (backend: modules/pur/common.py). */
export const PUR_SUPPLIER_VIEW = 'pur.supplier.view';
export const PUR_SUPPLIER_MANAGE = 'pur.supplier.manage';
export const PUR_PO_VIEW = 'pur.po.view';
export const PUR_PO_MANAGE = 'pur.po.manage';
export const PUR_PO_APPROVE = 'pur.po.approve';
export const PUR_PO_CLOSE = 'pur.po.close';
export const PUR_GRN_MANAGE = 'pur.grn.manage';
export const PUR_ACCOUNT_VIEW = 'pur.account.view';
export const PUR_INVOICE_MANAGE = 'pur.invoice.manage';
export const PUR_INVOICE_DIRECT = 'pur.invoice.direct';
export const PUR_PAYMENT_MANAGE = 'pur.payment.manage';
export const PUR_CREDIT_NOTE_MANAGE = 'pur.credit_note.manage';
export const PUR_ALLOCATION_MANAGE = 'pur.allocation.manage';
export const PUR_ALLOCATION_REVERSE = 'pur.allocation.reverse';

/** Supplier money: invoices, payments, credit notes, allocations, statements. */
export const PUR_ACCOUNT_PERMISSIONS = [
  PUR_ACCOUNT_VIEW,
  PUR_INVOICE_MANAGE,
  PUR_INVOICE_DIRECT,
  PUR_PAYMENT_MANAGE,
  PUR_CREDIT_NOTE_MANAGE,
  PUR_ALLOCATION_MANAGE,
] as const;
export const PUR_SUPPLIER_PERMISSIONS = [
  PUR_SUPPLIER_VIEW,
  PUR_SUPPLIER_MANAGE,
  ...PUR_ACCOUNT_PERMISSIONS,
] as const;
export const PUR_PO_PERMISSIONS = [
  PUR_PO_VIEW,
  PUR_PO_MANAGE,
  PUR_PO_APPROVE,
  PUR_PO_CLOSE,
  PUR_GRN_MANAGE,
  ...PUR_ACCOUNT_PERMISSIONS,
] as const;
export const PUR_GRN_PERMISSIONS = [
  PUR_GRN_MANAGE,
  PUR_PO_VIEW,
  PUR_PO_MANAGE,
  'inv.stock.view',
  ...PUR_ACCOUNT_PERMISSIONS,
] as const;
export const PUR_INVOICE_CREATE_PERMISSIONS = [
  PUR_INVOICE_MANAGE,
  PUR_INVOICE_DIRECT,
] as const;
