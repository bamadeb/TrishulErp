import { ChangeDetectionStrategy, Component, inject } from '@angular/core';
import { MatButton } from '@angular/material/button';
import { MatIcon } from '@angular/material/icon';
import { MatSnackBar } from '@angular/material/snack-bar';
import { RouterLink, RouterLinkActive, RouterOutlet } from '@angular/router';
import { BiometricApi } from '@trishul/hr-data-access';
import { PageHeader } from '@trishul/shared-ui';

const TABS = [
  { label: 'Biometric Dashboard', icon: 'fingerprint', route: 'dashboard' },
  { label: 'Devices', icon: 'smartphone', route: 'devices' },
  { label: 'Employee Mapping', icon: 'group', route: 'mapping' },
  { label: 'Punch Logs', icon: 'format_list_bulleted', route: 'punches' },
  { label: 'Sync History', icon: 'sync', route: 'sync-history' },
] as const;

@Component({
  selector: 'trishul-biometric-shell-page',
  imports: [MatButton, MatIcon, PageHeader, RouterLink, RouterLinkActive, RouterOutlet],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './biometric-shell.page.html',
  styleUrl: './biometric.shared.scss',
})
export class BiometricShellPage {
  private readonly api = inject(BiometricApi);
  private readonly snackBar = inject(MatSnackBar);
  protected readonly tabs = TABS;
  protected readonly todayLabel = new Date().toLocaleDateString('en-GB', {
    weekday: 'long',
    day: 'numeric',
    month: 'short',
    year: 'numeric',
  });

  protected syncNow(): void {
    this.api.runSync().subscribe({
      next: () => this.snackBar.open('Synchronization completed.', 'OK', { duration: 3000 }),
      error: (err) => {
        const detail = err?.error?.detail;
        this.snackBar.open(
          typeof detail === 'string'
            ? detail
            : 'Biometric synchronization is unavailable until device connectivity is configured.',
          'OK',
          { duration: 5000 },
        );
      },
    });
  }
}
