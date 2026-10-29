import { HttpErrorResponse, HttpRequest } from '@angular/common/http';
import {
  CompanyOption,
  CustomerCreate,
  CustomerDetail,
  CustomerFormOptions,
  CustomerUpdate,
  PageCustomerListItem,
  StateOption,
} from '@trishul/core-api';
import { MockRoute } from '@trishul/core-http';

/** In-memory /core/customers and its option lists for mock mode and the end-to-end tests. */

const companies: CompanyOption[] = [
  { id: 1, name: 'Trishul' },
  { id: 2, name: 'Kashi Sales' },
];
const states: StateOption[] = [
  { id: 1, name: 'Odisha', gstStateCode: '21' },
  { id: 2, name: 'Maharashtra', gstStateCode: '27' },
  { id: 3, name: 'Karnataka', gstStateCode: '29' },
];

let nextId = 100;
let version = 1;
const rowVersion = () => btoa(`cust-rv-${version++}`);

type Seed = {
  id: number;
  code: string;
  name: string;
  customerType: CustomerDetail['customerType'];
  companyId: number;
  primaryPhone: string;
  alternatePhone: string | null;
  email: string | null;
  pan: string | null;
  gstin: string | null;
  gstRegistrationType: CustomerDetail['gstRegistrationType'];
  billingAddress: string | null;
  billingStateId: number | null;
  priorityTier: CustomerDetail['priorityTier'];
  isAscCustomer: boolean;
  isActive: boolean;
};

function detail(s: Seed): CustomerDetail {
  return {
    ...s,
    billingStateName:
      states.find((st) => st.id === s.billingStateId)?.name ?? null,
    companyName: companies.find((c) => c.id === s.companyId)?.name ?? null,
    createdAt: new Date().toISOString(),
    rowVersion: rowVersion(),
  };
}

const seeds: Seed[] = [
  {
    id: 10,
    code: 'C0010',
    name: 'Blue Earth Movers',
    customerType: 'Contractor',
    companyId: 1,
    primaryPhone: '9822000010',
    alternatePhone: null,
    email: 'ops@blueearth.co.in',
    pan: 'AAACB1234C',
    gstin: '21AAACB1234C1Z5',
    gstRegistrationType: 'Regular',
    billingAddress: 'Plot 14, Industrial Estate, Bhadrak',
    billingStateId: 1,
    priorityTier: 'Key',
    isAscCustomer: true,
    isActive: true,
  },
  {
    id: 11,
    code: 'C0011',
    name: 'Deccan Fabricators Pvt Ltd',
    customerType: 'Company',
    companyId: 1,
    primaryPhone: '9822000011',
    alternatePhone: null,
    email: null,
    pan: null,
    gstin: '27AABCD5678E1Z2',
    gstRegistrationType: 'Regular',
    billingAddress: 'MIDC, Pune',
    billingStateId: 2,
    priorityTier: 'Normal',
    isAscCustomer: false,
    isActive: true,
  },
  {
    id: 12,
    code: 'C0012',
    name: 'Ravi Kumar',
    customerType: 'Individual',
    companyId: 2,
    primaryPhone: '9822000012',
    alternatePhone: null,
    email: null,
    pan: null,
    gstin: null,
    gstRegistrationType: 'Unregistered',
    billingAddress: null,
    billingStateId: 3,
    priorityTier: 'Low',
    isAscCustomer: false,
    isActive: true,
  },
];

function find(params: Record<string, string>, req: HttpRequest<unknown>): Seed {
  const seed = seeds.find((s) => s.id === Number(params['customerId']));
  if (!seed) {
    throw new HttpErrorResponse({
      status: 404,
      url: req.url,
      error: { status: 404, title: 'Not found', detail: 'Customer not found.' },
    });
  }
  return seed;
}

function duplicate(
  req: HttpRequest<unknown>,
  code: string | undefined,
  selfId: number | null,
): void {
  if (code && seeds.some((s) => s.code === code && s.id !== selfId)) {
    throw new HttpErrorResponse({
      status: 409,
      url: req.url,
      error: {
        status: 409,
        title: 'Already exists',
        detail: `Customer code '${code}' is already in use.`,
      },
    });
  }
}

