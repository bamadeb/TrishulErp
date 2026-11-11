import { DatePipe, DecimalPipe, NgTemplateOutlet } from '@angular/common';
import {
  ChangeDetectionStrategy,
  Component,
  computed,
  effect,
  inject,
  input,
  signal,
  untracked,
} from '@angular/core';
import { MatButton } from '@angular/material/button';
import { MatIcon } from '@angular/material/icon';
import { MatProgressBar } from '@angular/material/progress-bar';
import { RouterLink } from '@angular/router';
import {
  AdjustmentDetail,
  ApiClient,
  BatchMoved,
  TransferDetail,
  getAdjustment,
  getTransfer,
} from '@trishul/core-api';
import { PageHeader } from '@trishul/shared-ui';
import { EMPTY, Observable, catchError } from 'rxjs';
import { DocumentKind } from './document-list.page';
import { ageClass, n0 } from '@trishul/inventory-data-access';

type Detail = TransferDetail | AdjustmentDetail;

/** One posted transfer or adjustment, with the GRN batches it created or moved. */
@Component({
  selector: 'trishul-document-detail-page',
  imports: [
    DatePipe,
    DecimalPipe,
    NgTemplateOutlet,
    RouterLink,
    MatButton,
    MatIcon,
    MatProgressBar,
    PageHeader,
  ],
  changeDetection: ChangeDetectionStrategy.OnPush,
  styleUrl: '../../../data-access/src/lib/inventory.scss',
  template: `
    @switch (kind()) {
      @case ('transfer') {
        @if (transfer(); as t) {
          <trishul-page-header
            [title]="'Transfer ' + t.transferNo"
            [subtitle]="t.fromBranchName + ' → ' + t.toBranchName"
          >
            <a mat-stroked-button routerLink=".."
              ><mat-icon>arrow_back</mat-icon>All transfers</a
            >
          </trishul-page-header>
          <section class="card">
            <dl class="facts">
              <div>
                <dt>Date</dt>
                <dd>{{ t.transferDate | date: 'dd MMM yyyy' }}</dd>
              </div>
              <div>
                <dt>From</dt>
                <dd>{{ t.fromBranchName }} · {{ t.fromLocationName }}</dd>
              </div>
              <div>
                <dt>To</dt>
                <dd>{{ t.toBranchName }} · {{ t.toLocationName }}</dd>
              </div>
              <div>
                <dt>Value</dt>
                <dd>₹{{ t.totalValue | number: '1.2-2' }}</dd>
              </div>
              <div>
                <dt>By</dt>
                <dd>
                  {{ t.createdBy ?? '—' }} ·
                  {{ t.createdAt | date: 'dd MMM yyyy, HH:mm' }}
                </dd>
              </div>
              @if (t.remarks) {
                <div>
                  <dt>Remarks</dt>
                  <dd>{{ t.remarks }}</dd>
                </div>
              }
            </dl>
          </section>
          <section class="card">
            <h2>Items</h2>
            <table class="plain">
              <thead>
                <tr>
                  <th>Item</th>
                  <th class="num">Qty</th>
                  <th>From rack</th>
                  <th>To rack</th>
                  <th class="num">Value</th>
                </tr>
              </thead>
              <tbody>
                @for (l of t.lines; track l.id) {
                  <tr>
                    <td>
                      <a
                        class="name"
                        [routerLink]="['/inventory/items', l.itemId]"
                        >{{ l.itemCode }}</a
                      >
                      <div class="muted">{{ l.itemDescription }}</div>
                    </td>
                    <td class="num">
                      {{ l.quantity | number: '1.0-3' }} {{ l.uomCode }}
                    </td>
                    <td>{{ l.fromBinCode ?? 'Any' }}</td>
                    <td>{{ l.toBinCode ?? '—' }}</td>
                    <td class="num">{{ l.value | number: '1.2-2' }}</td>
                  </tr>
                }
              </tbody>
            </table>
          </section>
          <ng-container
            *ngTemplateOutlet="
              batchTable;
              context: {
                $implicit: t.batches,
                title: 'GRN batches moved (each keeps its GRN date)',
              }
            "
          />
        } @else {
          <mat-progress-bar mode="indeterminate" />
        }
      }
      @case ('adjustment') {
        @if (adjustment(); as a) {
          <trishul-page-header
            [title]="'Adjustment ' + a.adjustmentNo"
            [subtitle]="a.reason + ' · ' + a.branchName"
          >
            <a mat-stroked-button routerLink=".."
              ><mat-icon>arrow_back</mat-icon>All adjustments</a
            >
          </trishul-page-header>
          <section class="card">
            <dl class="facts">
              <div>
                <dt>Date</dt>
                <dd>{{ a.adjustmentDate | date: 'dd MMM yyyy' }}</dd>
              </div>
              <div>
                <dt>Location</dt>
                <dd>{{ a.branchName }} · {{ a.locationName }}</dd>
              </div>
              <div>
                <dt>Reason</dt>
                <dd>{{ a.reason }}</dd>
              </div>
              <div>
                <dt>Value change</dt>
                <dd [class.negative]="n0(a.valueChange) < 0">
                  ₹{{ a.valueChange | number: '1.2-2' }}
                </dd>
              </div>
              <div>
                <dt>Authorised by</dt>
                <dd>
                  {{ a.postedBy ?? '—' }} ·
                  {{ a.postedAt | date: 'dd MMM yyyy, HH:mm' }}
                </dd>
              </div>
              @if (a.remarks) {
                <div>
                  <dt>Remarks</dt>
                  <dd>{{ a.remarks }}</dd>
                </div>
              }
            </dl>
          </section>
          <section class="card">
            <h2>Items</h2>
            <table class="plain">
              <thead>
                <tr>
                  <th>Item</th>
                  <th class="num">Change</th>
                  <th>Rack</th>
                  <th class="num">Cost / unit</th>
                  <th>Remarks</th>
                </tr>
              </thead>
              <tbody>
                @for (l of a.lines; track l.id) {
                  <tr>
                    <td>
                      <a
                        class="name"
                        [routerLink]="['/inventory/items', l.itemId]"
                        >{{ l.itemCode }}</a
                      >
                      <div class="muted">{{ l.itemDescription }}</div>
                    </td>
                    <td
                      class="num"
                      [class.negative]="n0(l.qtyChange) < 0"
                      [class.positive]="n0(l.qtyChange) > 0"
                    >
                      {{ n0(l.qtyChange) > 0 ? '+' : ''
                      }}{{ l.qtyChange | number: '1.0-3' }} {{ l.uomCode }}
                    </td>
                    <td>{{ l.binCode ?? 'Any' }}</td>
                    <td class="num">
                      {{
                        l.unitCost !== null
                          ? (l.unitCost | number: '1.2-4')
                          : '—'
                      }}
                    </td>
                    <td>{{ l.remarks ?? '' }}</td>
                  </tr>
                }
              </tbody>
            </table>
          </section>
          <ng-container
            *ngTemplateOutlet="
              batchTable;
              context: { $implicit: a.batches, title: 'GRN batches changed' }
            "
          />
        } @else {
          <mat-progress-bar mode="indeterminate" />
        }
      }
    }

    <ng-template #batchTable let-batches let-title="title">
      <section class="card">
        <h2>{{ title }}</h2>
        <table class="plain">
          <thead>
            <tr>
              <th>Batch</th>
              <th>GRN no</th>
              <th>GRN date</th>
              <th>Age</th>
              <th>Rack</th>
              <th class="num">Qty</th>
              <th class="num">Value</th>
            </tr>
          </thead>
          <tbody>
            @for (b of asBatches(batches); track $index) {
              <tr>
                <td>{{ b.lotNo }}</td>
                <td>{{ b.grnNo }}</td>
                <td class="nowrap">{{ b.grnDate | date: 'dd MMM yyyy' }}</td>
                <td>
                  <span [class]="'age ' + ageClass(age(b.grnDate))"
                    >{{ age(b.grnDate) }} days</span
                  >
                </td>
                <td>{{ b.binCode ?? '—' }}</td>
                <td class="num" [class.negative]="n0(b.quantity) < 0">
                  {{ b.quantity | number: '1.0-3' }}
                </td>
                <td class="num">{{ b.value | number: '1.2-2' }}</td>
              </tr>
            }
          </tbody>
        </table>
      </section>
    </ng-template>
  `,
})
export class DocumentDetailPage {
  private readonly api = inject(ApiClient);
  readonly kind = input.required<DocumentKind>();
  readonly documentId = input.required<string>();

