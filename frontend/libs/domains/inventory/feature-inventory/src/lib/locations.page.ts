import {
  ChangeDetectionStrategy,
  Component,
  computed,
  inject,
  signal,
} from '@angular/core';
import { toSignal } from '@angular/core/rxjs-interop';
import { MatButton, MatIconButton } from '@angular/material/button';
import { MatDialog } from '@angular/material/dialog';
import { MatFormField, MatLabel } from '@angular/material/form-field';
import { MatIcon } from '@angular/material/icon';
import { MatOption, MatSelect } from '@angular/material/select';
import { MatTooltip } from '@angular/material/tooltip';
import {
  ApiClient,
  LocationCreate,
  LocationOut,
  LocationUpdate,
  createLocation,
  listLocations,
  updateLocation,
  withRowVersion,
} from '@trishul/core-api';
import { AuthStore } from '@trishul/core-auth';
import { PageHeader } from '@trishul/shared-ui';
import { EMPTY, catchError, filter } from 'rxjs';
import { openFieldsDialog } from '@trishul/inventory-data-access';
import { INV_LOCATION_MANAGE } from '@trishul/inventory-data-access';
import { InventoryLookups } from '@trishul/inventory-data-access';
import { StoragePanel } from './storage-panel';

type LocationLocationType = NonNullable<LocationCreate['locationType']>;

const LOCATION_TYPES: LocationLocationType[] = [
  'Main store',
  'Receiving',
  'Open area',
  'Transit',
  'Quarantine',
  'Scrap',
];
const CODE = '^[A-Za-z0-9][A-Za-z0-9_./-]*$';

/** Stock locations under branches and warehouses, and the racks inside each. */
@Component({
  selector: 'trishul-locations-page',
  imports: [
    MatButton,
    MatIconButton,
    MatIcon,
    MatTooltip,
    MatFormField,
    MatLabel,
    MatSelect,
    MatOption,
    PageHeader,
    StoragePanel,
  ],
  changeDetection: ChangeDetectionStrategy.OnPush,
  styleUrl: '../../../data-access/src/lib/inventory.scss',
  styles: `
    .panes {
      display: grid;
      grid-template-columns: minmax(0, 3fr) minmax(0, 2fr);
      gap: 1rem;
      align-items: start;
    }
    h2 {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 0.5rem;
    }
    tr.selected {
      background: color-mix(in srgb, var(--mat-sys-primary) 10%, transparent);
    }
    tbody tr {
      cursor: pointer;
    }
    @media (max-width: 900px) {
      .panes {
        grid-template-columns: 1fr;
      }
    }
  `,
  template: `
    <trishul-page-header
      title="Storage locations"
      subtitle="Where stock is kept: locations, their racks and bins, and yard spots. Racks and bins are optional everywhere."
    >
      @if (canManage) {
        <button mat-flat-button (click)="editLocation(null)">
          <mat-icon>add</mat-icon>Add location
        </button>
      }
    </trishul-page-header>

    <div class="filters">
      <mat-form-field appearance="outline" subscriptSizing="dynamic">
        <mat-label>Branch / warehouse</mat-label>
        <mat-select [value]="branchId()" (valueChange)="branchId.set($event)">
          <mat-option [value]="null">All</mat-option>
          @for (b of branches(); track b.id) {
            <mat-option [value]="b.id"
              >{{ b.name }} ({{ b.branchType }})</mat-option
            >
          }
        </mat-select>
      </mat-form-field>
    </div>

    <div class="panes">
      <section class="card">
        <h2>Locations</h2>
        <table class="plain">
          <thead>
            <tr>
              <th>Branch</th>
              <th>Code</th>
              <th>Name</th>
              <th>Type</th>
              <th class="num">Racks</th>
              <th class="num">Bins</th>
              <th>Status</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            @for (l of shown(); track l.id) {
              <tr
                [class.selected]="l.id === selected()?.id"
                (click)="select(l)"
              >
                <td>
                  {{ l.branchName }}
                  <div class="muted">{{ l.branchType }}</div>
                </td>
                <td>{{ l.code }}</td>
                <td>
                  {{ l.name }}
                  @if (!l.isStockLocation) {
                    <div class="muted">Holds no stock</div>
                  }
                </td>
                <td>
                  {{ l.locationType }}
                  @if (l.requiresBin) {
                    <div class="muted">Bin required</div>
                  }
                </td>
                <td class="num">{{ l.storageRackCount }}</td>
                <td class="num">{{ l.rackCount }}</td>
                <td>{{ l.isActive ? 'Active' : 'Inactive' }}</td>
                <td class="actions">
                  @if (canManage) {
                    <button
                      mat-icon-button
                      matTooltip="Change"
                      (click)="$event.stopPropagation(); editLocation(l)"
                    >
                      <mat-icon>edit</mat-icon>
                    </button>
                  }
                </td>
              </tr>
            } @empty {
              <tr>
                <td colspan="8" class="empty">
                  No locations yet. Add one for each store in a branch or
                  warehouse.
                </td>
              </tr>
            }
          </tbody>
        </table>
      </section>

      <section class="card">
        @if (selected(); as l) {
          <trishul-storage-panel
            [location]="l"
            [canManage]="canManage"
            (changed)="changed()"
          />
        } @else {
          <p class="empty">
            Choose a location to see its racks, bins and spots.
          </p>
        }
      </section>
    </div>
  `,
})
export class LocationsPage {
  private readonly api = inject(ApiClient);
  private readonly dialog = inject(MatDialog);
  private readonly lookups = inject(InventoryLookups);
  protected readonly canManage =
    inject(AuthStore).hasPermission(INV_LOCATION_MANAGE);

