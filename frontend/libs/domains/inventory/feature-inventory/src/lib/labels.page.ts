import {
  ChangeDetectionStrategy,
  Component,
  computed,
  inject,
  signal,
} from '@angular/core';
import { toObservable, toSignal } from '@angular/core/rxjs-interop';
import { FormControl, ReactiveFormsModule } from '@angular/forms';
import { MatButton, MatIconButton } from '@angular/material/button';
import { MatCheckbox } from '@angular/material/checkbox';
import { MatFormField, MatLabel } from '@angular/material/form-field';
import { MatIcon } from '@angular/material/icon';
import { MatInput } from '@angular/material/input';
import { MatOption, MatSelect } from '@angular/material/select';
import { MatTab, MatTabGroup } from '@angular/material/tabs';
import { MatTooltip } from '@angular/material/tooltip';
import { ActivatedRoute } from '@angular/router';
import { catchError, of, switchMap } from 'rxjs';
import {
  ApiClient,
  ItemListItem,
  listLocations,
  listStorageRacks,
} from '@trishul/core-api';
import { AuthStore } from '@trishul/core-auth';
import {
  BarcodeApi,
  INV_BARCODE_MANAGE,
  ItemPicker,
  LabelRequest,
} from '@trishul/inventory-data-access';
import { PageHeader } from '@trishul/shared-ui';

type Layout = NonNullable<LabelRequest['layout']>;

/** Barcode labels as a PDF: the bins of a rack or a location's loose bins and spots, racks, or items. */
@Component({
  selector: 'trishul-labels-page',
  imports: [
    ReactiveFormsModule,
    MatButton,
    MatIconButton,
    MatCheckbox,
    MatFormField,
    MatLabel,
    MatIcon,
    MatInput,
    MatSelect,
    MatOption,
    MatTab,
    MatTabGroup,
    MatTooltip,
    ItemPicker,
    PageHeader,
  ],
  changeDetection: ChangeDetectionStrategy.OnPush,
  styleUrl: '../../../data-access/src/lib/inventory.scss',
  styles: `
    .row {
      display: flex;
      flex-wrap: wrap;
      gap: 0.75rem;
      align-items: center;
      margin: 1rem 0;
    }
    .row mat-form-field {
      width: 16rem;
    }
    .row .copies {
      width: 7rem;
    }
    .racks {
      display: grid;
      grid-template-columns: repeat(auto-fill, minmax(14rem, 1fr));
      gap: 0.25rem 1rem;
      margin: 0.5rem 0 1rem;
    }
    .items trishul-item-picker {
      flex: 1 1 22rem;
    }
  `,
  template: `
    <trishul-page-header
      title="Print labels"
      subtitle="Barcode labels for bins, racks and items, to print on a roll label printer or A4 sticker sheets"
    />

    <div class="row">
      <mat-form-field appearance="outline" subscriptSizing="dynamic">
        <mat-label>Paper</mat-label>
        <mat-select [value]="layout()" (valueChange)="layout.set($event)">
          <mat-option value="roll">Roll, 50 × 25 mm (one per label)</mat-option>
          <mat-option value="sheet">A4 sticker sheet, 3 × 8</mat-option>
        </mat-select>
      </mat-form-field>
      <mat-form-field
        class="copies"
        appearance="outline"
        subscriptSizing="dynamic"
      >
        <mat-label>Copies</mat-label>
        <input
          matInput
          type="number"
          min="1"
          max="20"
          [value]="copies()"
          (input)="copies.set(+$any($event.target).value || 1)"
        />
      </mat-form-field>
    </div>

    <mat-tab-group
      mat-stretch-tabs="false"
      animationDuration="0ms"
      [selectedIndex]="tab()"
      (selectedIndexChange)="tab.set($event)"
    >
      <mat-tab label="Bins and racks">
        <div class="row">
          <mat-form-field appearance="outline" subscriptSizing="dynamic">
            <mat-label>Location</mat-label>
            <mat-select
              [value]="locationId()"
              (valueChange)="locationId.set($event); chosenRacks.set([])"
            >
              @for (l of locations(); track l.id) {
                <mat-option [value]="l.id"
                  >{{ l.code }} · {{ l.name }}</mat-option
                >
              }
            </mat-select>
          </mat-form-field>
        </div>
        @if (locationId()) {
          @if (racks().length) {
            <p class="muted">
              Choose racks: print their bin labels or the rack labels.
            </p>
            <div class="racks">
              @for (r of racks(); track r.id) {
                <mat-checkbox
                  [checked]="chosenRacks().includes(r.id)"
                  (change)="toggleRack(r.id, $event.checked)"
                  >{{ r.code }} ({{ r.binCount }} bins)</mat-checkbox
                >
              }
            </div>
          } @else {
            <p class="muted">This location has no racks.</p>
          }
          <div class="row">
            <button
              mat-flat-button
              type="button"
              [disabled]="!chosenRacks().length"
              (click)="printRackBins()"
            >
              <mat-icon>print</mat-icon>Bin labels of chosen racks
            </button>
            <button
              mat-stroked-button
              type="button"
              [disabled]="!chosenRacks().length"
              (click)="printRacks()"
            >
              <mat-icon>print</mat-icon>Rack labels
            </button>
            <button mat-stroked-button type="button" (click)="printLoose()">
              <mat-icon>print</mat-icon>Loose bins and yard spots
            </button>
          </div>
        }
      </mat-tab>
      @if (canItems) {
        <mat-tab label="Items">
          <p class="muted">
            Each label carries the item's primary barcode, or its item code as a
            barcode when it has none.
          </p>
          <div class="row items">
            <trishul-item-picker [formControl]="picker" [stockOnly]="false" />
            <button
              mat-stroked-button
              type="button"
              [disabled]="!picker.value"
              (click)="addItem()"
            >
              <mat-icon>add</mat-icon>Add
            </button>
          </div>
          <table class="plain">
            <tbody>
              @for (i of items(); track i.id) {
                <tr>
                  <td>{{ i.itemCode }}</td>
                  <td>{{ i.description }}</td>
                  <td class="actions">
                    <button
                      mat-icon-button
                      matTooltip="Remove"
                      (click)="removeItem(i.id)"
                    >
                      <mat-icon>close</mat-icon>
                    </button>
                  </td>
                </tr>
              } @empty {
                <tr>
                  <td class="empty">Add the items to label.</td>
                </tr>
              }
            </tbody>
          </table>
          <div class="row">
            <button
              mat-flat-button
              type="button"
              [disabled]="!items().length"
              (click)="printItems()"
            >
              <mat-icon>print</mat-icon>Print {{ items().length }} item label(s)
            </button>
          </div>
        </mat-tab>
      }
    </mat-tab-group>
  `,
})
export class LabelsPage {
  private readonly api = inject(ApiClient);
  private readonly barcodes = inject(BarcodeApi);
  private readonly route = inject(ActivatedRoute);
  protected readonly canItems =
    inject(AuthStore).hasPermission(INV_BARCODE_MANAGE);

