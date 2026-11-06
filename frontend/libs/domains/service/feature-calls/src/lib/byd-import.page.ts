import { MatOptgroup } from '@angular/material/core';
import {
  ChangeDetectionStrategy,
  Component,
  computed,
  inject,
  signal,
} from '@angular/core';
import { MatButton } from '@angular/material/button';
import { MatFormField, MatLabel } from '@angular/material/form-field';
import { MatIcon } from '@angular/material/icon';
import { MatProgressBar } from '@angular/material/progress-bar';
import { MatSnackBar } from '@angular/material/snack-bar';
import { MatOption, MatSelect } from '@angular/material/select';
import { RouterLink } from '@angular/router';
import { EMPTY, catchError, finalize } from 'rxjs';
import { AuthStore, BranchGroupsPipe } from '@trishul/core-auth';
import {
  BydImportApi,
  BydImportPreview,
  BydImportResult,
} from '@trishul/service-data-access';
import { PageHeader } from '@trishul/shared-ui';
import { ImportRowsTable } from './import-rows-table';

/** Upload a Tata Hitachi BYD export, preview what it would do, then import (upsert) the calls. */
@Component({
  selector: 'trishul-byd-import-page',
  imports: [
    BranchGroupsPipe,
    MatOptgroup,
    MatButton,
    MatIcon,
    MatFormField,
    MatLabel,
    MatSelect,
    MatOption,
    MatProgressBar,
    RouterLink,
    PageHeader,
    ImportRowsTable,
  ],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './byd-import.page.html',
  styleUrl: './byd-import.page.scss',
})
export class BydImportPage {
  private readonly api = inject(BydImportApi);
  private readonly auth = inject(AuthStore);
  private readonly snackBar = inject(MatSnackBar);

  protected readonly file = signal<File | null>(null);
  protected readonly branchId = signal<number | null>(this.auth.branchId());
  protected readonly preview = signal<BydImportPreview | null>(null);
  protected readonly result = signal<BydImportResult | null>(null);
  protected readonly busy = signal(false);

  protected readonly branches = computed(
    () => this.auth.user()?.branches ?? [],
  );
  protected readonly summary = computed(
    () => this.result()?.summary ?? this.preview()?.summary ?? null,
  );
  protected readonly rows = computed(
    () => this.result()?.rows ?? this.preview()?.rows ?? [],
  );
  protected readonly ready = computed(
    () => this.file() !== null && this.branchId() !== null && !this.busy(),
  );

  protected onFileChange(event: Event): void {
    const input = event.target as HTMLInputElement;
    this.file.set(input.files?.[0] ?? null);
    this.preview.set(null);
    this.result.set(null);
  }

  protected doPreview(): void {
    const file = this.file();
    const branchId = this.branchId();
    if (!file || branchId === null || this.busy()) return;
    this.busy.set(true);
    this.result.set(null);
    this.api
      .preview(file, branchId)
      .pipe(
        finalize(() => this.busy.set(false)),
        catchError(() => EMPTY), // the global interceptor shows the error toast
      )
      .subscribe((preview) => this.preview.set(preview));
  }

  protected doImport(): void {
    const file = this.file();
    const branchId = this.branchId();
    if (!file || branchId === null || this.busy()) return;
    this.busy.set(true);
    this.api
      .apply(file, branchId)
      .pipe(
        finalize(() => this.busy.set(false)),
        catchError(() => EMPTY),
      )
      .subscribe((result) => {
        this.preview.set(null);
        this.result.set(result);
        const s = result.summary;
        this.snackBar.open(
          `Imported: ${s.inserts} new, ${s.updates} updated` +
            (s.needsLinking ? `, ${s.needsLinking} to link` : ''),
          'Dismiss',
          { duration: 6000 },
        );
      });
  }
}
