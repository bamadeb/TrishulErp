import { DatePipe } from '@angular/common';
import { ChangeDetectionStrategy, Component, inject } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { MatButton, MatIconButton } from '@angular/material/button';
import { MatDialog } from '@angular/material/dialog';
import {
  MatFormField,
  MatLabel,
  MatPrefix,
} from '@angular/material/form-field';
import { MatIcon } from '@angular/material/icon';
import { MatInput } from '@angular/material/input';
import { MatPaginator, PageEvent } from '@angular/material/paginator';
import { MatProgressBar } from '@angular/material/progress-bar';
import { MatOption, MatSelect } from '@angular/material/select';
import { MatSnackBar } from '@angular/material/snack-bar';
import { MatSort, MatSortHeader, Sort } from '@angular/material/sort';
import { MatTableModule } from '@angular/material/table';
import { MatTooltip } from '@angular/material/tooltip';
import {
  Subject,
  debounceTime,
  distinctUntilChanged,
  filter,
  switchMap,
} from 'rxjs';
import {
  DOCUMENT_CATEGORY_FILTERS,
  DOCUMENT_MANAGE_PERMISSION,
  DocumentLibraryApi,
  DocumentLibraryItem,
  DocumentLibraryStore,
} from '@trishul/admin-data-access';
import { HasPermission } from '@trishul/core-auth';
import { DocumentApi, documentIcon } from '@trishul/core-documents';
import { PageHeader, confirmAction } from '@trishul/shared-ui';
import { DocumentUploadDialog } from './document-upload.dialog';

/**
 * Administration > Documents: the library of every uploaded document, whichever module it belongs to.
 * Any module that registers a document target on the server shows up here automatically.
 */
@Component({
  selector: 'trishul-document-list-page',
  imports: [
    DatePipe,
    MatTableModule,
    MatSort,
    MatSortHeader,
    MatPaginator,
    MatProgressBar,
    MatFormField,
    MatLabel,
    MatPrefix,
    MatInput,
    MatSelect,
    MatOption,
    MatButton,
    MatIconButton,
    MatIcon,
    MatTooltip,
    PageHeader,
    HasPermission,
  ],
  providers: [DocumentLibraryStore],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './document-list.page.html',
  styleUrls: ['./customer-list.page.scss', './document-list.page.scss'],
})
export class DocumentListPage {
  protected readonly store = inject(DocumentLibraryStore);
  private readonly library = inject(DocumentLibraryApi);
  private readonly files = inject(DocumentApi);
  private readonly dialog = inject(MatDialog);
  private readonly snackBar = inject(MatSnackBar);

  protected readonly columns = [
    'fileName',
    'category',
    'entityType',
    'fileSizeBytes',
    'uploadedBy',
    'uploadedAt',
    'actions',
  ];
  protected readonly categories = DOCUMENT_CATEGORY_FILTERS;
  protected readonly managePermission = DOCUMENT_MANAGE_PERMISSION;

  private readonly search$ = new Subject<string>();

  constructor() {
    this.search$
      .pipe(debounceTime(350), distinctUntilChanged(), takeUntilDestroyed())
      .subscribe((search) =>
        this.store.updateQuery({ search: search || undefined }),
      );
  }

  protected onSearch(value: string): void {
    this.search$.next(value.trim());
  }

  protected onSort(sort: Sort): void {
    this.store.updateQuery({
      sort: sort.direction
        ? `${sort.direction === 'desc' ? '-' : ''}${sort.active}`
        : undefined,
    });
  }

  protected onPage(event: PageEvent): void {
    this.store.updateQuery({
      page: event.pageIndex + 1,
      pageSize: event.pageSize,
    });
  }

  protected upload(): void {
    this.dialog
      .open(DocumentUploadDialog, {
        data: { entityTypes: this.store.entityTypes() },
        width: '34rem',
        maxWidth: '95vw',
        autoFocus: 'dialog',
        disableClose: true,
      })
      .afterClosed()
      .subscribe((uploaded?: boolean) => {
        if (uploaded) this.store.reload();
      });
  }

  protected view(doc: DocumentLibraryItem): void {
    this.files.view(doc.id, doc.fileName);
  }

  protected download(doc: DocumentLibraryItem): void {
    this.files.download(doc.id, doc.fileName);
  }

  protected remove(doc: DocumentLibraryItem): void {
    confirmAction(this.dialog, {
      title: 'Remove document?',
      message:
        `"${doc.fileName}" (${doc.entityLabel}, ${doc.recordLabel ?? '#' + doc.entityId}) ` +
        'will be deleted for everyone. This cannot be undone.',
      confirmText: 'Remove',
      destructive: true,
    })
      .pipe(
        filter(Boolean),
        switchMap(() => this.library.remove(doc)),
      )
      .subscribe(() => {
        this.snackBar.open('Document removed', 'OK', { duration: 4000 });
        this.store.reload();
      });
  }

  protected icon(doc: DocumentLibraryItem): string {
    return documentIcon(doc.contentType);
  }

  protected size(bytes: number | null): string {
    if (bytes === null) return '—';
    return bytes >= 1024 * 1024
      ? `${(bytes / 1024 / 1024).toFixed(1)} MB`
      : `${Math.max(1, Math.round(bytes / 1024))} KB`;
  }
}
