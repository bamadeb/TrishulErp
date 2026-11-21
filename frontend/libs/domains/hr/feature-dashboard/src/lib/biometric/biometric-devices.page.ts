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
import {
  BiometricApi,
  BiometricDevice,
  BiometricDeviceStatus,
} from '@trishul/hr-data-access';
import { StatusBadge, StatusSeverity } from '@trishul/shared-ui';
import { BiometricDeviceDialog, BiometricDeviceDialogData } from './biometric-device.dialog';

@Component({
  selector: 'trishul-biometric-devices-page',
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
    StatusBadge,
  ],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './biometric-devices.page.html',
  styleUrl: './biometric.shared.scss',
})
export class BiometricDevicesPage implements OnInit {
  private readonly api = inject(BiometricApi);
  private readonly dialog = inject(MatDialog);
  private readonly snackBar = inject(MatSnackBar);

  protected readonly severities: Partial<Record<string, StatusSeverity>> = {
    Online: 'success',
    Offline: 'neutral',
    Maintenance: 'warn',
  };
  protected readonly loading = signal(true);
  protected readonly error = signal<string | null>(null);
  protected readonly rows = signal<BiometricDevice[]>([]);
  protected readonly search = signal('');
  protected readonly status = signal<BiometricDeviceStatus | ''>('');
  protected readonly page = signal(0);
  protected readonly pageSize = signal(8);

  protected readonly filtered = computed(() => {
    const q = this.search().trim().toLowerCase();
    const status = this.status();
    return this.rows().filter((row) => {
      if (status && row.status !== status) return false;
      if (!q) return true;
      return [row.name, row.code, row.serialNumber, row.locationName, row.baseUrl, row.vendor]
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

  protected openEdit(row: BiometricDevice): void {
    this.openDialog(row);
  }

  private openDialog(row?: BiometricDevice): void {
    const data: BiometricDeviceDialogData = { row };
    this.dialog
      .open(BiometricDeviceDialog, { width: '32rem', data })
      .afterClosed()
      .subscribe((saved: boolean | undefined) => {
        if (!saved) return;
        this.snackBar.open(row ? 'Device updated.' : 'Device registered.', 'OK', { duration: 3000 });
        this.reload();
      });
  }

  private reload(): void {
    this.loading.set(true);
    this.error.set(null);
    this.api.listDevices().subscribe({
      next: (rows) => {
        this.rows.set(rows);
        this.loading.set(false);
      },
      error: () => {
        this.error.set('Biometric devices could not be loaded.');
        this.rows.set([]);
        this.loading.set(false);
      },
    });
  }
}
