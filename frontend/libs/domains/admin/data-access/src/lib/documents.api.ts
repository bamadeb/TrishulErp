import { Injectable, inject } from '@angular/core';
import { Observable } from 'rxjs';
import {
  ApiClient,
  PageDocumentLibraryItem,
  deleteDocument,
  listDocumentRecords,
  listDocumentEntityTypes,
  listDocumentLibrary,
  withRowVersion,
} from '@trishul/core-api';
import {
  DocumentEntityType,
  DocumentLibraryItem,
  DocumentLibraryQuery,
  DocumentRecordOption,
} from './documents.models';

/** /core/documents/library: every document of every module, for the Administration screen. */
@Injectable({ providedIn: 'root' })
export class DocumentLibraryApi {
  private readonly api = inject(ApiClient);

  list(query: DocumentLibraryQuery): Observable<PageDocumentLibraryItem> {
    return this.api.call(listDocumentLibrary, query);
  }

  /** Kinds of record that carry documents, for the module filter. */
  entityTypes(): Observable<DocumentEntityType[]> {
    return this.api.call(listDocumentEntityTypes);
  }

  /** Records of a module a document can be attached to, found by name or number. */
  records(
    entityType: string,
    search: string,
  ): Observable<DocumentRecordOption[]> {
    return this.api.call(listDocumentRecords, { entityType, search });
  }

  /** rowVersion from the list; a newer change by someone else gives 409. */
  remove(doc: DocumentLibraryItem): Observable<void> {
    return this.api.call(
      deleteDocument,
      { documentId: doc.id },
      withRowVersion(doc.rowVersion),
    );
  }
}