  protected readonly n0 = n0;
  protected readonly ageClass = ageClass;
  private readonly detail = signal<Detail | null>(null);
  protected readonly transfer = computed(() =>
    this.kind() === 'transfer'
      ? (this.detail() as TransferDetail | null)
      : null,
  );
  protected readonly adjustment = computed(() =>
    this.kind() === 'adjustment'
      ? (this.detail() as AdjustmentDetail | null)
      : null,
  );

  constructor() {
    effect(() => {
      const id = Number(this.documentId());
      const kind = this.kind();
      untracked(() => {
        const request: Observable<Detail> =
          kind === 'transfer'
            ? this.api.call(getTransfer, { transferId: id })
            : this.api.call(getAdjustment, { adjustmentId: id });
        request
          .pipe(catchError(() => EMPTY))
          .subscribe((d) => this.detail.set(d));
      });
    });
  }

  protected asBatches(value: unknown): BatchMoved[] {
    return value as BatchMoved[];
  }

  /** Days since the GRN date: the batch's age today. */
  protected age(grnDate: string): number {
    const [y, m, d] = grnDate.split('-').map(Number);
    const start = new Date(y, m - 1, d).getTime();
    const today = new Date();
    today.setHours(0, 0, 0, 0);
    return Math.round((today.getTime() - start) / 86_400_000);
  }
}
