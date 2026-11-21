import { DatePipe } from '@angular/common';
import { ChangeDetectionStrategy, Component, inject, OnInit, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { MatButton } from '@angular/material/button';
import { MatFormField, MatLabel } from '@angular/material/form-field';
import { MatIcon } from '@angular/material/icon';
import { MatPaginator, PageEvent } from '@angular/material/paginator';
import { MatProgressBar } from '@angular/material/progress-bar';
import { MatOption, MatSelect } from '@angular/material/select';
import { MatSnackBar } from '@angular/material/snack-bar';
import {
  BiometricApi,
  BiometricSyncLog,
  BiometricSyncStatus,
  BiometricSyncTrigger,
} from '@trishul/hr-data-access';
import { StatusBadge, StatusSeverity } from '@trishul/shared-ui';

@Component({
  selector: 'trishul-biometric-sync-page',
  imports: [
    DatePipe,
    FormsModule,
    MatButton,
    MatFormField,
    MatIcon,
    MatLabel,
    MatOption,
    MatPaginator,
    MatProgressBar,
    MatSelect,
    StatusBadge,
  ],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './biometric-sync.page.html',
  styleUrl: './biometric.shared.scss',
})
export class BiometricSyncPage implements OnInit {
  private readonly api = inject(BiometricApi);
  private readonly snackBar = inject(MatSnackBar);

  protected readonly severities: Partial<Record<string, StatusSeverity>> = {
    Success: 'success',
    Failed: 'danger',
    Skipped: 'warn',
    Running: 'info',
    Pending: 'info',
  };
  protected readonly loading = signal(true);
  protected readonly error = signal<string | null>(null);
  protected readonly rows = signal<BiometricSyncLog[]>([]);
  protected readonly total = signal(0);
  protected readonly status = signal<BiometricSyncStatus | ''>('');
  protected readonly syncType = signal<BiometricSyncTrigger | ''>('');
  protected readonly page = signal(0);
  protected readonly pageSize = signal(20);

  ngOnInit(): void {
    this.reload();
  }

  protected onPage(event: PageEvent): void {
    this.page.set(event.pageIndex);
    this.pageSize.set(event.pageSize);
    this.reload();
  }

  protected applyFilters(): void {
    this.page.set(0);
    this.reload();
  }

  protected runManualSync(): void {
    this.api.runSync().subscribe({
      next: () => {
        this.snackBar.open('Synchronization completed.', 'OK', { duration: 3000 });
        this.reload();
      },
      error: (err) => {
        const detail = err?.error?.detail;
        this.snackBar.open(
          typeof detail === 'string'
            ? detail
            : 'Biometric synchronization is unavailable until device connectivity is configured.',
          'OK',
          { duration: 5000 },
        );
        this.reload();
      },
    });
  }

  private reload(): void {
    this.loading.set(true);
    this.error.set(null);
    this.api
      .listSyncLogs({
        page: this.page() + 1,
        pageSize: this.pageSize(),
        status: this.status() || undefined,
        trigger: this.syncType() || undefined,
      })
      .subscribe({
        next: (page) => {
          this.rows.set(page.items);
          this.total.set(page.total);
          this.loading.set(false);
        },
        error: () => {
          this.error.set('Sync history could not be loaded.');
          this.rows.set([]);
          this.total.set(0);
          this.loading.set(false);
        },
      });
  }
}
