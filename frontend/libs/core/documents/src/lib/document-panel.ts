import { DatePipe, DecimalPipe } from '@angular/common';
import {
  ChangeDetectionStrategy,
  Component,
  DestroyRef,
  OnInit,
  inject,
  input,
  output,
  signal,
} from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { FormsModule } from '@angular/forms';
import { MatButtonModule } from '@angular/material/button';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatIconModule } from '@angular/material/icon';
import { MatInputModule } from '@angular/material/input';
import { MatProgressBarModule } from '@angular/material/progress-bar';
import { MatSelectModule } from '@angular/material/select';
import { MatSnackBar } from '@angular/material/snack-bar';
import { MatTooltipModule } from '@angular/material/tooltip';
import {
  DOCUMENT_ACCEPT,
  DOCUMENT_CATEGORIES,
  DocumentApi,
  DocumentCategory,
  DocumentOut,
  documentFileProblem,
} from './document.api';

/**
 * Documents of one record: list, upload, view, download, rename, change type and remove.
 *
 *   <trishul-document-panel entityType="trk.manual_travel" [entityId]="id" />
 *
 * The same panel serves every module. What the signed-in user may do is decided by the API for that
 * record (each row's canDelete); `readonly` only hides the upload controls for a screen that never edits.
 */
@Component({
  selector: 'trishul-document-panel',
  imports: [
    DatePipe,
    DecimalPipe,
    FormsModule,
    MatButtonModule,
    MatFormFieldModule,
    MatIconModule,
    MatInputModule,
    MatProgressBarModule,
    MatSelectModule,
    MatTooltipModule,
  ],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <section class="docs" [attr.aria-label]="title()">
      <h4>{{ title() }} ({{ docs().length }})</h4>
      @if (loading() || busy()) {
        <mat-progress-bar mode="indeterminate" />
      }

      @if (failed()) {
        <p class="msg error" role="alert">
          <mat-icon inline>error_outline</mat-icon> Could not load the
          documents.
          <button mat-button type="button" (click)="load()">Retry</button>
        </p>
      } @else if (!loading() && docs().length === 0) {
        <p class="msg muted">No documents attached yet.</p>
      }

      <ul class="list">
        @for (d of docs(); track d.id) {
          <li>
            <mat-icon class="kind" aria-hidden="true">{{
              icon(d)
            }}</mat-icon>
            <div class="meta">
              @if (renamingId() === d.id) {
                <form class="rename" (submit)="saveRename(d, $event)">
                  <mat-form-field appearance="outline" subscriptSizing="dynamic">
                    <input
                      matInput
                      name="fileName"
                      aria-label="File name"
                      maxlength="200"
                      [ngModel]="d.fileName"
                      (ngModelChange)="draftName.set($event)"
                    />
                  </mat-form-field>
                  <mat-form-field appearance="outline" subscriptSizing="dynamic">
                    <mat-select
                      aria-label="Document type"
                      [value]="draftCategory()"
                      (valueChange)="draftCategory.set($event)"
                    >
                      @for (c of categories; track c) {
                        <mat-option [value]="c">{{ c }}</mat-option>
                      }
                    </mat-select>
                  </mat-form-field>
                  <button mat-flat-button type="submit">Save</button>
                  <button mat-button type="button" (click)="renamingId.set(null)">
                    Cancel
                  </button>
                </form>
              } @else {
                <span class="name">{{ d.fileName }}</span>
                <span class="sub">
                  {{ d.category }} · {{ size(d.fileSizeBytes) }} ·
                  {{ d.uploadedByName ?? 'Unknown' }} ·
                  {{ d.uploadedAt | date: 'dd MMM yyyy, hh:mm a' }}
                </span>
              }
            </div>
            @if (renamingId() !== d.id) {
              <div class="actions">
                <button
                  mat-icon-button
                  type="button"
                  matTooltip="View"
                  aria-label="View document"
                  (click)="open(d)"
                >
                  <mat-icon>visibility</mat-icon>
                </button>
                <button
                  mat-icon-button
                  type="button"
                  matTooltip="Download"
                  aria-label="Download document"
                  (click)="download(d)"
                >
                  <mat-icon>download</mat-icon>
                </button>
                @if (d.canDelete && !readonly()) {
                  <button
                    mat-icon-button
                    type="button"
                    matTooltip="Rename or change type"
                    aria-label="Rename document"
                    (click)="startRename(d)"
                  >
                    <mat-icon>edit</mat-icon>
                  </button>
                  @if (confirmId() === d.id) {
                    <button mat-button type="button" class="danger" (click)="remove(d)">
                      Remove?
                    </button>
                    <button mat-button type="button" (click)="confirmId.set(null)">
                      Keep
                    </button>
                  } @else {
                    <button
                      mat-icon-button
                      type="button"
                      matTooltip="Remove"
                      aria-label="Remove document"
                      (click)="confirmId.set(d.id)"
                    >
                      <mat-icon>delete</mat-icon>
                    </button>
                  }
                }
              </div>
            }
          </li>
        }
      </ul>

      @if (!readonly()) {
        <div class="upload">
          <mat-form-field appearance="outline" subscriptSizing="dynamic">
            <mat-label>Document type</mat-label>
            <mat-select
              [value]="category()"
              (valueChange)="category.set($event)"
            >
              @for (c of categories; track c) {
                <mat-option [value]="c">{{ c }}</mat-option>
              }
            </mat-select>
          </mat-form-field>
          <button
            mat-stroked-button
            type="button"
            [disabled]="busy()"
            (click)="picker.click()"
          >
            <mat-icon>upload_file</mat-icon> Upload ticket / document
          </button>
          <input
            #picker
            type="file"
            hidden
            multiple
            [accept]="accept"
            (change)="pick($event)"
          />
        </div>
        <p class="hint">PDF, JPG, JPEG or PNG · up to 10 MB each</p>
      }
    </section>
  `,
  styles: `
    .docs h4 {
      margin: 0 0 0.5rem;
      font: var(--mat-sys-title-small);
    }
    .list {
      margin: 0;
      padding: 0;
      list-style: none;
    }
    li {
      display: flex;
      align-items: center;
      gap: 0.75rem;
      padding: 0.5rem 0;
      border-bottom: 1px solid var(--mat-sys-outline-variant);
    }
    .kind {
      flex: none;
      color: var(--mat-sys-primary);
    }
    .meta {
      display: flex;
      flex: 1;
      flex-direction: column;
      min-width: 0;
    }
    .name {
      font-weight: 500;
      overflow-wrap: anywhere;
    }
    .sub,
    .hint,
    .muted {
      font: var(--mat-sys-body-small);
      color: var(--mat-sys-on-surface-variant);
    }
    .actions {
      display: flex;
      flex: none;
      align-items: center;
    }
    .danger {
      color: var(--mat-sys-error);
    }
    .rename {
      display: flex;
      flex-wrap: wrap;
      align-items: center;
      gap: 0.5rem;
    }
    .upload {
      display: flex;
      flex-wrap: wrap;
      align-items: center;
      gap: 0.75rem;
      margin-top: 0.75rem;
    }
    .hint {
      margin: 0.25rem 0 0;
    }
    .msg {
      display: flex;
      align-items: center;
      gap: 0.25rem;
      margin: 0.5rem 0;
    }
    .error {
      color: var(--mat-sys-error);
    }
    @media (max-width: 520px) {
      li {
        flex-wrap: wrap;
      }
      .actions {
        width: 100%;
        justify-content: flex-end;
      }
    }
  `,
})
export class DocumentPanel implements OnInit {
  /** The record's table, e.g. "trk.manual_travel". */
  readonly entityType = input.required<string>();
  /** The record's id. */
  readonly entityId = input.required<number>();
  readonly title = input('Documents');
  /** Hide the upload, rename and remove controls. */
  readonly readonly = input(false);
  /** Fires after an upload or removal with the new document count. */
  readonly changed = output<number>();

  protected readonly categories = DOCUMENT_CATEGORIES;
  protected readonly accept = DOCUMENT_ACCEPT;
  protected readonly docs = signal<DocumentOut[]>([]);
  protected readonly loading = signal(false);
  protected readonly failed = signal(false);
  protected readonly busy = signal(false);
  protected readonly category = signal<DocumentCategory>('Document');
  protected readonly renamingId = signal<number | null>(null);
  protected readonly confirmId = signal<number | null>(null);
  protected readonly draftName = signal('');
  protected readonly draftCategory = signal<DocumentCategory>('Document');

  private readonly api = inject(DocumentApi);
  private readonly snackBar = inject(MatSnackBar);
  private readonly destroyRef = inject(DestroyRef);

  ngOnInit(): void {
    this.load();
  }

  protected load(): void {
    this.loading.set(true);
    this.failed.set(false);
    this.api
      .list(this.entityType(), this.entityId())
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: (docs) => {
          this.docs.set(docs);
          this.loading.set(false);
        },
        error: () => {
          this.failed.set(true);
          this.loading.set(false);
        },
      });
  }

  protected pick(event: Event): void {
    const input = event.target as HTMLInputElement;
    const files = Array.from(input.files ?? []);
    input.value = ''; // so the same file can be chosen again
    this.uploadNext(files);
  }

  /** One at a time, so the document-count limit and error messages stay in order. */
  private uploadNext(files: File[]): void {
    const [file, ...rest] = files;
    if (!file) return;
    const problem = documentFileProblem(file);
    if (problem) {
      this.snackBar.open(`${file.name}: ${problem}`, 'OK', { duration: 6000 });
      this.uploadNext(rest);
      return;
    }
    this.busy.set(true);
    this.api
      .upload(this.entityType(), this.entityId(), file, this.category())
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: (doc) => {
          this.docs.update((list) => [...list, doc]);
          this.busy.set(false);
          this.changed.emit(this.docs().length);
          this.uploadNext(rest);
        },
        // The global interceptor shows the server's message.
        error: () => this.busy.set(false),
      });
  }

  protected startRename(doc: DocumentOut): void {
    this.confirmId.set(null);
    this.draftName.set(doc.fileName);
    this.draftCategory.set(doc.category as DocumentCategory);
    this.renamingId.set(doc.id);
  }

  protected saveRename(doc: DocumentOut, event: Event): void {
    event.preventDefault();
    const fileName = this.draftName().trim();
    if (!fileName) return;
    this.busy.set(true);
    this.api
      .update(doc, { fileName, category: this.draftCategory() })
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: (updated) => {
          this.docs.update((list) =>
            list.map((d) => (d.id === updated.id ? updated : d)),
          );
          this.renamingId.set(null);
          this.busy.set(false);
        },
        error: () => this.busy.set(false),
      });
  }

  protected remove(doc: DocumentOut): void {
    this.busy.set(true);
    this.api
      .remove(doc)
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: () => {
          this.docs.update((list) => list.filter((d) => d.id !== doc.id));
          this.confirmId.set(null);
          this.busy.set(false);
          this.changed.emit(this.docs().length);
        },
        error: () => this.busy.set(false),
      });
  }

  protected open(doc: DocumentOut): void {
    // Open the tab first (a popup blocker only allows it inside the click), then point it at the file.
    const tab = window.open('', '_blank');
    this.api
      .content(doc.id, true)
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: (blob) => {
          const url = URL.createObjectURL(blob);
          if (tab) tab.location.href = url;
          else this.save(url, doc.fileName);
          setTimeout(() => URL.revokeObjectURL(url), 60_000);
        },
        error: () => tab?.close(),
      });
  }

  protected download(doc: DocumentOut): void {
    this.api
      .content(doc.id)
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe((blob) => {
        const url = URL.createObjectURL(blob);
        this.save(url, doc.fileName);
        URL.revokeObjectURL(url);
      });
  }

  private save(url: string, fileName: string): void {
    const link = document.createElement('a');
    link.href = url;
    link.download = fileName;
    link.click();
  }

  protected icon(doc: DocumentOut): string {
    return doc.contentType === 'application/pdf'
      ? 'picture_as_pdf'
      : 'image';
  }

  protected size(bytes: number | null): string {
    if (bytes === null) return '—';
    return bytes >= 1024 * 1024
      ? `${(bytes / 1024 / 1024).toFixed(1)} MB`
      : `${Math.max(1, Math.round(bytes / 1024))} KB`;
  }
}
