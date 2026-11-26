import { Injectable, inject } from '@angular/core';
import { Observable, Subscription } from 'rxjs';
import {
  ApiClient,
  ItemImportBatch,
  ItemImportLineOut,
  ItemImportUploader,
  ListItemImportLines$Params,
  ListItemImports$Params,
  PageItemImportBatch,
  PageItemImportLineOut,
  confirmItemImport,
  getItemImport,
  getItemImportErrorReport,
  getItemImportFile,
  getItemImportTemplate,
  listItemImportLines,
  listItemImportUploaders,
  listItemImports,
  uploadItemImport,
} from '@trishul/core-api';

export type {
  ItemImportBatch,
  ItemImportFieldChange,
  ItemImportLineOut,
  ItemImportUploader,
} from '@trishul/core-api';

export type ItemImportStatus = ItemImportBatch['status'];
export type ItemImportDuplicateMode = ItemImportBatch['duplicateMode'];
export type ItemImportHistoryQuery = ListItemImports$Params;
export type ItemImportLineQuery = Omit<ListItemImportLines$Params, 'importId'>;

/** Item list import: upload and check a file, confirm it, and read the history (backend /inv/item-imports). */
@Injectable({ providedIn: 'root' })
export class ItemListImportApi {
  private readonly api = inject(ApiClient);

  /** Stores and checks the file; nothing is imported until confirm(). */
  upload(
    file: File,
    duplicateMode: ItemImportDuplicateMode,
  ): Observable<ItemImportBatch> {
    // The generated body types the file as string (OpenAPI binary); at runtime it is sent as the File.
    return this.api.call(uploadItemImport, {
      body: { file: file as unknown as string, duplicateMode },
    });
  }

  confirm(importId: number): Observable<ItemImportBatch> {
    return this.api.call(confirmItemImport, { importId });
  }

  get(importId: number): Observable<ItemImportBatch> {
    return this.api.call(getItemImport, { importId });
  }

  history(query: ItemImportHistoryQuery): Observable<PageItemImportBatch> {
    return this.api.call(listItemImports, query);
  }

  lines(
    importId: number,
    query: ItemImportLineQuery,
  ): Observable<PageItemImportLineOut> {
    return this.api.call(listItemImportLines, { importId, ...query });
  }

  uploaders(): Observable<ItemImportUploader[]> {
    return this.api.call(listItemImportUploaders);
  }

  downloadTemplate(): Subscription {
    return this.save(
      this.api.call(getItemImportTemplate),
      'item-import-template.xlsx',
    );
  }

  downloadFile(batch: ItemImportBatch): Subscription {
    return this.save(
      this.api.call(getItemImportFile, { importId: batch.id }),
      batch.fileName,
    );
  }

  downloadErrorReport(batch: ItemImportBatch): Subscription {
    return this.save(
      this.api.call(getItemImportErrorReport, { importId: batch.id }),
      `${batch.batchNo ?? batch.id}-errors.xlsx`,
    );
  }

  // The requests are authenticated, so a plain link cannot be used: fetch the bytes and save them.
  private save(request: Observable<Blob>, fileName: string): Subscription {
    return request.subscribe((blob) => {
      const url = URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.download = fileName;
      link.click();
      setTimeout(() => URL.revokeObjectURL(url), 10_000);
    });
  }
}

/** Severity of a batch status / a row's action or outcome, for trishul-status-badge. */
export const ITEM_IMPORT_SEVERITY = {
  Pending: 'info',
  Processing: 'info',
  Completed: 'success',
  'Partially Completed': 'warn',
  Failed: 'danger',
  Create: 'success',
  Update: 'info',
  Skip: 'warn',
  Error: 'danger',
  Created: 'success',
  Updated: 'info',
  Skipped: 'warn',
  'Will be created': 'success',
  'Will be updated': 'info',
  Duplicate: 'warn',
} as const;

/** What a row's action or outcome is called on screen. */
export function itemImportLineLabel(line: ItemImportLineOut): string {
  if (line.outcome) return line.outcome;
  return (
    {
      Create: 'Will be created',
      Update: 'Will be updated',
      Skip: 'Duplicate',
      Error: 'Error',
    } as const
  )[line.action];
}
