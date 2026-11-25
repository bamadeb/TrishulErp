import { Injectable, inject } from '@angular/core';
import { Observable } from 'rxjs';
import {
  ApiClient,
  ItemImportPreview,
  applyItemImport,
  previewItemImport,
} from '@trishul/core-api';

export type {
  ItemImportIssue,
  ItemImportPreview,
  ItemImportResult,
  ItemImportRow,
  ItemImportSummary,
} from '@trishul/core-api';

/** Where the file's price (ZAmount) is stored on the item. */
export type ItemPriceField = 'mrp' | 'standardCost';

export interface ItemImportOptions {
  /** Needed when the file has parts that are not in the item master yet. */
  categoryId: number | null;
  /** Leave out to use the category's default unit. */
  uomId: number | null;
  priceField: ItemPriceField;
}

/** Uploads the spare-part price file: preview is a dry run, apply creates items and updates prices / HSN codes. */
@Injectable({ providedIn: 'root' })
export class ItemImportApi {
  private readonly api = inject(ApiClient);

  preview(
    file: File,
    options: ItemImportOptions,
  ): Observable<ItemImportPreview> {
    return this.api.call(previewItemImport, { body: this.body(file, options) });
  }

  apply(
    file: File,
    options: ItemImportOptions,
  ): Observable<ItemImportPreview> {
    return this.api.call(applyItemImport, { body: this.body(file, options) });
  }

  // The generated body types the file as string (OpenAPI binary); at runtime it is sent as the File.
  private body(file: File, options: ItemImportOptions) {
    return {
      file: file as unknown as string,
      categoryId: options.categoryId,
      uomId: options.uomId,
      priceField: options.priceField,
    };
  }
}
