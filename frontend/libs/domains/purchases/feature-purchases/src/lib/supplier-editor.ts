import { Injectable, inject } from '@angular/core';
import { MatDialog } from '@angular/material/dialog';
import {
  ApiClient,
  SupplierCreate,
  SupplierDetail,
  SupplierUpdate,
  createSupplier,
  getSupplierFormOptions,
  updateSupplier,
  withRowVersion,
} from '@trishul/core-api';
import {
  FieldDef,
  InventoryLookups,
  num,
  openFieldsDialog,
} from '@trishul/inventory-data-access';
import { Observable, catchError, of, switchMap, tap } from 'rxjs';

const TYPES = [
  'OEM',
  'Parts',
  'Lubricants',
  'Services',
  'Transporter',
  'Other',
];
const GST_TYPES = ['Regular', 'Composition', 'Unregistered', 'SEZ', 'Overseas'];

/** Opens the add / edit supplier form; resolves with the saved supplier (undefined when cancelled). */
@Injectable()
export class SupplierEditor {
  private readonly api = inject(ApiClient);
  private readonly dialog = inject(MatDialog);
  private readonly lookups = inject(InventoryLookups);

  edit(
    supplier: SupplierDetail | null,
  ): Observable<SupplierDetail | undefined> {
    return this.api.call(getSupplierFormOptions).pipe(
      catchError(() => of({ states: [], paymentTerms: [] })),
      switchMap((options) => {
        const fields: FieldDef[] = [
          ...(supplier
            ? []
            : [
                {
                  key: 'code',
                  label: 'Code',
                  required: true,
                  maxLength: 20,
                  pattern: '^[A-Za-z0-9][A-Za-z0-9_./-]*$',
                },
              ]),
          {
            key: 'name',
            label: 'Name',
            required: true,
            maxLength: 200,
            wide: !supplier,
          },
          {
            key: 'supplierType',
            label: 'Type',
            type: 'select',
            required: true,
            options: TYPES.map((t) => ({ value: t, label: t })),
          },
          { key: 'contactPerson', label: 'Contact person', maxLength: 100 },
          { key: 'phone', label: 'Phone', maxLength: 15 },
          { key: 'email', label: 'Email', maxLength: 120 },
          { key: 'address', label: 'Billing address', type: 'textarea' },
          {
            key: 'stateId',
            label: 'State',
            type: 'select',
            options: [
              { value: null, label: '—' },
              ...options.states.map((s) => ({ value: s.id, label: s.name })),
            ],
            hint: 'Another state than the branch: IGST',
          },
          {
            key: 'gstin',
            label: 'GSTIN',
            pattern: '^\\d{2}[A-Z]{5}\\d{4}[A-Z][A-Z\\d]Z[A-Z\\d]$',
            hint: '15 characters, capitals',
          },
          {
            key: 'gstRegistrationType',
            label: 'GST registration',
            type: 'select',
            options: [
              { value: null, label: '—' },
              ...GST_TYPES.map((t) => ({ value: t, label: t })),
            ],
          },
          { key: 'pan', label: 'PAN', pattern: '^[A-Z]{5}\\d{4}[A-Z]$' },
          {
            key: 'paymentTermsId',
            label: 'Payment terms',
            type: 'select',
            options: [
              { value: null, label: '—' },
              ...options.paymentTerms.map((t) => ({
                value: t.id,
                label: t.name,
              })),
            ],
            hint: 'Sets invoice due dates',
          },
          {
            key: 'creditLimit',
            label: 'Credit limit (₹)',
            type: 'number',
            min: 0,
          },
          { key: 'bankName', label: 'Bank', maxLength: 100 },
          {
            key: 'bankAccountNo',
            label: 'Account no',
            pattern: '^\\d{6,30}$',
            hint: supplier ? 'Leave blank to keep the saved one' : undefined,
          },
          { key: 'ifsc', label: 'IFSC', pattern: '^[A-Z]{4}0[A-Z0-9]{6}$' },
          {
            key: 'openingBalance',
            label: 'Opening balance (₹)',
            type: 'number',
            hint: 'Owed at go-live; negative for an advance',
          },
          { key: 'openingBalanceDate', label: 'As of', type: 'date' },
          ...(supplier
            ? [{ key: 'isActive', label: 'Active', type: 'checkbox' as const }]
            : []),
        ];
        return openFieldsDialog(this.dialog, {
          title: supplier ? `Change ${supplier.code}` : 'Add supplier',
          submitText: supplier ? 'Save' : 'Add',
          fields,
          value: supplier
            ? {
                ...supplier,
                bankAccountNo: null,
                creditLimit: num(supplier.creditLimit),
                openingBalance: num(supplier.openingBalance),
              }
            : { supplierType: 'Parts', openingBalance: 0 },
          save: (v) => {
            if (supplier) {
              const body = { ...v } as SupplierUpdate & Record<string, unknown>;
              if (!body['bankAccountNo']) delete body['bankAccountNo'];
              return this.api.call(
                updateSupplier,
                { supplierId: supplier.id, body },
                withRowVersion(supplier.rowVersion),
              );
            }
            return this.api.call(createSupplier, {
              body: v as unknown as SupplierCreate,
            });
          },
        });
      }),
      tap((saved) => {
        if (saved) this.lookups.reset();
      }),
    );
  }
}
