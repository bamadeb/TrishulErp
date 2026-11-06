import {
  ChangeDetectionStrategy,
  Component,
  DestroyRef,
  inject,
  signal,
} from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { MatAutocompleteModule } from '@angular/material/autocomplete';
import { MatButtonModule } from '@angular/material/button';
import {
  MAT_DIALOG_DATA,
  MatDialogModule,
  MatDialogRef,
} from '@angular/material/dialog';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatIconModule } from '@angular/material/icon';
import { MatInputModule } from '@angular/material/input';
import { MatProgressBarModule } from '@angular/material/progress-bar';
import { MatSelectModule } from '@angular/material/select';
import { Subject, catchError, debounceTime, of, switchMap } from 'rxjs';
import {
  DOCUMENT_CATEGORY_FILTERS,
  DocumentEntityType,
  DocumentLibraryApi,
  DocumentRecordOption,
} from '@trishul/admin-data-access';
import {
  DOCUMENT_ACCEPT,
  DOCUMENT_FORMATS_HINT,
  DocumentApi,
  documentFileProblem,
  documentIcon,
} from '@trishul/core-documents';

export interface DocumentUploadData {
  entityTypes: DocumentEntityType[];
}

type FileState = 'waiting' | 'uploading' | 'done' | 'failed';

interface QueuedFile {
  file: File;
  state: FileState;
  /** Why this file is not going to be (or was not) uploaded. */
  problem: string | null;
}

/**
 * Upload documents to any record of a module: pick the module, find the record by name or number, choose
 * the document type, then add the files. Files go up one after another through the common document API.
 */
