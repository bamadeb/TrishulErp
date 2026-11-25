import { DecimalPipe } from '@angular/common';
import {
  ChangeDetectionStrategy,
  Component,
  DestroyRef,
  computed,
  inject,
  signal,
} from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { FormsModule } from '@angular/forms';
import { MatButton, MatIconButton } from '@angular/material/button';
import {
  MatError,
  MatFormField,
  MatHint,
  MatLabel,
} from '@angular/material/form-field';
import { MatIcon } from '@angular/material/icon';
import { MatInput } from '@angular/material/input';
import { MatProgressBar } from '@angular/material/progress-bar';
import { MatOption, MatSelect } from '@angular/material/select';
import { MatSnackBar } from '@angular/material/snack-bar';
import { Router, RouterLink } from '@angular/router';
import { concatMap, from, last, of, catchError, defaultIfEmpty } from 'rxjs';
import {
  COMPLAINT_ENTITY_TYPE,
  ComplaintDepartmentOption,
  ComplaintsApi,
} from '@trishul/admin-data-access';
import {
  DOCUMENT_ACCEPT,
  DOCUMENT_FORMATS_HINT,
  DocumentApi,
  documentFileProblem,
} from '@trishul/core-documents';
import { PageHeader } from '@trishul/shared-ui';

const MAX_FILES = 10;

/** Raise a complaint: department, issue type, what happened, and optional photos or documents. */
@Component({
  selector: 'trishul-complaint-raise-page',
  imports: [
    DecimalPipe,
    FormsModule,
    RouterLink,
    MatButton,
    MatIconButton,
    MatIcon,
    MatFormField,
    MatLabel,
    MatHint,
    MatError,
    MatInput,
    MatSelect,
    MatOption,
    MatProgressBar,
    PageHeader,
  ],
  changeDetection: ChangeDetectionStrategy.OnPush,
  styleUrl: './complaints.scss',
  styles: `
    form {
      display: grid;
      gap: 1rem;
      max-width: 44rem;
    }
    .row {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(14rem, 1fr));
      gap: 1rem;
    }
    .files {
      margin: 0;
      padding: 0;
      list-style: none;
    }
    .files li {
      display: flex;
      align-items: center;
      gap: 0.5rem;
      padding: 0.25rem 0;
      border-bottom: 1px solid var(--mat-sys-outline-variant);
    }
    .files .file-name {
      flex: 1;
      overflow-wrap: anywhere;
    }
    .actions {
      display: flex;
      gap: 0.75rem;
      justify-content: flex-end;
    }
  `,
  template: `
    <trishul-page-header
      title="Raise a complaint"
      subtitle="Tell the department what the problem is. You can follow it under My complaints."
    />

    <div class="card">
      @if (loading()) {
        <mat-progress-bar mode="indeterminate" />
      }
      @if (failed()) {
        <p class="error" role="alert">
          The departments could not be loaded.
          <button mat-button type="button" (click)="loadDepartments()">
            Retry
          </button>
        </p>
      } @else if (!loading() && departments().length === 0) {
        <p class="notice" role="status">
          <mat-icon>info</mat-icon>
          No department takes complaints yet. Ask an administrator to add
          issue types.
        </p>
      } @else {
        <form #f="ngForm" (ngSubmit)="submit()" novalidate>
          <div class="row">
            <mat-form-field appearance="outline">
              <mat-label>Department</mat-label>
              <mat-select
                name="department"
                required
                [ngModel]="departmentId()"
                (ngModelChange)="pickDepartment($event)"
              >
                @for (d of departments(); track d.id) {
                  <mat-option [value]="d.id">{{ d.name }}</mat-option>
                }
              </mat-select>
              <mat-hint>Who should handle it</mat-hint>
              <mat-error>Choose a department</mat-error>
            </mat-form-field>
            <mat-form-field appearance="outline">
              <mat-label>Issue type</mat-label>
              <mat-select
                name="issueType"
                required
                [disabled]="!departmentId()"
                [ngModel]="issueTypeId()"
                (ngModelChange)="issueTypeId.set($event)"
              >
                @for (t of issueTypes(); track t.id) {
                  <mat-option [value]="t.id">{{ t.name }}</mat-option>
                }
              </mat-select>
              @if (issueHint(); as hint) {
                <mat-hint>{{ hint }}</mat-hint>
              }
              <mat-error>Choose an issue type</mat-error>
            </mat-form-field>
          </div>

          <mat-form-field appearance="outline">
            <mat-label>Describe the issue</mat-label>
            <textarea
              matInput
              name="description"
              required
              minlength="5"
              maxlength="2000"
              rows="6"
              [ngModel]="description()"
              (ngModelChange)="description.set($event)"
            ></textarea>
            <mat-hint align="end">{{ description().length }} / 2000</mat-hint>
            <mat-error>Write at least 5 characters</mat-error>
          </mat-form-field>

          <section aria-label="Attachments">
            <h3>Attachments (optional)</h3>
            @if (files().length) {
              <ul class="files">
                @for (file of files(); track $index) {
                  <li>
                    <mat-icon aria-hidden="true">{{
                      file.type.startsWith('image/') ? 'image' : 'description'
                    }}</mat-icon>
                    <span class="file-name">{{ file.name }}</span>
                    <span class="muted"
                      >{{ file.size / 1024 | number: '1.0-0' }} KB</span
                    >
                    <button
                      mat-icon-button
                      type="button"
                      [attr.aria-label]="'Remove ' + file.name"
                      (click)="removeFile($index)"
                    >
                      <mat-icon>close</mat-icon>
                    </button>
                  </li>
                }
              </ul>
            }
            <button
              mat-stroked-button
              type="button"
              [disabled]="files().length >= maxFiles || saving()"
              (click)="picker.click()"
            >
              <mat-icon>attach_file</mat-icon> Add photo or document
            </button>
            <input
              #picker
              type="file"
              hidden
              multiple
              [accept]="accept"
              (change)="pickFiles($event)"
            />
            <p class="muted">
              {{ formatsHint }} · up to {{ maxFiles }} files. On a phone you
              can take a photo directly.
            </p>
          </section>

          @if (saving()) {
            <mat-progress-bar mode="indeterminate" />
          }
          <div class="actions">
            <a mat-button routerLink="/complaints/mine">Cancel</a>
            <button
              mat-flat-button
              type="submit"
              [disabled]="saving() || f.invalid"
            >
              <mat-icon>send</mat-icon> Submit complaint
            </button>
          </div>
        </form>
      }
    </div>
  `,
})
export class ComplaintRaisePage {
  private readonly api = inject(ComplaintsApi);
  private readonly documents = inject(DocumentApi);
  private readonly router = inject(Router);
  private readonly snackBar = inject(MatSnackBar);
  private readonly destroyRef = inject(DestroyRef);

