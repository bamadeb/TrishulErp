import { Injectable, inject } from '@angular/core';
import { Observable } from 'rxjs';
import {
  ApiClient,
  BydImportPreview,
  BydImportResult,
  applyServiceCallImport,
  previewServiceCallImport,
} from '@trishul/core-api';

/** Uploads a Tata Hitachi BYD export: preview is a dry run, apply upserts the calls. */
@Injectable({ providedIn: 'root' })
export class BydImportApi {
  private readonly api = inject(ApiClient);

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
