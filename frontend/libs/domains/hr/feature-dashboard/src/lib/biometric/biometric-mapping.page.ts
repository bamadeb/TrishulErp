import { DatePipe } from '@angular/common';
import { ChangeDetectionStrategy, Component, computed, inject, OnInit, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { MatButton, MatIconButton } from '@angular/material/button';
import { MatDialog } from '@angular/material/dialog';
import { MatFormField, MatLabel, MatPrefix } from '@angular/material/form-field';
import { MatIcon } from '@angular/material/icon';
import { MatInput } from '@angular/material/input';
import { MatPaginator, PageEvent } from '@angular/material/paginator';
import { MatProgressBar } from '@angular/material/progress-bar';
import { MatOption, MatSelect } from '@angular/material/select';
import { MatSnackBar } from '@angular/material/snack-bar';
import { BiometricApi, BiometricDevice, BiometricMapping } from '@trishul/hr-data-access';
import { BiometricMappingDialog, BiometricMappingDialogData } from './biometric-mapping.dialog';

@Component({
  selector: 'trishul-biometric-mapping-page',
  imports: [
    DatePipe,
    FormsModule,
    MatButton,
    MatFormField,
    MatIcon,
    MatIconButton,
    MatInput,
    MatLabel,
    MatOption,
    MatPaginator,
    MatPrefix,
    MatProgressBar,
    MatSelect,
  ],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './biometric-mapping.page.html',
  styleUrl: './biometric.shared.scss',
})
export class BiometricMappingPage implements OnInit {
  private readonly api = inject(BiometricApi);
  private readonly dialog = inject(MatDialog);
  private readonly snackBar = inject(MatSnackBar);

  protected readonly loading = signal(true);
  protected readonly error = signal<string | null>(null);
  protected readonly rows = signal<BiometricMapping[]>([]);
  protected readonly devices = signal<BiometricDevice[]>([]);
  protected readonly search = signal('');
  protected readonly department = signal('');
  protected readonly location = signal('');
  protected readonly page = signal(0);
  protected readonly pageSize = signal(8);

  protected readonly departments = computed(() =>
    [...new Set(this.rows().map((row) => row.departmentName).filter(Boolean) as string[])].sort(),
  );
  protected readonly locations = computed(() =>
    [...new Set(this.rows().map((row) => row.branchName).filter(Boolean) as string[])].sort(),
  );

  protected readonly filtered = computed(() => {
    const q = this.search().trim().toLowerCase();
    const department = this.department();
    const location = this.location();
    return this.rows().filter((row) => {
      if (department && row.departmentName !== department) return false;
      if (location && row.branchName !== location) return false;
      if (!q) return true;
      return [row.employeeCode, row.employeeName, row.biometricUserId, row.deviceName]
        .filter(Boolean)
        .join(' ')
        .toLowerCase()
        .includes(q);
    });
  });

  protected readonly pageRows = computed(() => {
    const start = this.page() * this.pageSize();
    return this.filtered().slice(start, start + this.pageSize());
  });

  ngOnInit(): void {
    this.reload();
  }

  protected onPage(event: PageEvent): void {
    this.page.set(event.pageIndex);
    this.pageSize.set(event.pageSize);
  }

  protected openCreate(): void {
    this.openDialog();
  }

  protected openEdit(row: BiometricMapping): void {
    this.openDialog(row);
  }

  protected unmap(row: BiometricMapping): void {
    this.api.deactivateMapping(row.id).subscribe({
      next: () => {
        this.snackBar.open('Employee unmapped.', 'OK', { duration: 3000 });
        this.reload();
      },
      error: (err) => {
        this.snackBar.open(err?.error?.detail || 'Mapping could not be removed.', 'OK', {
          duration: 4000,
        });
      },
    });
  }

  protected bulkUpload(): void {
    this.snackBar.open('Bulk upload is not available yet.', 'OK', { duration: 3500 });
  }

  private openDialog(row?: BiometricMapping): void {
    const data: BiometricMappingDialogData = { row, devices: this.devices() };
    this.dialog
      .open(BiometricMappingDialog, { width: '32rem', data })
      .afterClosed()
      .subscribe((saved: boolean | undefined) => {
        if (!saved) return;
        this.snackBar.open(row ? 'Mapping updated.' : 'Mapping created.', 'OK', { duration: 3000 });
        this.reload();
      });
  }

  private reload(): void {
    this.loading.set(true);
    this.error.set(null);
    this.api.listDevices().subscribe({
      next: (devices) => this.devices.set(devices),
      error: () => this.devices.set([]),
    });
    this.api.listMappings().subscribe({
      next: (rows) => {
        this.rows.set(rows);
        this.loading.set(false);
      },
      error: () => {
        this.error.set('Employee mappings could not be loaded.');
        this.rows.set([]);
        this.loading.set(false);
      },
    });
  }
}
