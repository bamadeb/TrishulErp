import { Injectable, inject } from '@angular/core';
import { Observable } from 'rxjs';
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
export const DOCUMENT_ACCEPT = '.pdf,.jpg,.jpeg,.png';
export const DOCUMENT_MAX_BYTES = 10 * 1024 * 1024;

const ALLOWED_EXTENSIONS = ['pdf', 'jpg', 'jpeg', 'png'];

/** Why this file cannot be uploaded, or null when it can. */
export function documentFileProblem(file: File): string | null {
  const extension = file.name.split('.').pop()?.toLowerCase() ?? '';
  if (!ALLOWED_EXTENSIONS.includes(extension)) {
    return 'Only PDF, JPG, JPEG and PNG files can be uploaded.';
  }
  if (file.size === 0) return 'The file is empty.';
  if (file.size > DOCUMENT_MAX_BYTES) return 'The file must be 10 MB or smaller.';
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
