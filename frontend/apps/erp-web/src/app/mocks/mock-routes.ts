import { HttpParams } from '@angular/common/http';
import { CurrentUser } from '@trishul/core-auth';
import { MockRoute } from '@trishul/core-http';
import { PageServiceCallListItem } from '@trishul/core-api';
import {
  CALL_STATUSES,
  CallPriority,
  ServiceCallListItem,
} from '@trishul/service-data-access';

/** Fixtures used when config.json has "useMockApi": true. They mirror the API contract, not real data. */

const currentUser: CurrentUser = {
  id: 1,
  username: 'demo.admin',
  displayName: 'Demo Admin',
  email: 'demo.admin@example.com',
  defaultBranchId: 1,
  permissions: ['*'],
  branches: [
    { id: 1, code: 'PUN', name: 'Pune' },
    { id: 2, code: 'MUM', name: 'Mumbai' },
    { id: 3, code: 'NGP', name: 'Nagpur' },
  ],
  principals: [
    { id: 1, code: 'ATLAS_COPCO', name: 'Atlas Copco' },
    { id: 2, code: 'TATA_HITACHI', name: 'Tata Hitachi' },
  ],
};

const customers = [
  'Shree Ganesh Infra',
  'Deccan Fabricators',
  'Sahyadri Pharma',
  'Konkan Stone Crushers',
  'Vidarbha Textiles',
  'Pune Auto Components',
  'Marathwada Agro Foods',
];
const machines = [
  ['Atlas Copco', 'GA 37 VSD+', 'API'],
  ['Atlas Copco', 'GA 75', 'AII'],
  ['Atlas Copco', 'FD 300 dryer', 'ITR'],
  ['Tata Hitachi', 'EX 200LC', 'THX'],
  ['Tata Hitachi', 'SHINRAI BX80', 'THB'],
];
const complaints = [
  'High discharge temperature, unit tripping after 20 minutes',
  'Oil carry-over in compressed air line',
  'Service due at 4000 running hours',
  'Hydraulic oil leakage near boom cylinder',
  'Engine not starting, battery checked OK',
  'Abnormal noise from air end',
  'Dryer dew point alarm',
];
const engineers = [
  'Rahul Patil',
  'Sneha Kulkarni',
  'Imran Shaikh',
  'Amit Deshmukh',
  null,
];
const priorities: CallPriority[] = [
  'Critical',
  'High',
  'Normal',
  'Normal',
  'Low',
];

const now = Date.now();
const calls: (ServiceCallListItem & {
  branchId: number;
  principalId: number;
})[] = Array.from({ length: 87 }, (_, i) => {
  const [brand, model, serialPrefix] = machines[i % machines.length];
  const receivedAt = new Date(now - i * 5.5 * 3600_000);
  const status = CALL_STATUSES[(i * 7) % CALL_STATUSES.length];
  return {
    id: 1000 + i,
    callNo: `SC/25-26/${String(4210 - i).padStart(5, '0')}`,
    receivedAt: receivedAt.toISOString(),
    principalCode: brand === 'Atlas Copco' ? 'ATLAS_COPCO' : 'TATA_HITACHI',
    principalId: brand === 'Atlas Copco' ? 1 : 2,
    branchId: (i % 3) + 1,
    customerName: customers[i % customers.length],
    machineSerialNo: `${serialPrefix}${String(600000 + i * 37)}`,
    machineModel: model,
    complaintDescription: complaints[i % complaints.length],
    priority: priorities[i % priorities.length],
    isMachineDown: i % 4 === 0,
    isAscPriority: i % 5 === 0,
    coverageType: (['Warranty', 'Contract', 'Chargeable'] as const)[i % 3],
    currentStatus: status,
    assignedEngineerName:
      status === 'Logged' ? null : engineers[i % engineers.length],
    oemCallId: i % 3 === 0 ? `BYD-${700100 + i}` : null,
    slaDueAt: new Date(receivedAt.getTime() + 24 * 3600_000).toISOString(),
    rowVersion: btoa(`rv-${i}`),
  };
});

function listCalls(
  params: HttpParams,
  branchId: string | null,
  principalId: string | null,
): PageServiceCallListItem {
  const page = Number(params.get('page') ?? 1);
  const pageSize = Number(params.get('pageSize') ?? 20);
  const search = (params.get('search') ?? '').toLowerCase();
  const statuses = params.getAll('status') ?? [];
  const priorityFilter = params.getAll('priority') ?? [];
  const sort = params.get('sort') ?? '-receivedAt';

  let rows = calls.filter(
    (c) =>
      (!branchId || c.branchId === Number(branchId)) &&
      (!principalId || c.principalId === Number(principalId)) &&
      (!statuses.length || statuses.includes(c.currentStatus)) &&
      (!priorityFilter.length || priorityFilter.includes(c.priority)) &&
      (!search ||
        [c.callNo, c.customerName, c.machineSerialNo, c.oemCallId].some((v) =>
          v?.toLowerCase().includes(search),
        )),
  );

  const desc = sort.startsWith('-');
  const field = (desc ? sort.slice(1) : sort) as keyof ServiceCallListItem;
  rows = [...rows].sort((a, b) => {
    const result = String(a[field] ?? '').localeCompare(String(b[field] ?? ''));
    return desc ? -result : result;
  });

  return {
    items: rows.slice((page - 1) * pageSize, page * pageSize),
    total: rows.length,
    page,
    pageSize,
  };
}

export const mockRoutes: MockRoute[] = [
  { method: 'GET', path: '/me', handle: () => currentUser },
  {
    method: 'GET',
    path: '/svc/service-calls',
    handle: (req) =>
      listCalls(
        req.params,
        req.headers.get('X-Branch-Id'),
        req.headers.get('X-Principal-Id'),
      ),
  },
  {
    method: 'GET',
    path: '/core/lookups/:type',
    handle: () => [],
  },
];
