import { DatePipe, DecimalPipe } from '@angular/common';
import { ChangeDetectionStrategy, Component, computed, inject, OnInit, signal } from '@angular/core';
import { MatIcon } from '@angular/material/icon';
import { MatProgressBar } from '@angular/material/progress-bar';
import { MatSnackBar } from '@angular/material/snack-bar';
import { RouterLink } from '@angular/router';
import {
  BiometricApi,
  BiometricDashboard,
  BiometricPunchTrendPoint,
} from '@trishul/hr-data-access';
import { StatusBadge, StatusSeverity } from '@trishul/shared-ui';

@Component({
  selector: 'trishul-biometric-dashboard-page',
  imports: [DatePipe, DecimalPipe, MatIcon, MatProgressBar, RouterLink, StatusBadge],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './biometric-dashboard.page.html',
  styleUrl: './biometric-dashboard.page.scss',
})
export class BiometricDashboardPage implements OnInit {
  private readonly api = inject(BiometricApi);
  private readonly snackBar = inject(MatSnackBar);

  protected readonly loading = signal(true);
  protected readonly error = signal<string | null>(null);
  protected readonly data = signal<BiometricDashboard | null>(null);

  protected readonly padX = 28;
  protected readonly padY = 16;
  protected readonly chartWidth = 560;
  protected readonly chartHeight = 150;
  protected readonly gridYs = [16, 50, 84, 118, 150];

  protected readonly severities: Partial<Record<string, StatusSeverity>> = {
    IN: 'success',
    OUT: 'danger',
    Success: 'success',
    Failed: 'danger',
    Skipped: 'warn',
    Running: 'info',
    Pending: 'info',
    Online: 'success',
    Offline: 'neutral',
    Maintenance: 'warn',
  };

  protected readonly slices = computed(() => {
    const status = this.data()?.deviceStatus;
    if (!status) return [];
    const total = status.online + status.offline + status.maintenance || 1;
    const circumference = 2 * Math.PI * 42;
    const parts = [
      { label: 'Online', count: status.online, color: '#15803d' },
      { label: 'Offline', count: status.offline, color: '#94a3b8' },
      { label: 'Maintenance', count: status.maintenance, color: '#c2410c' },
    ];
    let cursor = 0;
    return parts.map((part) => {
      const length = (part.count / total) * circumference;
      const slice = {
        ...part,
        dash: `${length} ${circumference - length}`,
        offset: String(-cursor),
      };
      cursor += length;
      return slice;
    });
  });

  protected readonly checkInLine = computed(() => this.trendPolyline((point) => point.checkIn));
  protected readonly checkOutLine = computed(() => this.trendPolyline((point) => point.checkOut));

  ngOnInit(): void {
    this.reload();
  }

  protected labelX(index: number): number {
    const trend = this.data()?.punchTrend ?? [];
    const count = Math.max(trend.length - 1, 1);
    return this.padX + (index / count) * (this.chartWidth - this.padX * 2);
  }

  protected lastSyncLabel(iso: string | null | undefined): string {
    if (!iso) return '—';
    return new Date(iso).toLocaleTimeString('en-IN', { hour: 'numeric', minute: '2-digit' });
  }

  protected initials(name: string | null | undefined): string {
    return (name ?? '')
      .split(/\s+/)
      .filter(Boolean)
      .slice(0, 2)
      .map((part) => part[0]?.toUpperCase() ?? '')
      .join('');
  }

  protected syncPunchData(): void {
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
    this.api.dashboard().subscribe({
      next: (board) => {
        this.data.set(board);
        this.loading.set(false);
      },
      error: () => {
        this.error.set('Biometric dashboard could not be loaded.');
        this.data.set(null);
        this.loading.set(false);
      },
    });
  }

  private trendPolyline(pick: (point: BiometricPunchTrendPoint) => number): string {
    const trend = this.data()?.punchTrend ?? [];
    if (!trend.length) return '';
    const max = Math.max(...trend.map((point) => Math.max(point.checkIn, point.checkOut)), 1);
    return trend
      .map((point, index) => {
        const x =
          this.padX + (index / Math.max(trend.length - 1, 1)) * (this.chartWidth - this.padX * 2);
        const y =
          this.chartHeight -
          this.padY -
          (pick(point) / max) * (this.chartHeight - this.padY * 2);
        return `${x.toFixed(1)},${y.toFixed(1)}`;
      })
      .join(' ');
  }
}
