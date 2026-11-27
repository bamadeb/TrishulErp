import {
  ChangeDetectionStrategy,
  Component,
  computed,
  effect,
  inject,
  input,
  output,
  signal,
  untracked,
} from '@angular/core';
import { DecimalPipe } from '@angular/common';
import { MatButton, MatIconButton } from '@angular/material/button';
import { MatDialog } from '@angular/material/dialog';
import { MatIcon } from '@angular/material/icon';
import { MatTooltip } from '@angular/material/tooltip';
import { RouterLink } from '@angular/router';
import {
  ApiClient,
  LocationOut,
  RackCreate,
  RackOut,
  RackUpdate,
  StorageRackCreate,
  StorageRackOut,
  StorageRackUpdate,
  createRack,
  createStorageRack,
  listRacks,
  listStorageRacks,
  updateRack,
  updateStorageRack,
  withRowVersion,
} from '@trishul/core-api';
import { EMPTY, catchError, filter } from 'rxjs';
import { BarcodeApi, openFieldsDialog } from '@trishul/inventory-data-access';

const CODE = '^[A-Za-z0-9][A-Za-z0-9_./-]*$';
const RACK_TYPES = ['Rack', 'Shelf', 'Bin cabinet', 'Floor'];
const BIN_TYPES = [
  { value: 'Mixed', label: 'Mixed – several items' },
  { value: 'Single item', label: 'Single item – one item only' },
  { value: 'Shared', label: 'Shared – one compartment per item' },
  { value: 'Area spot', label: 'Area spot – open area / yard' },
];

/**
 * What a location holds: its racks (levels x positions of generated bins, shown as a grid) and its loose bins
 * and yard spots (bins with no rack). Stock may also be kept at the location itself, without any bin.
 */
