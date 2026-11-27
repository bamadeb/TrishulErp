import { DatePipe } from '@angular/common';
import {
  ChangeDetectionStrategy,
  Component,
  effect,
  inject,
  signal,
  untracked,
} from '@angular/core';
import { toSignal } from '@angular/core/rxjs-interop';
import { MatButton } from '@angular/material/button';
import { MatCheckbox } from '@angular/material/checkbox';
import { MatFormField, MatHint, MatLabel } from '@angular/material/form-field';
import { MatIcon } from '@angular/material/icon';
import { MatInput } from '@angular/material/input';
import { MatPaginator, PageEvent } from '@angular/material/paginator';
import { MatOption, MatSelect } from '@angular/material/select';
import { Router, RouterLink } from '@angular/router';
import {
  ApiClient,
  PageStockCountOut,
  RackOut,
  StorageRackOut,
  listStorageRacks,
} from '@trishul/core-api';
import { AuthStore } from '@trishul/core-auth';
import {
  INV_COUNT_MANAGE,
  InventoryLookups,
  StockCountApi,
  locationLabel,
} from '@trishul/inventory-data-access';
import { PageHeader } from '@trishul/shared-ui';
import { EMPTY, catchError, finalize, of } from 'rxjs';

type Scope = 'Location' | 'Rack' | 'Bins';
type Status = 'Open' | 'Counted' | 'Adjusted' | 'Cancelled';

/** Physical stock counts: start a count of a location, a rack or some bins; see the counts made. */
@Component({
  selector: 'trishul-stock-counts-page',
  imports: [
    DatePipe,
    RouterLink,
    MatButton,
    MatCheckbox,
    MatFormField,
    MatHint,
    MatLabel,
    MatIcon,
    MatInput,
    MatPaginator,
    MatSelect,
    MatOption,
    PageHeader,
  ],
  changeDetection: ChangeDetectionStrategy.OnPush,
  styleUrl: '../../../data-access/src/lib/inventory.scss',
  styles: `
    .bar {
      display: flex;
      flex-wrap: wrap;
      gap: 0.75rem;
      align-items: center;
      margin-bottom: 0.75rem;
    }
    .bar mat-form-field {
      width: 16rem;
    }
    .new-grid {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(14rem, 1fr));
      gap: 0.75rem;
      align-items: start;
      max-width: 64rem;
    }
    .status {
      font-weight: 500;
    }
    .status.Open {
      color: var(--mat-sys-primary);
    }
    .status.Counted {
      color: var(--mat-sys-tertiary);
    }
    .status.Cancelled {
      color: var(--mat-sys-on-surface-variant);
    }
  `,
  template: `
    <trishul-page-header
      title="Physical stock count"
      subtitle="Count a whole location, one rack or a few bins; review the differences and post them"
    />

    @if (canCount) {
      <section class="card">
        <h2>Start a count</h2>
        <div class="new-grid">
          <mat-form-field appearance="outline" subscriptSizing="dynamic">
            <mat-label>Location</mat-label>
            <mat-select
              [value]="locationId()"
              (valueChange)="locationId.set($event)"
            >
              @for (l of locations(); track l.id) {
                <mat-option [value]="l.id">{{ label(l) }}</mat-option>
              }
            </mat-select>
          </mat-form-field>
          <mat-form-field appearance="outline" subscriptSizing="dynamic">
            <mat-label>What to count</mat-label>
            <mat-select [value]="scope()" (valueChange)="scope.set($event)">
              <mat-option value="Location"
                >Everything at the location (full count)</mat-option
              >
              <mat-option value="Rack">One rack (cycle count)</mat-option>
              <mat-option value="Bins">Chosen bins (cycle count)</mat-option>
            </mat-select>
          </mat-form-field>
          @if (scope() === 'Rack') {
            <mat-form-field appearance="outline" subscriptSizing="dynamic">
              <mat-label>Rack</mat-label>
              <mat-select [value]="rackId()" (valueChange)="rackId.set($event)">
                @for (r of racks(); track r.id) {
                  <mat-option [value]="r.id"
                    >{{ r.code }}{{ r.name ? ' · ' + r.name : '' }}</mat-option
                  >
                }
              </mat-select>
              @if (locationId() && !racks().length) {
                <mat-hint>No racks at this location</mat-hint>
              }
            </mat-form-field>
          }
          @if (scope() === 'Bins') {
            <mat-form-field appearance="outline" subscriptSizing="dynamic">
              <mat-label>Bins</mat-label>
              <mat-select
                multiple
                [value]="binIds()"
                (valueChange)="binIds.set($event)"
              >
                @for (b of bins(); track b.id) {
                  <mat-option [value]="b.id">{{ b.code }}</mat-option>
                }
              </mat-select>
              <mat-hint>{{ binIds().length }} chosen</mat-hint>
            </mat-form-field>
          }
          <mat-form-field appearance="outline" subscriptSizing="dynamic">
            <mat-label>Remarks</mat-label>
            <input
              matInput
              maxlength="300"
              [value]="remarks()"
              (input)="remarks.set($any($event.target).value)"
            />
          </mat-form-field>
        </div>
        <p>
          <mat-checkbox [checked]="blind()" (change)="blind.set($event.checked)"
            >Blind count: counters don't see the system quantity until counting
            is finished</mat-checkbox
          >
        </p>
        <button
          mat-flat-button
          type="button"
          [disabled]="!canStart() || busy()"
          (click)="start()"
        >
          <mat-icon>fact_check</mat-icon>Start count
        </button>
      </section>
    }

    <section class="card">
      <div class="bar">
        <mat-form-field appearance="outline" subscriptSizing="dynamic">
          <mat-label>Location</mat-label>
          <mat-select
            [value]="filterLocation()"
            (valueChange)="filterLocation.set($event); page.set(1)"
          >
            <mat-option [value]="null">All</mat-option>
            @for (l of locations(); track l.id) {
              <mat-option [value]="l.id">{{ label(l) }}</mat-option>
            }
          </mat-select>
        </mat-form-field>
        <mat-form-field appearance="outline" subscriptSizing="dynamic">
          <mat-label>Status</mat-label>
          <mat-select
            [value]="filterStatus()"
            (valueChange)="filterStatus.set($event); page.set(1)"
          >
            <mat-option [value]="null">All</mat-option>
            @for (s of statuses; track s) {
              <mat-option [value]="s">{{ s }}</mat-option>
            }
          </mat-select>
        </mat-form-field>
      </div>
      <div class="table-wrap">
        <table class="plain">
          <thead>
            <tr>
              <th>Count</th>
              <th>Date</th>
              <th>Location</th>
              <th>Scope</th>
              <th>Status</th>
              <th class="num">Lines</th>
              <th class="num">Counted</th>
              <th>Adjustment</th>
              <th>Started by</th>
            </tr>
          </thead>
          <tbody>
            @for (c of counts()?.items ?? []; track c.id) {
              <tr>
                <td>
                  <a [routerLink]="[c.id]">{{ c.countNo }}</a>
                </td>
                <td>{{ c.countDate | date: 'dd MMM yyyy' }}</td>
                <td>{{ c.locationCode }}</td>
                <td>
                  {{
                    c.scope === 'Location'
                      ? 'Full'
                      : c.scope === 'Rack'
                        ? 'Rack ' + (c.storageRackCode ?? '')
                        : 'Bins'
                  }}{{ c.isBlind ? ' · blind' : '' }}
                </td>
                <td>
                  <span class="status" [class]="c.status">{{ c.status }}</span>
                </td>
                <td class="num">{{ c.lineCount }}</td>
                <td class="num">{{ c.countedCount }}</td>
                <td>{{ c.adjustmentNo ?? '' }}</td>
                <td>{{ c.createdByName }}</td>
              </tr>
            } @empty {
              <tr>
                <td colspan="9" class="empty">No counts yet.</td>
              </tr>
            }
          </tbody>
        </table>
      </div>
      <mat-paginator
        [length]="counts()?.total ?? 0"
        [pageIndex]="page() - 1"
        [pageSize]="20"
        [hidePageSize]="true"
        (page)="onPage($event)"
      />
    </section>
  `,
})
export class StockCountsPage {
  private readonly api = inject(ApiClient);
  private readonly countsApi = inject(StockCountApi);
  private readonly lookups = inject(InventoryLookups);
  private readonly router = inject(Router);
  protected readonly canCount =
    inject(AuthStore).hasPermission(INV_COUNT_MANAGE);

