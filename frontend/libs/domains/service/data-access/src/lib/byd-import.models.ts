// API types come from the generated client; only the permission code is added here.
export type {
  BydImportPreview,
  BydImportResult,
  BydImportRow,
  BydImportSummary,
} from '@trishul/core-api';

/**
 * Who may import BYD service calls. Used by the route guard and the menu.
 * The API checks the same code: backend/src/trishul_api/modules/service/router.py (CAN_IMPORT).
 */
export const SERVICE_CALL_IMPORT_PERMISSION = 'svc.call.import';