@Component({
  selector: 'trishul-storage-panel',
  imports: [
    DecimalPipe,
    MatButton,
    MatIconButton,
    MatIcon,
    MatTooltip,
    RouterLink,
  ],
  changeDetection: ChangeDetectionStrategy.OnPush,
  styleUrl: '../../../data-access/src/lib/inventory.scss',
  styles: `
    h2,
    h3 {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 0.5rem;
    }
    h3 {
      margin: 1rem 0 0.5rem;
      font: var(--mat-sys-title-small);
    }
    tbody tr.pick {
      cursor: pointer;
    }
    tr.selected {
      background: color-mix(in srgb, var(--mat-sys-primary) 10%, transparent);
    }
    .grid {
      display: grid;
      gap: 4px;
      overflow-x: auto;
      padding-bottom: 0.25rem;
    }
    .grid-row {
      display: flex;
      gap: 4px;
      align-items: stretch;
    }
    .level {
      flex: 0 0 2.25rem;
      align-self: center;
      font: var(--mat-sys-label-medium);
      color: var(--mat-sys-on-surface-variant);
    }
    .cell {
      flex: 0 0 4.25rem;
      min-height: 3rem;
      padding: 0.25rem;
      border-radius: 6px;
      border: 1px solid var(--mat-sys-outline-variant);
      background: var(--mat-sys-surface);
      font: var(--mat-sys-label-small);
      text-align: center;
      cursor: pointer;
      color: var(--mat-sys-on-surface);
    }
    .cell .qty {
      display: block;
      font-weight: 600;
    }
    .cell.occupied {
      background: var(--trishul-success-container);
      border-color: var(--trishul-success);
    }
    .cell.blocked {
      background: var(--trishul-danger-container);
      border-color: var(--trishul-danger);
    }
    .cell.inactive {
      opacity: 0.45;
    }
    .legend {
      display: flex;
      flex-wrap: wrap;
      gap: 0.75rem;
      margin: 0.5rem 0;
      font: var(--mat-sys-body-small);
      color: var(--mat-sys-on-surface-variant);
    }
    .legend span::before {
      content: '';
      display: inline-block;
      width: 0.75rem;
      height: 0.75rem;
      margin-right: 0.25rem;
      vertical-align: middle;
      border-radius: 3px;
      border: 1px solid var(--mat-sys-outline-variant);
    }
    .legend .l-occupied::before {
      background: var(--trishul-success-container);
    }
    .legend .l-blocked::before {
      background: var(--trishul-danger-container);
    }
    .badge-blocked {
      color: var(--trishul-danger);
      font: var(--mat-sys-label-small);
      font-weight: 600;
    }
  `,
  template: `
    @let l = location();
    <h2>
      Storage in {{ l.code }}
      @if (canManage()) {
        <button mat-button (click)="editStorageRack(null)">
          <mat-icon>add</mat-icon>Add rack
        </button>
      }
    </h2>
    <p class="muted">
      {{ l.locationType }} ·
      {{
        l.requiresBin
          ? 'every movement here needs a bin'
          : 'a bin is optional: stock may also be kept at the location itself'
      }}
    </p>

    <table class="plain">
      <thead>
        <tr>
          <th>Rack</th>
          <th>Type</th>
          <th class="num">Levels × bins</th>
          <th class="num">Bins in use</th>
          <th class="num">Qty</th>
          <th></th>
        </tr>
      </thead>
      <tbody>
        @for (r of storageRacks(); track r.id) {
          <tr
            class="pick"
            [class.selected]="r.id === rackId()"
            (click)="rackId.set(r.id)"
          >
            <td>
              {{ r.shortCode }}
              @if (r.name) {
                <div class="muted">{{ r.name }}</div>
              }
              @if (r.isBlocked) {
                <div class="badge-blocked">
                  Blocked{{ r.blockedReason ? ': ' + r.blockedReason : '' }}
                </div>
              }
              @if (!r.isActive) {
                <div class="muted">Inactive</div>
              }
            </td>
            <td>{{ r.rackType }}</td>
            <td class="num">{{ r.levels }} × {{ r.positions }}</td>
            <td class="num">{{ r.occupiedBins }} / {{ r.binCount }}</td>
            <td class="num">{{ r.qtyOnHand | number: '1.0-3' }}</td>
            <td class="actions">
              @if (canManage()) {
                <button
                  mat-icon-button
                  matTooltip="Change, resize or block"
                  (click)="$event.stopPropagation(); editStorageRack(r)"
                >
                  <mat-icon>edit</mat-icon>
                </button>
              }
            </td>
          </tr>
        } @empty {
          <tr>
            <td colspan="6" class="empty">
              No racks. Add one to get its bins with printed codes, or keep
              stock in loose bins, yard spots or at the location itself.
            </td>
          </tr>
        }
      </tbody>
    </table>

    @if (rack(); as r) {
      <h3>
        {{ r.code }} · bins
        <a
          mat-button
          routerLink="../bin-stock"
          [queryParams]="{ locationId: l.id, storageRackId: r.id }"
          ><mat-icon>inventory</mat-icon>Stock in this rack</a
        >
        @if (canManage()) {
          <button
            mat-button
            type="button"
            (click)="
              barcodes.printLabels({ kind: 'Bin', storageRackIds: [r.id] })
            "
          >
            <mat-icon>print</mat-icon>Print bin labels
          </button>
        }
      </h3>
      <div class="legend">
        <span>Empty</span><span class="l-occupied">Holds stock</span
        ><span class="l-blocked">Blocked</span>
      </div>
      <div class="grid">
        @for (level of levels(); track level.no) {
          <div class="grid-row">
            <span class="level">L{{ level.no }}</span>
            @for (b of level.bins; track b.id) {
              <button
                type="button"
                class="cell"
                [class.occupied]="b.itemCount > 0"
                [class.blocked]="b.isBlocked"
                [class.inactive]="!b.isActive"
                [matTooltip]="tip(b)"
                (click)="editBin(b)"
              >
                B{{ b.positionNo }}
                @if (b.itemCount) {
                  <span class="qty">{{ b.qtyOnHand | number: '1.0-3' }}</span>
                }
              </button>
            }
          </div>
        }
      </div>
    }

    <h3>
      Loose bins and yard spots
      @if (canManage()) {
        <span>
          @if (looseBins().length) {
            <button
              mat-button
              type="button"
              (click)="barcodes.printLabels({ kind: 'Bin', locationId: l.id })"
            >
              <mat-icon>print</mat-icon>Print labels
            </button>
          }
          <button mat-button (click)="editBin(null)">
            <mat-icon>add</mat-icon>Add bin / spot
          </button>
        </span>
      }
    </h3>
    <table class="plain">
      <thead>
        <tr>
          <th>Code</th>
          <th>Type</th>
          <th class="num">Items</th>
          <th class="num">Qty</th>
          <th>Status</th>
          <th></th>
        </tr>
      </thead>
      <tbody>
        @for (b of looseBins(); track b.id) {
          <tr>
            <td>
              <a
                class="name"
                routerLink="../bin-stock"
                [queryParams]="{ locationId: l.id, binId: b.id }"
                >{{ b.code }}</a
              >
              @if (b.description) {
                <div class="muted">{{ b.description }}</div>
              }
            </td>
            <td>
              {{ b.binType }}
              @if (b.isReceiving) {
                <div class="muted">Receiving bin</div>
              }
            </td>
            <td class="num">{{ b.itemCount }}</td>
            <td class="num">{{ b.qtyOnHand | number: '1.0-3' }}</td>
            <td>
              @if (b.isBlocked) {
                <span class="badge-blocked">Blocked</span>
              } @else {
                {{ b.isActive ? 'Active' : 'Inactive' }}
              }
            </td>
            <td class="actions">
              @if (canManage()) {
                <button
                  mat-icon-button
                  matTooltip="Change"
                  (click)="editBin(b)"
                >
                  <mat-icon>edit</mat-icon>
                </button>
              }
            </td>
          </tr>
        } @empty {
          <tr>
            <td colspan="6" class="empty">No loose bins or spots.</td>
          </tr>
        }
      </tbody>
    </table>
  `,
})
export class StoragePanel {
  private readonly api = inject(ApiClient);
  private readonly dialog = inject(MatDialog);
  protected readonly barcodes = inject(BarcodeApi);

