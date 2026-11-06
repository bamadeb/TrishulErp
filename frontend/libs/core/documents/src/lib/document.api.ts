import { Injectable, inject } from '@angular/core';
import { Observable, Subscription } from 'rxjs';
import {
  ApiClient,
  DocumentOut,
  DocumentUpdate,
  deleteDocument,
  getDocumentContent,
  listDocuments,
  updateDocument,
  uploadDocument,
  withRowVersion,
} from '@trishul/core-api';

export type { DocumentOut } from '@trishul/core-api';

export type DocumentCategory = 'Document' | 'Invoice' | 'Photo' | 'Other';

/** Document types a user can pick; "Document" suits tickets and general paperwork. */
export const DOCUMENT_CATEGORIES: readonly DocumentCategory[] = [
  'Document',
  'Invoice',
  'Photo',
  'Other',
];

/** What the API accepts, checked here too so the user gets the message before the upload starts. */
export const DOCUMENT_ACCEPT =
  '.pdf,.doc,.docx,.xls,.xlsx,.jpg,.jpeg,.png,.gif,.webp';
export const DOCUMENT_FORMATS_HINT =
  'PDF, Word, Excel or image (JPG, PNG, GIF, WebP) · up to 10 MB each';
export const DOCUMENT_MAX_BYTES = 10 * 1024 * 1024;

const ALLOWED_EXTENSIONS = [
  'pdf',
  'doc',
  'docx',
  'xls',
  'xlsx',
  'jpg',
  'jpeg',
  'png',
  'gif',
  'webp',
];

/** Why this file cannot be uploaded, or null when it can. */
export function documentFileProblem(file: File): string | null {
  const extension = file.name.split('.').pop()?.toLowerCase() ?? '';
  if (!ALLOWED_EXTENSIONS.includes(extension)) {
    return 'Only PDF, Word, Excel and image files can be uploaded.';
  }
  if (file.size === 0) return 'The file is empty.';
  if (file.size > DOCUMENT_MAX_BYTES)
    return 'The file must be 10 MB or smaller.';
  return null;
}

/** The common document endpoints (/core/documents), for any module's records. */
@Injectable({ providedIn: 'root' })
export class DocumentApi {
  private readonly api = inject(ApiClient);

  list(entityType: string, entityId: number): Observable<DocumentOut[]> {
    return this.api.call(listDocuments, { entityType, entityId });
  }

  upload(
    entityType: string,
    entityId: number,
    file: File,
    category: DocumentCategory,
  ): Observable<DocumentOut> {
    return this.api.call(uploadDocument, {
      body: { entityType, entityId, category, file },
    });
  }

  /** The file's bytes; the request is authenticated, so a plain link cannot be used. */
  content(documentId: number, inline = false): Observable<Blob> {
    return this.api.call(getDocumentContent, { documentId, inline });
  }

  /**
   * Shows the file in a new tab. The tab is opened first (a popup blocker only allows that inside the
   * click) and pointed at the file once it arrives; if the browser blocked it, the file is saved instead.
   */
  view(documentId: number, fileName: string): Subscription {
    const tab = window.open('', '_blank');
    return this.content(documentId, true).subscribe({
      next: (blob) => {
        const url = URL.createObjectURL(blob);
        if (tab) tab.location.href = url;
        else saveBlobUrl(url, fileName);
        setTimeout(() => URL.revokeObjectURL(url), 60_000);
      },
      error: () => tab?.close(),
    });
  }

  download(documentId: number, fileName: string): Subscription {
    return this.content(documentId).subscribe((blob) => {
      const url = URL.createObjectURL(blob);
      saveBlobUrl(url, fileName);
      URL.revokeObjectURL(url);
    });
  }

  update(doc: DocumentOut, body: DocumentUpdate): Observable<DocumentOut> {
    return this.api.call(
      updateDocument,
      { documentId: doc.id, body },
      withRowVersion(doc.rowVersion),
    );
  }

  remove(doc: DocumentOut): Observable<void> {
    return this.api.call(
      deleteDocument,
      { documentId: doc.id },
      withRowVersion(doc.rowVersion),
    );
  }
}

function saveBlobUrl(url: string, fileName: string): void {
  const link = document.createElement('a');
  link.href = url;
  link.download = fileName;
  link.click();
}

/** Material icon for a file, by its content type. */
export function documentIcon(contentType: string | null | undefined): string {
  if (contentType === 'application/pdf') return 'picture_as_pdf';
  if (contentType?.startsWith('image/')) return 'image';
  if (
    contentType?.includes('spreadsheet') ||
    contentType === 'application/vnd.ms-excel'
  ) {
    return 'table_chart';
  }
  if (contentType?.includes('word')) return 'description';
  return 'draft';
}
