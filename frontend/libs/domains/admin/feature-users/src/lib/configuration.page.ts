import {
  ChangeDetectionStrategy,
  Component,
  computed,
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
  PRICE_APPROVE_PERMISSION,
  PriceSettings,
  PriceSettingsApi,
  SERVICE_CONFIG_PERMISSION,
  ServiceSettingsApi,
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
  private readonly serviceApi = inject(ServiceSettingsApi);
  private readonly trackingApi = inject(TrackingConfigApi);
  private readonly priceApi = inject(PriceSettingsApi);
  private readonly snackBar = inject(MatSnackBar);
  private readonly auth = inject(AuthStore);

  protected readonly canBrands = this.auth.hasPermission(
    BRAND_MANAGE_PERMISSION,
  );
  protected readonly canTracking = this.auth.hasPermission(
    TRACKING_CONFIG_PERMISSION,
  );

  protected readonly canService = this.auth.hasPermission(
    SERVICE_CONFIG_PERMISSION,
  );
  protected readonly canPrices = this.auth.hasPermission(
    PRICE_APPROVE_PERMISSION,
  );
  /** Price change limit as saved (with its row version), and what is typed in the box. */
  protected readonly priceSettings = signal<PriceSettings | null>(null);
  protected readonly priceLimitDraft = signal('');
  protected readonly savingPrices = signal(false);
  /** Pending-call limit as saved, and what is typed in the box. */
  protected readonly maxPending = signal<number | null>(null);
  protected readonly maxPendingDraft = signal('');
  protected readonly savingService = signal(false);

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
    if (this.canService) this.loadServiceSettings();
    if (this.canPrices) this.loadPriceSettings();
  }

  // ------------------------------------------------------------------ price change limit

  protected readonly priceLimitDirty = computed(() => {
    const text = this.priceLimitDraft().trim();
    const saved = this.priceSettings();
    return (
      text !== '' &&
      saved !== null &&
      Number(text) !== Number(saved.maxChangePct)
    );
  });

  protected savePriceLimit(): void {
    const current = this.priceSettings();
    const value = Number(this.priceLimitDraft().trim());
    if (current === null) return;
    if (Number.isNaN(value) || value < 0 || value > 1000) {
      this.snackBar.open('Enter a percentage from 0 to 1000.', 'OK', {
        duration: 4000,
      });
      return;
    }
    this.savingPrices.set(true);
    this.priceApi.update(current, value).subscribe({
      next: (saved) => {
        this.priceSettings.set(saved);
        this.priceLimitDraft.set(String(Number(saved.maxChangePct)));
        this.savingPrices.set(false);
        this.snackBar.open('Price change limit saved', 'OK', {
          duration: 3000,
        });
      },
      // The global interceptor shows the error (e.g. someone changed it meanwhile): load it again.
      error: () => {
        this.savingPrices.set(false);
        this.loadPriceSettings();
      },
    });
  }

  private loadPriceSettings(): void {
    this.priceApi.get().subscribe((s) => {
      this.priceSettings.set(s);
      this.priceLimitDraft.set(String(Number(s.maxChangePct)));
    });
  }

  // ------------------------------------------------------------------ service settings

  protected readonly maxPendingDirty = computed(() => {
    const text = this.maxPendingDraft().trim();
    return text !== '' && Number(text) !== this.maxPending();
  });

  protected saveMaxPending(): void {
    const value = Number(this.maxPendingDraft().trim());
    if (!Number.isInteger(value) || value < 0 || value > 100) {
      this.snackBar.open('Enter a whole number from 0 to 100.', 'OK', {
        duration: 4000,
      });
      return;
    }
    this.savingService.set(true);
    this.serviceApi.update(value).subscribe({
      next: (saved) => {
        this.maxPending.set(saved.maxPendingCalls);
        this.maxPendingDraft.set(String(saved.maxPendingCalls));
        this.savingService.set(false);
        this.snackBar.open('Pending-call limit saved', 'OK', {
          duration: 3000,
        });
      },
      error: () => this.savingService.set(false),
    });
  }

  private loadServiceSettings(): void {
    this.serviceApi.get().subscribe((s) => {
      this.maxPending.set(s.maxPendingCalls);
      this.maxPendingDraft.set(String(s.maxPendingCalls));
    });
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
