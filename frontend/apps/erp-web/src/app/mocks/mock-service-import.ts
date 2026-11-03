import { HttpErrorResponse, HttpRequest } from '@angular/common/http';
import { MockRoute } from '@trishul/core-http';
import {
  BydImportLogDetail,
  BydImportLogItem,
  BydImportPreview,
  BydImportResult,
  BydImportRow,
  BydImportSummary,
} from '@trishul/service-data-access';

/** Canned BYD import for mock mode and e2e. The real parsing happens in the API; this returns a
 * fixed preview/result so the upload screen can be exercised without a real .xlsx being parsed.
 * Each applied import is added to an in-memory import log. */

const rows: BydImportRow[] = [
  {
    rowNumber: 6,
    c4CTicketId: '2628300',
    externalReference: 'SO-1175715',
    subject: 'Job card - Machine overhauling',
    account: 'Chilika Development Authority',
    action: 'insert',
    serviceCallId: null,
    callNo: null,
    customerMatched: true,
    machineMatched: true,
    engineerMatched: true,
    needsLinking: false,
    messages: [],
    changes: [],
  },
  {
    rowNumber: 7,
    c4CTicketId: '2627450',
    externalReference: 'SO-1175488',
    subject: 'Electrical Problem',
    account: 'Golap Manjari Rout',
    action: 'update',
    serviceCallId: null,
    callNo: 'SC-1007',
    customerMatched: false,
    machineMatched: false,
    engineerMatched: true,
    needsLinking: true,
    messages: [
      "Customer 'Golap Manjari Rout' not found; linked to the placeholder for later linking.",
    ],
    changes: [],
  },
  {
    rowNumber: 8,
    c4CTicketId: null,
    externalReference: 'SO-1175392',
    subject: 'No ticket id',
    account: 'SBB Constructions Pvt Ltd',
    action: 'skip',
    serviceCallId: null,
    callNo: null,
    customerMatched: false,
    machineMatched: false,
    engineerMatched: false,
    needsLinking: false,
    messages: ['No C4C Ticket ID; the row cannot be identified.'],
    changes: [],
  },
];

/** What applying the file does: the insert gets a call number, the update changes two fields. */
const appliedRows: BydImportRow[] = rows.map((r) => {
  if (r.action === 'insert')
    return { ...r, callNo: `SC-${1000 + r.rowNumber}` };
  if (r.action === 'update')
    return {
      ...r,
      changes: [
        { field: 'Priority', old: 'Normal', new: 'High' },
        { field: 'Engineer', old: 'Satyajit Tung', new: 'Amit Das' },
      ],
    };
  return r;
});

const log: BydImportLogDetail[] = [];

function fileName(req: HttpRequest<unknown>): string {
  const body = req.body as FormData | null;
  const file = body?.get?.('file');
  return file instanceof File ? file.name : 'export.xlsx';
}

function summary(name: string): BydImportSummary {
  return {
    sourceKind: 'Service orders',
    fileName: name,
    total: 3,
    inserts: 1,
    updates: 1,
    skips: 1,
    needsLinking: 1,
  };
}

export const mockServiceImportRoutes: MockRoute[] = [
  {
    method: 'POST',
    path: '/svc/service-calls/import/preview',
    handle: (req): BydImportPreview => ({
      summary: summary(fileName(req)),
      rows,
    }),
  },
  {
    method: 'POST',
    path: '/svc/service-calls/import',
    handle: (req): BydImportResult => {
      const s = summary(fileName(req));
      const entry: BydImportLogDetail = {
        id: log.length + 1,
        fileName: s.fileName,
        sourceKind: s.sourceKind,
        branchName: 'Pune',
        principalCode: 'TATA_HITACHI',
        importedAt: new Date().toISOString(),
        importedByName: 'Demo Admin',
        totalRows: s.total,
        insertedCount: s.inserts,
        updatedCount: s.updates,
        unlinkedCount: s.needsLinking,
        failedCount: s.skips,
        rows: appliedRows,
      };
      log.unshift(entry);
      return { batchId: entry.id, summary: s, rows: appliedRows };
    },
  },
  {
    method: 'GET',
    path: '/svc/service-call-imports',
    handle: (req) => {
      const page = Number(req.params.get('page') ?? 1);
      const pageSize = Number(req.params.get('pageSize') ?? 20);
      // A log item is the entry without its rows.
      const items = log.map(
        (entry): BydImportLogItem =>
          ({ ...entry, rows: undefined }) as BydImportLogItem,
      );
      return {
        items: items.slice((page - 1) * pageSize, page * pageSize),
        total: items.length,
        page,
        pageSize,
      };
    },
  },
  {
    method: 'GET',
    path: '/svc/service-call-imports/:importId',
    handle: (req, params) => {
      const entry = log.find((e) => e.id === Number(params['importId']));
      if (!entry) {
        throw new HttpErrorResponse({
          status: 404,
          url: req.url,
          error: {
            status: 404,
            title: 'Not found',
            detail: 'Import not found.',
          },
        });
      }
      return entry;
    },
  },
];
