import { MatOptgroup } from '@angular/material/core';
import { DatePipe } from '@angular/common';
import {
  ChangeDetectionStrategy,
  Component,
  computed,
  inject,
  signal,
} from '@angular/core';
import { MatButton } from '@angular/material/button';
import { MatButtonToggle, MatButtonToggleGroup } from '@angular/material/button-toggle';
import { MatFormField, MatLabel } from '@angular/material/form-field';
import { MatIcon } from '@angular/material/icon';
import { MatProgressBar } from '@angular/material/progress-bar';
import { MatOption, MatSelect } from '@angular/material/select';
import { MatSnackBar } from '@angular/material/snack-bar';
import { MatTableModule } from '@angular/material/table';
import { RouterLink } from '@angular/router';
import { EMPTY, catchError, finalize } from 'rxjs';
import { AuthStore, BranchGroupsPipe } from '@trishul/core-auth';
import {
  AscApi,
  AscImportResult,
  AscImportRow,
} from '@trishul/service-data-access';
import { PageHeader, StatusBadge, StatusSeverity } from '@trishul/shared-ui';

type RowFilter = 'all' | 'insert' | 'update' | 'new' | 'skip';

const ACTION_LABELS: Record<string, string> = {
  insert: 'New ASC',
  update: 'Update',
  skip: 'Skipped',
};
const ACTION_SEVERITY: Record<string, StatusSeverity> = {
  'New ASC': 'success',
  Update: 'info',
  Skipped: 'neutral',
};

/** Upload the team's ASC register (Excel), preview what it would do, then import it. */
@Component({
  selector: 'trishul-asc-import-page',
  imports: [
    BranchGroupsPipe,
    MatOptgroup,
    DatePipe,
    MatButton,
    MatButtonToggleGroup,
    MatButtonToggle,
    MatIcon,
    MatFormField,
    MatLabel,
    MatSelect,
    MatOption,
    MatProgressBar,
    MatTableModule,
    RouterLink,
    PageHeader,
    StatusBadge,
  ],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './asc-import.page.html',
  styleUrl: './byd-import.page.scss',
})
export class AscImportPage {
  private readonly api = inject(AscApi);
  private readonly auth = inject(AuthStore);
  private readonly snackBar = inject(MatSnackBar);

  protected readonly file = signal<File | null>(null);
  protected readonly branchId = signal<number | null>(this.auth.branchId());
  protected readonly result = signal<AscImportResult | null>(null);
  protected readonly busy = signal(false);
  protected readonly rowFilter = signal<RowFilter>('all');

  protected readonly columns = [
    'rowNumber',
    'serialNumber',
    'customer',
    'branch',
    'period',
    'action',
    'messages',
  ];
  protected readonly actionSeverity = ACTION_SEVERITY;

  protected readonly branches = computed(
    () => this.auth.user()?.branches ?? [],
  );
  protected readonly ready = computed(
    () => this.file() !== null && this.branchId() !== null && !this.busy(),
  );
  protected readonly rows = computed(() => {
    const rows = this.result()?.rows ?? [];
    switch (this.rowFilter()) {
      case 'insert':
      case 'update':
      case 'skip':
        return rows.filter((r) => r.action === this.rowFilter());
      case 'new':
        return rows.filter(
          (r) => r.newCustomer || r.newMachine || r.newModel,
        );
      default:
        return rows;
    }
  });

  protected actionLabel(action: string): string {
    return ACTION_LABELS[action] ?? action;
  }

  protected created(row: AscImportRow): string {
    return [
      row.newCustomer ? 'customer' : null,
      row.newMachine ? 'machine' : null,
      row.newModel ? 'model' : null,
    ]
      .filter(Boolean)
      .join(', ');
  }

  protected onFileChange(event: Event): void {
    const input = event.target as HTMLInputElement;
    this.file.set(input.files?.[0] ?? null);
    this.result.set(null);
  }

  protected run(apply: boolean): void {
    const file = this.file();
    const branchId = this.branchId();
    if (!file || branchId === null || this.busy()) return;
    this.busy.set(true);
    const request = apply
      ? this.api.applyImport(file, branchId)
      : this.api.previewImport(file, branchId);
    request
      .pipe(
        finalize(() => this.busy.set(false)),
        catchError(() => EMPTY), // the global interceptor shows the error toast
      )
      .subscribe((result) => {
        this.result.set(result);
        this.rowFilter.set('all');
        if (apply) {
          const s = result.summary;
          this.snackBar.open(
            `Imported: ${s.inserts} new ASC, ${s.updates} updated`,
            'Dismiss',
            { duration: 6000 },
          );
        }
      });
  }
}