  protected readonly layout = signal<Layout>('roll');
  protected readonly copies = signal(1);
  protected readonly tab = signal(0);
  protected readonly locationId = signal<number | null>(
    Number(this.route.snapshot.queryParamMap.get('locationId')) || null,
  );
  protected readonly chosenRacks = signal<number[]>(
    this.route.snapshot.queryParamMap.get('storageRackId')
      ? [Number(this.route.snapshot.queryParamMap.get('storageRackId'))]
      : [],
  );
  protected readonly items = signal<ItemListItem[]>([]);
  protected readonly picker = new FormControl<ItemListItem | null>(null);

  protected readonly locations = toSignal(
    this.api
      .call(listLocations, { status: 'active' })
      .pipe(catchError(() => of([]))),
    { initialValue: [] },
  );
  protected readonly racks = toSignal(
    toObservable(computed(() => this.locationId())).pipe(
      switchMap((locationId) =>
        locationId
          ? this.api
              .call(listStorageRacks, { locationId, status: 'active' })
              .pipe(catchError(() => of([])))
          : of([]),
      ),
    ),
    { initialValue: [] },
  );

  protected toggleRack(id: number, on: boolean): void {
    this.chosenRacks.update((ids) =>
      on ? [...ids, id] : ids.filter((x) => x !== id),
    );
  }

  private request(): Pick<LabelRequest, 'layout' | 'copies'> {
    return { layout: this.layout(), copies: this.copies() };
  }

  protected printRackBins(): void {
    // One PDF, rack by rack, each rack's bins in level and position order.
    this.barcodes.printLabels({
      kind: 'Bin',
      storageRackIds: this.chosenRacks(),
      ...this.request(),
    });
  }

  protected printRacks(): void {
    this.barcodes.printLabels({
      kind: 'Rack',
      ids: this.chosenRacks(),
      ...this.request(),
    });
  }

  protected printLoose(): void {
    const locationId = this.locationId();
    if (locationId)
      this.barcodes.printLabels({ kind: 'Bin', locationId, ...this.request() });
  }

  protected addItem(): void {
    const item = this.picker.value;
    if (item && !this.items().some((i) => i.id === item.id)) {
      this.items.update((list) => [...list, item]);
    }
    this.picker.reset(null);
  }

  protected removeItem(id: number): void {
    this.items.update((list) => list.filter((i) => i.id !== id));
  }

  protected printItems(): void {
    this.barcodes.printLabels({
      kind: 'Item',
      ids: this.items().map((i) => i.id),
      ...this.request(),
    });
  }
}