  readonly location = input.required<LocationOut>();
  readonly canManage = input(false);
  /** Something changed (counts on the location list may differ). */
  readonly changed = output<void>();

  protected readonly storageRacks = signal<StorageRackOut[]>([]);
  protected readonly rackId = signal<number | null>(null);
  protected readonly rack = computed(
    () => this.storageRacks().find((r) => r.id === this.rackId()) ?? null,
  );
  private readonly rackBins = signal<RackOut[]>([]);
  protected readonly looseBins = signal<RackOut[]>([]);

  /** Top level first, as the rack is seen from the front. */
  protected readonly levels = computed(() => {
    const rack = this.rack();
    if (!rack) return [];
    const bins = this.rackBins();
    return Array.from({ length: rack.levels }, (_, i) => rack.levels - i).map(
      (no) => ({
        no,
        bins: bins
          .filter((b) => b.levelNo === no && b.isActive)
          .sort((a, b) => (a.positionNo ?? 0) - (b.positionNo ?? 0)),
      }),
    );
  });

  constructor() {
    effect(() => {
      const location = this.location();
      untracked(() => {
        this.rackId.set(null);
        this.loadRacks(location.id);
        this.loadLoose(location.id);
      });
    });
    effect(() => {
      const id = this.rackId();
      untracked(() => (id ? this.loadRackBins(id) : this.rackBins.set([])));
    });
  }

  protected tip(b: RackOut): string {
    const parts = [b.code, b.binType];
    if (b.isReceiving) parts.push('receiving bin');
    if (b.itemCount) parts.push(`${b.itemCount} item(s), qty ${b.qtyOnHand}`);
    else parts.push('empty');
    if (b.maxQty) parts.push(`max ${b.maxQty}`);
    if (b.isBlocked)
      parts.push(`blocked${b.blockedReason ? ': ' + b.blockedReason : ''}`);
    return parts.join(' · ');
  }

  private loadRacks(locationId: number): void {
    this.api
      .call(listStorageRacks, { locationId, status: 'all' })
      .pipe(catchError(() => EMPTY))
      .subscribe((rows) => this.storageRacks.set(rows));
  }

  private loadRackBins(storageRackId: number): void {
    this.api
      .call(listRacks, {
        locationId: this.location().id,
        storageRackId,
        status: 'all',
      })
      .pipe(catchError(() => EMPTY))
      .subscribe((rows) => this.rackBins.set(rows));
  }

  private loadLoose(locationId: number): void {
    this.api
      .call(listRacks, { locationId, loose: true, status: 'all' })
      .pipe(catchError(() => EMPTY))
      .subscribe((rows) => this.looseBins.set(rows));
  }

  private reload(): void {
    const id = this.location().id;
    this.loadRacks(id);
    this.loadLoose(id);
    const rackId = this.rackId();
    if (rackId) this.loadRackBins(rackId);
    this.changed.emit();
  }

