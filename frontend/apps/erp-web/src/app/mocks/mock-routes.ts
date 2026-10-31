import { HttpErrorResponse, HttpParams } from '@angular/common/http';
import { CurrentUser } from '@trishul/core-auth';
import { MockRoute } from '@trishul/core-http';
import { mockCustomerRoutes } from './mock-customers';
import { mockEmployeeRoutes } from './mock-employees';
import { mockServiceImportRoutes } from './mock-service-import';
import { mockUserRoutes } from './mock-users';
import { PageServiceCallListItem } from '@trishul/core-api';
import {
  CALL_STATUSES,
  CallPriority,
  CallStatusLogItem,
  EngineerOption,
  LookupValueOut,
  MachineUnitOption,
  ServiceCallCreate,
  ServiceCallDetail,
  ServiceCallListItem,
  ServiceCallStatusChange,
  ServiceCallTriageUpdate,
} from '@trishul/service-data-access';

/** Status changes made in mock mode, per call id (newest first), shown in the detail page's history. */
const mockHistory = new Map<number, CallStatusLogItem[]>();
let mockHistoryId = 1;

const MOCK_ENGINEERS: EngineerOption[] = [
  { id: 10, name: 'Rahul Patil', employeeCode: 'EMP0010' },
  { id: 11, name: 'Sneha Kulkarni', employeeCode: 'EMP0011' },
  { id: 12, name: 'Imran Shaikh', employeeCode: 'EMP0012' },
];

// Mirrors the mock customer seeds (see mock-customers.ts) so the triage PATCH can echo a name.
const MOCK_CUSTOMER_NAMES: Record<number, string> = {
  10: 'Blue Earth Movers',
  11: 'Deccan Fabricators Pvt Ltd',
  12: 'Ravi Kumar',
};

const LOOKUPS: Record<string, LookupValueOut[]> = {
  CALL_TYPE: [
    { id: 1, code: 'BREAKDOWN', name: 'Breakdown', sortOrder: 1 },
    { id: 2, code: 'PERIODIC_SERVICE', name: 'Periodic service', sortOrder: 2 },
    { id: 3, code: 'INSTALLATION', name: 'Installation', sortOrder: 3 },
    { id: 4, code: 'INSPECTION', name: 'Inspection', sortOrder: 4 },
  ],
  CALL_SOURCE: [
    { id: 11, code: 'PHONE', name: 'Phone', sortOrder: 1 },
    { id: 12, code: 'WHATSAPP', name: 'WhatsApp', sortOrder: 2 },
    { id: 13, code: 'EMAIL', name: 'Email', sortOrder: 3 },
  ],
};

