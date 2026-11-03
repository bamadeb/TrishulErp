import { Injectable, inject } from '@angular/core';
import { Observable } from 'rxjs';
import {
  ApiClient,
  BydImportLogDetail,
  BydImportPreview,
  BydImportResult,
  PageBydImportLogItem,
  applyServiceCallImport,
  getServiceCallImport,
  listServiceCallImports,
  previewServiceCallImport,
} from '@trishul/core-api';
import { ImportLogQuery } from './byd-import.models';

/** Uploads a Tata Hitachi BYD export (preview is a dry run, apply upserts the calls) and reads the import log. */
@Injectable({ providedIn: 'root' })
export class BydImportApi {
  private readonly api = inject(ApiClient);

  /** Uploads in the selected branch and brand, newest first. */
  log(query: ImportLogQuery): Observable<PageBydImportLogItem> {
    return this.api.call(listServiceCallImports, query);
  }

  /** One upload with what happened to every row. */
  logEntry(importId: number): Observable<BydImportLogDetail> {
    return this.api.call(getServiceCallImport, { importId });
  }

  preview(file: File, branchId: number): Observable<BydImportPreview> {
    return this.api.call(previewServiceCallImport, {
      body: this.body(file, branchId),
    });
  }

  apply(file: File, branchId: number): Observable<BydImportResult> {
    return this.api.call(applyServiceCallImport, {
      body: this.body(file, branchId),
    });
  }

  // The generated body types the file as string (OpenAPI binary); at runtime it is sent as the File.
  private body(
    file: File,
    branchId: number,
  ): { file: string; branchId: number } {
    return { file: file as unknown as string, branchId };
  }
}
