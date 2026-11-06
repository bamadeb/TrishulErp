import { ListDocumentLibrary$Params } from '@trishul/core-api';
import { allOf } from '@trishul/shared-util';

export type {
  DocumentEntityType,
  DocumentLibraryItem,
  DocumentRecordOption,
} from '@trishul/core-api';

export type DocumentLibraryQuery = Required<
  Pick<ListDocumentLibrary$Params, 'page' | 'pageSize'>
> &
  ListDocumentLibrary$Params;

/** Document types a user can choose; the same list the upload form offers. */
export const DOCUMENT_CATEGORY_FILTERS = allOf<
  NonNullable<ListDocumentLibrary$Params['category']>
>()(['Document', 'Invoice', 'Photo', 'Other']);

/**
 * Open the Documents screen / remove or rename any document. The API checks the same codes
 * (backend modules/core/documents/router.py).
 */
export const DOCUMENT_VIEW_PERMISSIONS = [
  'core.document.view',
  'core.document.manage',
] as const;
export const DOCUMENT_MANAGE_PERMISSION = 'core.document.manage';