  protected readonly branches = toSignal(this.lookups.branches(), {
    initialValue: [],
  });
  protected readonly branchId = signal<number | null>(null);
  protected readonly locations = signal<LocationOut[]>([]);
  protected readonly selected = signal<LocationOut | null>(null);
  protected readonly shown = computed(() => {
    const branch = this.branchId();
    return this.locations().filter(
      (l) => branch === null || l.branchId === branch,
    );
  });

  constructor() {
    this.load();
  }

  private load(): void {
    this.api
      .call(listLocations, { status: 'all' })
      .pipe(catchError(() => EMPTY))
      .subscribe((rows) => {
        this.locations.set(rows);
        const current = this.selected();
        if (current)
          this.selected.set(rows.find((l) => l.id === current.id) ?? null);
      });
  }

  protected select(location: LocationOut): void {
    this.selected.set(location);
  }

  protected changed(): void {
    this.lookups.reset();
    this.load();
  }

  protected editLocation(location: LocationOut | null): void {
    const branches = this.branches().map((b) => ({
      value: b.id,
      label: `${b.name} (${b.branchType})`,
    }));
    openFieldsDialog(this.dialog, {
      title: location ? `Change ${location.code}` : 'Add location',
      submitText: location ? 'Save' : 'Add',
      fields: [
        ...(location
          ? []
          : [
              {
                key: 'branchId',
                label: 'Branch / warehouse',
                type: 'select' as const,
                required: true,
                options: branches,
                wide: true,
              },
              {
                key: 'code',
                label: 'Code',
                required: true,
                maxLength: 10,
                pattern: CODE,
                hint: 'Unique, e.g. BBSR-MAIN',
              },
            ]),
        { key: 'name', label: 'Name', required: true, maxLength: 120 },
        {
          key: 'locationType',
          label: 'Type',
          type: 'select' as const,
          required: true,
          options: LOCATION_TYPES.map((t) => ({ value: t, label: t })),
        },
        { key: 'address', label: 'Address', type: 'textarea' as const },
        {
          key: 'isStockLocation',
          label: 'Holds stock',
          type: 'checkbox' as const,
        },
        {
          key: 'requiresBin',
          label: 'Every movement needs a bin',
          type: 'checkbox' as const,
        },
        ...(location
          ? [{ key: 'isActive', label: 'Active', type: 'checkbox' as const }]
          : []),
      ],
      value: location
        ? { ...location }
        : {
            branchId: this.branchId(),
            locationType: 'Main store',
            isStockLocation: true,
          },
      save: (v) =>
        location
          ? this.api.call(
              updateLocation,
              { locationId: location.id, body: v as LocationUpdate },
              withRowVersion(location.rowVersion),
            )
          : this.api.call(createLocation, {
              body: v as unknown as LocationCreate,
            }),
    })
      .pipe(filter((saved) => !!saved))
      .subscribe(() => this.changed());
  }
}
