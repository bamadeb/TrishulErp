import { ListServiceCallImports$Params } from '@trishul/core-api';

// API types come from the generated client; only permission codes and the log query are added here.
export type {
  BydImportLogDetail,
  BydImportLogItem,
  BydImportPreview,
  BydImportResult,
  BydImportRow,
  BydImportSummary,
  FieldChange,
} from '@trishul/core-api';

/**
 * Who may import BYD service calls. Used by the route guard and the menu.
 * The API checks the same code: backend/src/trishul_api/modules/service/router.py (CAN_IMPORT).
 */
export const SERVICE_CALL_IMPORT_PERMISSION = 'svc.call.import';

/** Who may read the import log (router.py CAN_VIEW_IMPORTS): importing also allows it. */
export const SERVICE_CALL_IMPORT_LOG_PERMISSIONS = [
  'svc.call.import.view',
  'svc.call.import',
] as const;

/** Query of the import log; page and page size are always set. */
export type ImportLogQuery = ListServiceCallImports$Params &
  Required<Pick<ListServiceCallImports$Params, 'page' | 'pageSize'>>;
