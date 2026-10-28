import { HttpRequest } from '@angular/common/http';
import { MockRoute } from '@trishul/core-http';
import {
  BydImportPreview,
  BydImportResult,
  BydImportRow,
  BydImportSummary,
} from '@trishul/service-data-access';

/** Canned BYD import for mock mode and e2e. The real parsing happens in the API; this returns a
 * fixed preview/result so the upload screen can be exercised without a real .xlsx being parsed. */

const rows: BydImportRow[] = [
  {
    rowNumber: 6,
    c4CTicketId: '2628300',
    externalReference: 'SO-1175715',
    subject: 'Job card - Machine overhauling',
    account: 'Chilika Development Authority',
    action: 'insert',
    callNo: null,
    customerMatched: true,
    machineMatched: true,
    engineerMatched: true,
    needsLinking: false,
    messages: [],
  },
  {
    rowNumber: 7,
    c4CTicketId: '2627450',
    externalReference: 'SO-1175488',
    subject: 'Electrical Problem',
    account: 'Golap Manjari Rout',
    action: 'insert',
    callNo: null,
    customerMatched: false,
    machineMatched: false,
    engineerMatched: true,
    needsLinking: true,
    messages: [
      "Customer 'Golap Manjari Rout' not found; linked to the placeholder for later linking.",
    ],
  },
  {
    rowNumber: 8,
    c4CTicketId: null,
    externalReference: 'SO-1175392',
    subject: 'No ticket id',
    account: 'SBB Constructions Pvt Ltd',
    action: 'skip',
    callNo: null,
    customerMatched: false,
    machineMatched: false,
    engineerMatched: false,
    needsLinking: false,
    messages: ['No C4C Ticket ID; the row cannot be identified.'],
  },
];

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
    inserts: 2,
    updates: 0,
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
    handle: (req): BydImportResult => ({
      batchId: 1,
      summary: summary(fileName(req)),
      rows: rows.map((r) =>
        r.action === 'insert'
          ? { ...r, callNo: `SC-${1000 + r.rowNumber}` }
          : r,
      ),
    }),
  },
];
