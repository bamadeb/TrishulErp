import { Injectable, inject } from '@angular/core';
import { Observable, Subscription } from 'rxjs';
import {
  ApiClient,
  ListPriceImportLines$Params,
  ListPriceImports$Params,
  PageItemPriceChange,
  PagePriceImportBatch,
  PagePriceImportLineOut,
  PriceImportBatch,
  PriceImportOptions,
  PriceImportUploader,
  PriceSettings,
  approvePriceImport,
  confirmPriceImport,
  getPriceImport,
  getPriceImportErrorReport,
  getPriceImportFile,
  getPriceImportOptions,
  getPriceImportTemplate,
  getPriceSettings,
  listItemPriceHistory,
  listPriceImportLines,
  listPriceImportUploaders,
  listPriceImports,
  rejectPriceImport,
  updatePriceSettings,
  uploadPriceImport,
  withRowVersion,
} from '@trishul/core-api';

export type {
  ItemPriceChange,
  PriceImportBatch,
  PriceImportLineOut,
  PriceImportOptions,
  PriceImportUploader,
  PriceListOption,
  PriceSettings,
} from '@trishul/core-api';

export type PriceImportStatus = PriceImportBatch['status'];
export type SapPriceField = NonNullable<PriceImportBatch['sapPriceField']>;
export type PriceImportHistoryQuery = ListPriceImports$Params;
export type PriceImportLineQuery = Omit<
  ListPriceImportLines$Params,
  'importId'
>;

export interface PriceUploadOptions {
  reason: string;
  /** Needed for selling prices. */
  priceListId: number | null;
  /** Which price the ZAmount of an SAP price file updates. */
  sapPriceField: SapPriceField;
}

/** Bulk item price import (backend /inv/price-imports), the price change limit and an item's price history. */
@Injectable({ providedIn: 'root' })
export class PriceImportApi {
  private readonly api = inject(ApiClient);

  options(): Observable<PriceImportOptions> {
    return this.api.call(getPriceImportOptions);
  }

  /** Stores the file and compares it with the current prices; nothing changes until confirm(). */
  upload(
    file: File,
    options: PriceUploadOptions,
  ): Observable<PriceImportBatch> {
    // The generated body types the file as string (OpenAPI binary); at runtime it is sent as the File.
    return this.api.call(uploadPriceImport, {
      body: {
        file: file as unknown as string,
        reason: options.reason,
        priceListId: options.priceListId,
        sapPriceField: options.sapPriceField,
      },
    });
  }

  confirm(
    importId: number,
    importAgain: boolean,
  ): Observable<PriceImportBatch> {
    return this.api.call(confirmPriceImport, {
      importId,
      body: { importAgain },
    });
  }

  approve(importId: number, note: string | null): Observable<PriceImportBatch> {
    return this.api.call(approvePriceImport, { importId, body: { note } });
  }

  reject(importId: number, note: string | null): Observable<PriceImportBatch> {
    return this.api.call(rejectPriceImport, { importId, body: { note } });
  }

  get(importId: number): Observable<PriceImportBatch> {
    return this.api.call(getPriceImport, { importId });
  }

  history(query: PriceImportHistoryQuery): Observable<PagePriceImportBatch> {
    return this.api.call(listPriceImports, query);
  }

  lines(
    importId: number,
    query: PriceImportLineQuery,
  ): Observable<PagePriceImportLineOut> {
    return this.api.call(listPriceImportLines, { importId, ...query });
  }

  uploaders(): Observable<PriceImportUploader[]> {
    return this.api.call(listPriceImportUploaders);
  }

  itemHistory(
    itemId: number,
    page = 1,
    pageSize = 20,
  ): Observable<PageItemPriceChange> {
    return this.api.call(listItemPriceHistory, { itemId, page, pageSize });
  }

  settings(): Observable<PriceSettings> {
    return this.api.call(getPriceSettings);
  }

  updateSettings(
    current: PriceSettings,
    maxChangePct: number,
  ): Observable<PriceSettings> {
    return this.api.call(
      updatePriceSettings,
      { body: { maxChangePct: String(maxChangePct) } },
      withRowVersion(current.rowVersion ?? ''),
    );
  }

  downloadTemplate(): Subscription {
    return this.save(
      this.api.call(getPriceImportTemplate),
      'item-price-template.xlsx',
    );
  }

  downloadFile(batch: PriceImportBatch): Subscription {
    return this.save(
      this.api.call(getPriceImportFile, { importId: batch.id }),
      batch.fileName,
    );
  }

  downloadErrorReport(batch: PriceImportBatch): Subscription {
    return this.save(
      this.api.call(getPriceImportErrorReport, { importId: batch.id }),
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

/** Severity of a batch status or a row's result, for trishul-status-badge. */
export const PRICE_IMPORT_SEVERITY = {
  Pending: 'info',
  'Pending approval': 'warn',
  Processing: 'info',
  Completed: 'success',
  'Partially Completed': 'warn',
  Failed: 'danger',
  Rejected: 'danger',
  Change: 'info',
  Unchanged: 'neutral',
  Duplicate: 'warn',
  Error: 'danger',
  Updated: 'success',
  Skipped: 'warn',
  'Will change': 'info',
  'Needs approval': 'warn',
} as const;
