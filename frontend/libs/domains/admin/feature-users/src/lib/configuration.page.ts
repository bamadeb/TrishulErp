import {
  ChangeDetectionStrategy,
  Component,
  inject,
  signal,
} from '@angular/core';
import { MatButton } from '@angular/material/button';
import { MatFormField, MatHint } from '@angular/material/form-field';
import { MatInput } from '@angular/material/input';
import { MatProgressBar } from '@angular/material/progress-bar';
import { MatSlideToggle } from '@angular/material/slide-toggle';
import { MatSnackBar } from '@angular/material/snack-bar';
import { MatTableModule } from '@angular/material/table';
import { MatTab, MatTabGroup } from '@angular/material/tabs';
import {
  BRAND_MANAGE_PERMISSION,
  BrandApi,
  BrandItem,
  TRACKING_CONFIG_PERMISSION,
  TrackingConfigApi,
  TrackingConfigParameter,
} from '@trishul/admin-data-access';
import { AuthStore } from '@trishul/core-auth';
import { PageHeader, StatusBadge, StatusSeverity } from '@trishul/shared-ui';

/**
 * Administration > Configuration: settings that change how the app behaves. Which brands need the full
 * inspection service report, and the trip-tracking parameters the mobile app fetches.
 */
@Component({
  selector: 'trishul-configuration-page',
  imports: [
    MatButton,
    MatFormField,
    MatHint,
    MatInput,
    MatProgressBar,
    MatSlideToggle,
    MatTab,
    MatTabGroup,
    MatTableModule,
    PageHeader,
    StatusBadge,
  ],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './configuration.page.html',
  styleUrl: './configuration.page.scss',
})
export class ConfigurationPage {
  private readonly brandApi = inject(BrandApi);
  private readonly trackingApi = inject(TrackingConfigApi);
  private readonly snackBar = inject(MatSnackBar);
  private readonly auth = inject(AuthStore);

  protected readonly canBrands = this.auth.hasPermission(
    BRAND_MANAGE_PERMISSION,
  );
  protected readonly canTracking = this.auth.hasPermission(
    TRACKING_CONFIG_PERMISSION,
  );

  protected readonly brands = signal<BrandItem[]>([]);
  protected readonly parameters = signal<TrackingConfigParameter[]>([]);
  protected readonly loadingBrands = signal(false);
  protected readonly loadingParameters = signal(false);
  /** Text typed in a parameter's box but not saved yet, by parameter code. */
  protected readonly drafts = signal<Record<string, string>>({});
  protected readonly saving = signal<string | null>(null);

  protected readonly brandColumns = ['brand', 'required'];
  protected readonly parameterColumns = ['name', 'value', 'status', 'actions'];
  protected readonly calibrationSeverity: Record<string, StatusSeverity> = {
    Calibrated: 'success',
    'To be calibrated': 'warn',
  };

  constructor() {
    if (this.canBrands) this.loadBrands();
    if (this.canTracking) this.loadParameters();
  }

  // ------------------------------------------------------------------ inspection report by brand

  protected setRequired(brand: BrandItem, required: boolean): void {
    this.brandApi
      .update(brand, { inspectionReportRequired: required })
      .subscribe({
        next: (saved) => {
          this.brands.update((list) =>
            list.map((b) => (b.id === saved.id ? saved : b)),
          );
          this.snackBar.open(
            `${saved.name}: inspection report ${required ? 'required' : 'not required'}`,
            'OK',
            { duration: 3000 },
          );
        },
        // The global interceptor shows the error; draw the toggles from the saved state again.
        error: () => this.brands.update((list) => [...list]),
      });
  }

  // ------------------------------------------------------------------ tracking parameters

  protected shown(parameter: TrackingConfigParameter): string {
    return this.drafts()[parameter.code] ?? parameter.value ?? '';
  }

  protected dirty(parameter: TrackingConfigParameter): boolean {
    const draft = this.drafts()[parameter.code];
    return draft !== undefined && draft !== (parameter.value ?? '');
  }

  protected edit(parameter: TrackingConfigParameter, text: string): void {
    this.drafts.update((d) => ({ ...d, [parameter.code]: text }));
  }

  /** "0 to 100 ms": the limits and unit the server enforces, as a hint under the box. */
  protected range(parameter: TrackingConfigParameter): string {
    const { minValue: min, maxValue: max, unit } = parameter;
    let limits = '';
    if (min !== null && max !== null) limits = `${min} to ${max}`;
    else if (min !== null) limits = `at least ${min}`;
    else if (max !== null) limits = `at most ${max}`;
    return [limits, unit].filter(Boolean).join(' ');
  }

  protected save(parameter: TrackingConfigParameter): void {
    const text = (this.drafts()[parameter.code] ?? '').trim();
    let value: number | string | null;
    if (text === '') {
      value = null;
    } else if (parameter.valueType === 'string') {
      value = text;
    } else {
      value = Number(text);
      if (Number.isNaN(value)) {
        this.snackBar.open('Enter a number.', 'OK', { duration: 4000 });
        return;
      }
    }
    this.saving.set(parameter.code);
    this.trackingApi.update(parameter, value).subscribe({
      next: (saved) => {
        this.parameters.update((list) =>
          list.map((p) => (p.code === saved.code ? saved : p)),
        );
        this.drafts.update((d) => {
          const rest = { ...d };
          delete rest[parameter.code];
          return rest;
        });
        this.saving.set(null);
        this.snackBar.open(`${saved.name} saved`, 'OK', { duration: 3000 });
      },
      // The global interceptor shows the server's message (out of range, stale version ...).
      error: () => this.saving.set(null),
    });
  }

  private loadBrands(): void {
    this.loadingBrands.set(true);
    this.brandApi.list().subscribe({
      next: (brands) => {
        this.brands.set(brands.filter((b) => b.isActive));
        this.loadingBrands.set(false);
      },
      error: () => this.loadingBrands.set(false),
    });
  }

  private loadParameters(): void {
    this.loadingParameters.set(true);
    this.trackingApi.list().subscribe({
      next: (parameters) => {
        this.parameters.set(parameters);
        this.loadingParameters.set(false);
      },
      error: () => this.loadingParameters.set(false),
    });
  }
}