  protected editStorageRack(rack: StorageRackOut | null): void {
    if (!this.canManage()) return;
    const location = this.location();
    openFieldsDialog(this.dialog, {
      title: rack
        ? `Change rack ${rack.code}`
        : `Add a rack in ${location.code}`,
      submitText: rack ? 'Save' : 'Add rack',
      fields: [
        rack
          ? {
              key: 'code',
              label: 'Rack code',
              readonly: true,
              wide: true,
            }
          : {
              key: 'shortCode',
              label: 'Rack no',
              required: true,
              maxLength: 8,
              pattern: '^[A-Za-z0-9]+$',
              hint: `e.g. R01 → bins ${location.code}-R01-L1-B01 …`,
              wide: true,
            },
        { key: 'name', label: 'Name', maxLength: 80, wide: true },
        {
          key: 'rackType',
          label: 'Type',
          type: 'select' as const,
          required: true,
          options: RACK_TYPES.map((t) => ({ value: t, label: t })),
        },
        {
          key: 'maxWeightKg',
          label: 'Max weight (kg)',
          type: 'number' as const,
          min: 0,
        },
        {
          key: 'levels',
          label: 'Levels (from the floor)',
          type: 'number' as const,
          required: true,
          min: 1,
          max: 20,
        },
        {
          key: 'positions',
          label: 'Bins per level',
          type: 'number' as const,
          required: true,
          min: 1,
          max: 99,
          hint: rack ? 'Shrinking only removes empty bins' : undefined,
        },
        ...(rack
          ? [
              {
                key: 'isBlocked',
                label: 'Blocked (no put-away)',
                type: 'checkbox' as const,
              },
              {
                key: 'blockedReason',
                label: 'Why blocked',
                maxLength: 200,
                wide: true,
              },
              { key: 'isActive', label: 'Active', type: 'checkbox' as const },
            ]
          : [
              {
                key: 'binType',
                label: 'Type of its bins',
                type: 'select' as const,
                required: true,
                options: BIN_TYPES,
                wide: true,
              },
            ]),
      ],
      value: rack
        ? { ...rack }
        : { rackType: 'Rack', levels: 4, positions: 5, binType: 'Mixed' },
      save: (v) =>
        rack
          ? this.api.call(
              updateStorageRack,
              {
                storageRackId: rack.id,
                body: {
                  name: v['name'],
                  rackType: v['rackType'],
                  levels: v['levels'],
                  positions: v['positions'],
                  maxWeightKg: v['maxWeightKg'],
                  isBlocked: v['isBlocked'],
                  blockedReason: v['blockedReason'],
                  isActive: v['isActive'],
                } as StorageRackUpdate,
              },
              withRowVersion(rack.rowVersion),
            )
          : this.api.call(createStorageRack, {
              locationId: location.id,
              body: v as unknown as StorageRackCreate,
            }),
    })
      .pipe(filter((saved) => !!saved))
      .subscribe((saved) => {
        if (!rack && saved) this.rackId.set((saved as StorageRackOut).id);
        this.reload();
      });
  }

  protected editBin(bin: RackOut | null): void {
    if (!this.canManage()) return;
    const location = this.location();
    const inRack = !!bin?.storageRackId;
    openFieldsDialog(this.dialog, {
      title: bin ? `Bin ${bin.code}` : `Add a bin or spot in ${location.code}`,
      submitText: bin ? 'Save' : 'Add',
      fields: [
        {
          key: 'code',
          label: 'Code',
          required: !inRack,
          readonly: inRack,
          maxLength: 30,
          pattern: CODE,
          hint: inRack
            ? 'Set by the rack, level and position'
            : 'Unique everywhere, e.g. BBS-Y01-S03 for a yard spot',
          wide: true,
        },
        {
          key: 'binType',
          label: 'Type',
          type: 'select' as const,
          required: true,
          options: BIN_TYPES,
          wide: true,
        },
        {
          key: 'maxQty',
          label: 'Max quantity (all items)',
          type: 'number' as const,
          min: 0,
          hint: 'Empty = no limit',
        },
        { key: 'description', label: 'Description', maxLength: 100 },
        {
          key: 'isReceiving',
          label: 'Receiving bin (GRNs put stock here first)',
          type: 'checkbox' as const,
          wide: true,
        },
        ...(bin
          ? [
              {
                key: 'isBlocked',
                label: 'Blocked (no put-away)',
                type: 'checkbox' as const,
              },
              {
                key: 'blockedReason',
                label: 'Why blocked',
                maxLength: 200,
                wide: true,
              },
              { key: 'isActive', label: 'Active', type: 'checkbox' as const },
            ]
          : []),
      ],
      value: bin
        ? { ...bin }
        : {
            binType:
              location.locationType === 'Open area' ? 'Area spot' : 'Mixed',
          },
      save: (v) => {
        const maxQty =
          v['maxQty'] === null || v['maxQty'] === ''
            ? null
            : String(v['maxQty']);
        if (!bin) {
          return this.api.call(createRack, {
            locationId: location.id,
            body: { ...v, maxQty } as unknown as RackCreate,
          });
        }
        const body: Record<string, unknown> = {
          binType: v['binType'],
          maxQty,
          description: v['description'],
          isBlocked: v['isBlocked'],
          blockedReason: v['blockedReason'],
          isReceiving: !!v['isReceiving'],
          isActive: v['isActive'],
        };
        if (!inRack) body['code'] = v['code'];
        return this.api.call(
          updateRack,
          { rackId: bin.id, body: body as RackUpdate },
          withRowVersion(bin.rowVersion),
        );
      },
    })
      .pipe(filter((saved) => !!saved))
      .subscribe(() => this.reload());
  }
}