  protected readonly label = locationLabel;
  protected readonly statuses: Status[] = [
    'Open',
    'Counted',
    'Adjusted',
    'Cancelled',
  ];
  protected readonly locations = toSignal(this.lookups.locations(), {
    initialValue: [],
  });

  // new count
  protected readonly locationId = signal<number | null>(null);
  protected readonly scope = signal<Scope>('Location');
  protected readonly rackId = signal<number | null>(null);
  protected readonly binIds = signal<number[]>([]);
  protected readonly blind = signal(true);
  protected readonly remarks = signal('');
  protected readonly racks = signal<StorageRackOut[]>([]);
  protected readonly bins = signal<RackOut[]>([]);
  protected readonly busy = signal(false);

  // list
  protected readonly filterLocation = signal<number | null>(null);
  protected readonly filterStatus = signal<Status | null>(null);
  protected readonly page = signal(1);
  protected readonly counts = signal<PageStockCountOut | null>(null);

  constructor() {
    effect(() => {
      const id = this.locationId();
      untracked(() => {
        this.rackId.set(null);
        this.binIds.set([]);
        this.racks.set([]);
        this.bins.set([]);
        if (!id) return;
        this.api
          .call(listStorageRacks, { locationId: id, status: 'active' })
          .pipe(catchError(() => of([] as StorageRackOut[])))
          .subscribe((racks) => this.racks.set(racks));
        this.lookups.racks(id).subscribe((bins) => this.bins.set(bins));
      });
    });
    effect(() => {
      const query = {
        page: this.page(),
        pageSize: 20,
        locationId: this.filterLocation(),
        status: this.filterStatus(),
      };
      untracked(() =>
        this.countsApi
          .list(query)
          .pipe(catchError(() => of(null)))
          .subscribe((p) => this.counts.set(p)),
      );
    });
  }

  protected canStart(): boolean {
    if (!this.locationId()) return false;
    if (this.scope() === 'Rack') return !!this.rackId();
    if (this.scope() === 'Bins') return this.binIds().length > 0;
    return true;
  }

  protected start(): void {
    const locationId = this.locationId();
    if (!locationId || !this.canStart()) return;
    this.busy.set(true);
    this.countsApi
      .create({
        locationId,
        scope: this.scope(),
        storageRackId: this.scope() === 'Rack' ? this.rackId() : null,
        binIds: this.scope() === 'Bins' ? this.binIds() : [],
        isBlind: this.blind(),
        remarks: this.remarks().trim() || null,
      })
      .pipe(
        finalize(() => this.busy.set(false)),
        catchError(() => EMPTY),
      )
      .subscribe(
        (count) =>
          void this.router.navigate(['/inventory/stock-counts', count.id]),
      );
  }

  protected onPage(event: PageEvent): void {
    this.page.set(event.pageIndex + 1);
  }
}