const MOCK_MACHINES: MachineUnitOption[] = [
  { id: 1, serialNumber: 'THX600123', modelName: 'EX 200LC', customerName: 'Shree Ganesh Infra' },
  { id: 2, serialNumber: 'THB700456', modelName: 'SHINRAI BX80', customerName: 'Deccan Fabricators' },
  { id: 3, serialNumber: 'API300789', modelName: 'GA 37 VSD+', customerName: 'Sahyadri Pharma' },
];

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
    path: '/core/lookups/:typeCode/values',
    handle: (_req, params) => LOOKUPS[params['typeCode']] ?? [],
  },
  {
    method: 'GET',
    path: '/svc/service-calls/engineer-options',
    handle: (req): EngineerOption[] => {
      const search = (req.params.get('search') ?? '').toLowerCase();
      return MOCK_ENGINEERS.filter(
        (e) => !search || e.name.toLowerCase().includes(search),
      );
    },
  },
  {
    method: 'PATCH',
    path: '/svc/service-calls/:callId',
    handle: (req, params): ServiceCallListItem => {
      const call = calls.find((c) => c.id === Number(params['callId']));
      if (!call) {
        throw new HttpErrorResponse({
          status: 404,
          url: req.url,
          error: { status: 404, title: 'Not found', detail: 'Call not found.' },
        });
      }
      const body = req.body as ServiceCallTriageUpdate;
      if (body.priority) call.priority = body.priority;
      if (body.customerId != null) {
        call.customerName =
          MOCK_CUSTOMER_NAMES[body.customerId] ?? `Customer #${body.customerId}`;
      }
      if ('engineerId' in body) {
        if (body.engineerId == null) {
          call.assignedEngineerName = null;
          if (call.currentStatus === 'Assigned') call.currentStatus = 'Logged';
        } else {
          call.assignedEngineerName =
            MOCK_ENGINEERS.find((e) => e.id === body.engineerId)?.name ?? null;
          if (call.currentStatus === 'Logged') call.currentStatus = 'Assigned';
        }
      }
      call.rowVersion = btoa(`rv-${call.id}-${Date.now()}`);
      return call;
    },
  },
  {
    method: 'GET',
    path: '/svc/service-calls/machine-options',
    handle: (req): MachineUnitOption[] => {
      const search = (req.params.get('search') ?? '').toLowerCase();
      return MOCK_MACHINES.filter(
        (m) =>
          !search ||
          m.serialNumber.toLowerCase().includes(search) ||
          (m.modelName ?? '').toLowerCase().includes(search),
      );
    },
  },
  {
    method: 'GET',
    path: '/svc/service-calls/:callId',
    handle: (req, params): ServiceCallDetail => {
      const call = calls.find((c) => c.id === Number(params['callId']));
      if (!call) {
        throw new HttpErrorResponse({
          status: 404,
          url: req.url,
          error: { status: 404, title: 'Not found', detail: 'Call not found.' },
        });
      }
      const branches: Record<number, string> = { 1: 'Pune', 2: 'Mumbai', 3: 'Nagpur' };
      return {
        id: call.id,
        callNo: call.callNo,
        receivedAt: call.receivedAt,
        branchName: branches[call.branchId] ?? null,
        principalCode: call.principalCode,
        principalName:
          call.principalCode === 'ATLAS_COPCO' ? 'Atlas Copco' : 'Tata Hitachi',
        customerId: 10,
        customerName: call.customerName,
        customerPhone: '9820000000',
        machineUnitId: null,
        machineSerialNo: call.machineSerialNo,
        machineModel: call.machineModel,
        complaintDescription: call.complaintDescription,
        callType: 'Breakdown',
        callSource: 'Phone',
        priority: call.priority,
        isMachineDown: call.isMachineDown,
        isAscPriority: call.isAscPriority,
        coverageType: call.coverageType,
        currentStatus: call.currentStatus,
        assignedEngineerId: null,
        assignedEngineerName: call.assignedEngineerName,
        callerName: 'Nilamadhab Sahoo',
        callerPhone: '7894435328',
        oemCallId: call.oemCallId,
        sourceReference: null,
        slaDueAt: call.slaDueAt,
        firstResponseAt: null,
        closedAt: null,
        siteName: null,
        siteAddress: null,
        needsMasterLinking: false,
        allowedStatuses: CALL_STATUSES.filter(
          (s) =>
            s !== call.currentStatus &&
            !['Closed', 'Completed', 'Cancelled', 'Reopened'].includes(s),
        ),
        rowVersion: call.rowVersion,
      };
    },
  },
  {
    method: 'GET',
    path: '/svc/service-calls/:callId/status-history',
    handle: (_req, params): CallStatusLogItem[] =>
      mockHistory.get(Number(params['callId'])) ?? [
        {
          id: 0,
          fromStatus: null,
          toStatus: 'Logged',
          changedAt: new Date(Date.now() - 86_400_000).toISOString(),
          changedByName: 'Demo Admin',
          remarks: 'Call logged',
        },
      ],
  },
  {
    method: 'POST',
    path: '/svc/service-calls/:callId/status',
    handle: (req, params): ServiceCallDetail => {
      const call = calls.find((c) => c.id === Number(params['callId']));
      if (!call) {
        throw new HttpErrorResponse({
          status: 404,
          url: req.url,
          error: { status: 404, title: 'Not found', detail: 'Call not found.' },
        });
      }
      const body = req.body as ServiceCallStatusChange;
      const rows = mockHistory.get(call.id) ?? [];
      rows.unshift({
        id: mockHistoryId++,
        fromStatus: call.currentStatus,
        toStatus: body.status,
        changedAt: new Date().toISOString(),
        changedByName: 'Demo Admin',
        remarks: body.remarks ?? null,
      });
      mockHistory.set(call.id, rows);
      call.currentStatus = body.status;
      call.rowVersion = btoa(`rv-${call.id}-${Date.now()}`);
      return {
        id: call.id,
        callNo: call.callNo,
        receivedAt: call.receivedAt,
        branchName: null,
        principalCode: call.principalCode,
        principalName: null,
        customerId: 10,
        customerName: call.customerName,
        customerPhone: null,
        machineUnitId: null,
        machineSerialNo: call.machineSerialNo,
        machineModel: call.machineModel,
        complaintDescription: call.complaintDescription,
        callType: null,
        callSource: null,
        priority: call.priority,
        isMachineDown: call.isMachineDown,
        isAscPriority: call.isAscPriority,
        coverageType: call.coverageType,
        currentStatus: call.currentStatus,
        assignedEngineerId: null,
        assignedEngineerName: call.assignedEngineerName,
        callerName: null,
        callerPhone: '7894435328',
        oemCallId: call.oemCallId,
        sourceReference: null,
        slaDueAt: call.slaDueAt,
        firstResponseAt: null,
        closedAt: null,
        siteName: null,
        siteAddress: null,
        needsMasterLinking: false,
        allowedStatuses: CALL_STATUSES.filter(
          (s) =>
            s !== call.currentStatus &&
            !['Closed', 'Completed', 'Cancelled', 'Reopened'].includes(s),
        ),
        rowVersion: call.rowVersion,
      };
    },
  },
  {
    method: 'POST',
    path: '/svc/service-calls',
    handle: (req): ServiceCallListItem => {
      const body = req.body as ServiceCallCreate;
      const machine = MOCK_MACHINES.find((m) => m.id === body.machineUnitId);
      return {
        id: Math.floor(Math.random() * 100000),
        callNo: `SC/25-26/${String(Math.floor(Math.random() * 90000) + 10000)}`,
        receivedAt: body.receivedAt ?? new Date().toISOString(),
        principalCode: 'TATA_HITACHI',
        customerName: `Customer #${body.customerId}`,
        machineSerialNo: machine?.serialNumber ?? null,
        machineModel: machine?.modelName ?? null,
        complaintDescription: body.complaintDescription,
        priority: body.priority ?? 'Normal',
        isMachineDown: body.isMachineDown ?? false,
        isAscPriority: false,
        coverageType: null,
        currentStatus: 'Logged',
        assignedEngineerName: null,
        oemCallId: null,
        slaDueAt: null,
        rowVersion: btoa(`new-${Date.now()}`),
      };
    },
  },
  ...mockServiceImportRoutes,
  ...mockUserRoutes,
  ...mockEmployeeRoutes,
  ...mockCustomerRoutes,
];