@Component({
  selector: 'trishul-document-upload-dialog',
  imports: [
    MatDialogModule,
    MatButtonModule,
    MatFormFieldModule,
    MatIconModule,
    MatInputModule,
    MatAutocompleteModule,
    MatProgressBarModule,
    MatSelectModule,
  ],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <h2 mat-dialog-title>Upload documents</h2>
    <mat-dialog-content>
      <mat-form-field appearance="outline">
        <mat-label>Module</mat-label>
        <mat-select
          [value]="entityType()"
          (valueChange)="pickModule($event)"
          [disabled]="busy()"
        >
          @for (t of data.entityTypes; track t.entityType) {
            <mat-option [value]="t.entityType">{{ t.label }}</mat-option>
          }
        </mat-select>
      </mat-form-field>

      <mat-form-field appearance="outline">
        <mat-label>Record</mat-label>
        <input
          matInput
          [matAutocomplete]="records"
          [disabled]="!entityType() || busy()"
          [value]="recordText()"
          placeholder="Type a name or number"
          (input)="onRecordInput($any($event.target).value)"
        />
        <mat-autocomplete
          #records="matAutocomplete"
          (optionSelected)="pickRecord($event.option.value)"
          [displayWith]="recordLabel"
        >
          @for (r of options(); track r.id) {
            <mat-option [value]="r">{{ r.label }}</mat-option>
          } @empty {
            @if (searched()) {
              <mat-option disabled>Nothing found</mat-option>
            }
          }
        </mat-autocomplete>
        @if (!record() && entityType()) {
          <mat-hint>Choose one from the list</mat-hint>
        }
      </mat-form-field>

      <mat-form-field appearance="outline">
        <mat-label>Document type</mat-label>
        <mat-select
          [value]="category()"
          (valueChange)="category.set($event)"
          [disabled]="busy()"
        >
          @for (c of categories; track c) {
            <mat-option [value]="c">{{ c }}</mat-option>
          }
        </mat-select>
      </mat-form-field>

      <button
        mat-stroked-button
        type="button"
        [disabled]="!record() || busy()"
        (click)="picker.click()"
      >
        <mat-icon>attach_file</mat-icon> Choose files
      </button>
      <input
        #picker
        type="file"
        hidden
        multiple
        [accept]="accept"
        (change)="addFiles($event)"
      />
      <p class="hint">{{ formatsHint }}</p>

      @if (queue().length) {
        <ul class="files">
          @for (q of queue(); track $index) {
            <li [class.failed]="q.state === 'failed' || q.problem">
              <mat-icon aria-hidden="true">{{ icon(q.file) }}</mat-icon>
              <span class="name">{{ q.file.name }}</span>
              <span class="state">
                @if (q.problem) {
                  {{ q.problem }}
                } @else if (q.state === 'done') {
                  Uploaded
                } @else if (q.state === 'uploading') {
                  Uploading…
                } @else if (q.state === 'failed') {
                  Failed
                }
              </span>
              @if (q.state === 'waiting' && !busy()) {
                <button
                  mat-icon-button
                  type="button"
                  aria-label="Remove from list"
                  (click)="drop($index)"
                >
                  <mat-icon>close</mat-icon>
                </button>
              }
            </li>
          }
        </ul>
      }
      @if (busy()) {
        <mat-progress-bar mode="indeterminate" />
      }
    </mat-dialog-content>
    <mat-dialog-actions align="end">
      <button mat-button type="button" (click)="finish()" [disabled]="busy()">
        {{ uploaded() ? 'Done' : 'Cancel' }}
      </button>
      <button
        mat-flat-button
        type="button"
        [disabled]="busy() || !ready()"
        (click)="start()"
      >
        Upload
      </button>
    </mat-dialog-actions>
  `,
  styles: `
    mat-form-field {
      width: 100%;
    }
    .hint {
      margin: 0.5rem 0 0;
      font: var(--mat-sys-body-small);
      color: var(--mat-sys-on-surface-variant);
    }
    .files {
      margin: 0.75rem 0 0;
      padding: 0;
      list-style: none;
    }
    li {
      display: flex;
      align-items: center;
      gap: 0.5rem;
      padding: 0.25rem 0;
      border-bottom: 1px solid var(--mat-sys-outline-variant);
    }
    .name {
      flex: 1;
      min-width: 0;
      overflow-wrap: anywhere;
    }
    .state {
      font: var(--mat-sys-body-small);
      color: var(--mat-sys-on-surface-variant);
    }
    li.failed .state {
      color: var(--mat-sys-error);
    }
  `,
})
export class DocumentUploadDialog {
  protected readonly data = inject<DocumentUploadData>(MAT_DIALOG_DATA);
  private readonly dialogRef =
    inject<MatDialogRef<DocumentUploadDialog, boolean>>(MatDialogRef);
  private readonly library = inject(DocumentLibraryApi);
  private readonly api = inject(DocumentApi);
  private readonly destroyRef = inject(DestroyRef);

  protected readonly categories = DOCUMENT_CATEGORY_FILTERS;
  protected readonly accept = DOCUMENT_ACCEPT;
  protected readonly formatsHint = DOCUMENT_FORMATS_HINT;

  protected readonly entityType = signal<string | null>(null);
  protected readonly record = signal<DocumentRecordOption | null>(null);
  protected readonly recordText = signal('');
  protected readonly options = signal<DocumentRecordOption[]>([]);
  protected readonly searched = signal(false);
  protected readonly category = signal<
    'Document' | 'Invoice' | 'Photo' | 'Other'
  >('Document');
  protected readonly queue = signal<QueuedFile[]>([]);
  protected readonly busy = signal(false);
  protected readonly uploaded = signal(false);

  private readonly typed$ = new Subject<string>();

  constructor() {
    this.typed$
      .pipe(
        debounceTime(300),
        switchMap((text) => {
          const type = this.entityType();
          if (!type) return of([] as DocumentRecordOption[]);
          return this.library
            .records(type, text)
            .pipe(catchError(() => of([] as DocumentRecordOption[])));
        }),
        takeUntilDestroyed(this.destroyRef),
      )
      .subscribe((found) => {
        this.options.set(found);
        this.searched.set(true);
      });
  }

  protected readonly recordLabel = (
    option: DocumentRecordOption | string | null,
  ): string => (typeof option === 'string' ? option : (option?.label ?? ''));

  protected pickModule(type: string): void {
    this.entityType.set(type);
    this.record.set(null);
    this.recordText.set('');
    this.options.set([]);
    this.searched.set(false);
    this.typed$.next(''); // load the first records so the list is not empty on focus
  }

  protected onRecordInput(text: string): void {
    this.recordText.set(text);
    this.record.set(null); // typing again un-chooses the record
    this.typed$.next(text.trim());
  }

  protected pickRecord(option: DocumentRecordOption): void {
    this.record.set(option);
    this.recordText.set(option.label);
  }

  protected addFiles(event: Event): void {
    const input = event.target as HTMLInputElement;
    const added = Array.from(input.files ?? []).map<QueuedFile>((file) => ({
      file,
      state: 'waiting',
      problem: documentFileProblem(file),
    }));
    input.value = '';
    this.queue.update((q) => [...q, ...added]);
  }

  protected drop(index: number): void {
    this.queue.update((q) => q.filter((_, i) => i !== index));
  }

  protected ready(): boolean {
    return (
      this.record() !== null &&
      this.queue().some((q) => q.state === 'waiting' && !q.problem)
    );
  }

  protected icon(file: File): string {
    return documentIcon(file.type || file.name.toLowerCase());
  }

  protected start(): void {
    const record = this.record();
    const type = this.entityType();
    if (!record || !type) return;
    this.busy.set(true);
    this.next(type, record.id);
  }

  /** Uploads the next waiting file; stops being busy when none is left. */
  private next(type: string, id: number): void {
    const index = this.queue().findIndex(
      (q) => q.state === 'waiting' && !q.problem,
    );
    if (index === -1) {
      this.busy.set(false);
      return;
    }
    this.mark(index, 'uploading');
    this.api
      .upload(type, id, this.queue()[index].file, this.category())
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: () => {
          this.uploaded.set(true);
          this.mark(index, 'done');
          this.next(type, id);
        },
        // The global interceptor shows the server's message; keep going with the other files.
        error: () => {
          this.mark(index, 'failed');
          this.next(type, id);
        },
      });
  }

  private mark(index: number, state: FileState): void {
    this.queue.update((q) =>
      q.map((item, i) => (i === index ? { ...item, state } : item)),
    );
  }

  protected finish(): void {
    this.dialogRef.close(this.uploaded());
  }
}