  protected readonly accept = DOCUMENT_ACCEPT;
  protected readonly formatsHint = DOCUMENT_FORMATS_HINT;
  protected readonly maxFiles = MAX_FILES;
  protected readonly departments = signal<ComplaintDepartmentOption[]>([]);
  protected readonly loading = signal(false);
  protected readonly failed = signal(false);
  protected readonly saving = signal(false);
  protected readonly departmentId = signal<number | null>(null);
  protected readonly issueTypeId = signal<number | null>(null);
  protected readonly description = signal('');
  protected readonly files = signal<File[]>([]);

  protected readonly issueTypes = computed(
    () =>
      this.departments().find((d) => d.id === this.departmentId())
        ?.issueTypes ?? [],
  );
  protected readonly issueHint = computed(
    () =>
      this.issueTypes().find((t) => t.id === this.issueTypeId())
        ?.description ?? null,
  );

  constructor() {
    this.loadDepartments();
  }

  protected loadDepartments(): void {
    this.loading.set(true);
    this.failed.set(false);
    this.api
      .departments()
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: (list) => {
          this.departments.set(list);
          this.loading.set(false);
        },
        error: () => {
          this.failed.set(true);
          this.loading.set(false);
        },
      });
  }

  protected pickDepartment(id: number): void {
    this.departmentId.set(id);
    const types = this.issueTypes();
    this.issueTypeId.set(types.length === 1 ? types[0].id : null);
  }

  protected pickFiles(event: Event): void {
    const input = event.target as HTMLInputElement;
    const picked = Array.from(input.files ?? []);
    input.value = '';
    const accepted: File[] = [];
    for (const file of picked) {
      const problem = documentFileProblem(file);
      if (problem) {
        this.snackBar.open(`${file.name}: ${problem}`, 'OK', { duration: 6000 });
      } else {
        accepted.push(file);
      }
    }
    const room = MAX_FILES - this.files().length;
    if (accepted.length > room) {
      this.snackBar.open(`Only ${MAX_FILES} files can be attached.`, 'OK', {
        duration: 5000,
      });
    }
    this.files.update((list) => [...list, ...accepted.slice(0, room)]);
  }

  protected removeFile(index: number): void {
    this.files.update((list) => list.filter((_, i) => i !== index));
  }

  protected submit(): void {
    const departmentId = this.departmentId();
    const issueTypeId = this.issueTypeId();
    if (!departmentId || !issueTypeId || this.saving()) return;
    this.saving.set(true);
    this.api
      .create({
        departmentId,
        issueTypeId,
        description: this.description().trim(),
      })
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: (complaint) => this.uploadThenOpen(complaint.id, complaint.complaintNo),
        // The global interceptor shows the server's message.
        error: () => this.saving.set(false),
      });
  }

  /** The complaint is saved first; then each file is attached to it, one at a time. */
  private uploadThenOpen(id: number, complaintNo: string): void {
    let failedUploads = 0;
    from(this.files())
      .pipe(
        concatMap((file) =>
          this.documents
            .upload(
              COMPLAINT_ENTITY_TYPE,
              id,
              file,
              file.type.startsWith('image/') ? 'Photo' : 'Document',
            )
            .pipe(
              catchError(() => {
                failedUploads += 1;
                return of(null);
              }),
            ),
        ),
        defaultIfEmpty(null),
        last(),
        takeUntilDestroyed(this.destroyRef),
      )
      .subscribe(() => {
        this.saving.set(false);
        const note = failedUploads
          ? ` ${failedUploads} file(s) could not be attached; add them on the complaint.`
          : '';
        this.snackBar.open(`Complaint ${complaintNo} raised.${note}`, 'OK', {
          duration: failedUploads ? 8000 : 4000,
        });
        this.router.navigate(['/complaints', id]);
      });
  }
}