export const mockCustomerRoutes: MockRoute[] = [
  {
    method: 'GET',
    path: '/core/customers',
    handle: (req): PageCustomerListItem => {
      const page = Number(req.params.get('page') ?? 1);
      const pageSize = Number(req.params.get('pageSize') ?? 20);
      const search = (req.params.get('search') ?? '').toLowerCase();
      const status = req.params.get('status') ?? 'active';
      const customerType = req.params.get('customerType');
      const priorityTier = req.params.get('priorityTier');
      const rows = seeds
        .filter(
          (s) =>
            (status === 'all' || s.isActive === (status === 'active')) &&
            (!customerType || s.customerType === customerType) &&
            (!priorityTier || s.priorityTier === priorityTier) &&
            (!search ||
              [s.code, s.name, s.primaryPhone, s.gstin, s.email].some((v) =>
                v?.toLowerCase().includes(search),
              )),
        )
        .map(detail);
      return {
        items: rows.slice((page - 1) * pageSize, page * pageSize),
        total: rows.length,
        page,
        pageSize,
      };
    },
  },
  {
    method: 'GET',
    path: '/core/customers/form-options',
    handle: (): CustomerFormOptions => ({ companies, states }),
  },
  {
    method: 'GET',
    path: '/core/customers/:customerId',
    handle: (req, params) => detail(find(params, req)),
  },
  {
    method: 'POST',
    path: '/core/customers',
    handle: (req): CustomerDetail => {
      const body = req.body as CustomerCreate;
      duplicate(req, body.code, null);
      const seed: Seed = {
        id: nextId++,
        code: body.code,
        name: body.name,
        customerType: body.customerType,
        companyId: body.companyId,
        primaryPhone: body.primaryPhone,
        alternatePhone: body.alternatePhone ?? null,
        email: body.email ?? null,
        pan: body.pan ?? null,
        gstin: body.gstin ?? null,
        gstRegistrationType: body.gstRegistrationType ?? 'Unregistered',
        billingAddress: body.billingAddress ?? null,
        billingStateId: body.billingStateId ?? null,
        priorityTier: body.priorityTier ?? 'Normal',
        isAscCustomer: body.isAscCustomer ?? false,
        isActive: true,
      };
      seeds.push(seed);
      return detail(seed);
    },
  },
  {
    method: 'PATCH',
    path: '/core/customers/:customerId',
    handle: (req, params) => {
      const seed = find(params, req);
      const body = req.body as CustomerUpdate;
      duplicate(req, body.code ?? undefined, seed.id);
      Object.assign(seed, {
        code: body.code ?? seed.code,
        name: body.name ?? seed.name,
        customerType: body.customerType ?? seed.customerType,
        companyId: body.companyId ?? seed.companyId,
        primaryPhone: body.primaryPhone ?? seed.primaryPhone,
        alternatePhone:
          'alternatePhone' in body
            ? (body.alternatePhone ?? null)
            : seed.alternatePhone,
        email: 'email' in body ? (body.email ?? null) : seed.email,
        pan: 'pan' in body ? (body.pan ?? null) : seed.pan,
        gstin: 'gstin' in body ? (body.gstin ?? null) : seed.gstin,
        gstRegistrationType:
          body.gstRegistrationType ?? seed.gstRegistrationType,
        billingAddress:
          'billingAddress' in body
            ? (body.billingAddress ?? null)
            : seed.billingAddress,
        billingStateId:
          'billingStateId' in body
            ? (body.billingStateId ?? null)
            : seed.billingStateId,
        priorityTier: body.priorityTier ?? seed.priorityTier,
        isAscCustomer: body.isAscCustomer ?? seed.isAscCustomer,
      });
      return detail(seed);
    },
  },
  {
    method: 'POST',
    path: '/core/customers/:customerId/deactivate',
    handle: (req, params) => {
      const seed = find(params, req);
      seed.isActive = false;
      return detail(seed);
    },
  },
  {
    method: 'POST',
    path: '/core/customers/:customerId/activate',
    handle: (req, params) => {
      const seed = find(params, req);
      seed.isActive = true;
      return detail(seed);
    },
  },
];
