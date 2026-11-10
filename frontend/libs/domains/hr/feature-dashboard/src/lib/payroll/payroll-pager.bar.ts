import { ChangeDetectionStrategy, Component, input, output } from '@angular/core';
import { MatIconButton } from '@angular/material/button';
import { MatIcon } from '@angular/material/icon';

/** Pager used by the payroll prototype tables. */
@Component({
  selector: 'trishul-payroll-pager',
  imports: [MatIconButton, MatIcon],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <footer class="pager">
      <label>
        {{ pageSizeLabel() }}:
        <select [value]="'' + pageSize()" (change)="sizeChange.emit($any($event.target).value)">
          @for (size of pageSizes(); track size) {
            <option [value]="'' + size">{{ size }}</option>
          }
        </select>
      </label>
      <span>{{ rangeLabel() }}</span>
      <div class="pages">
        <button type="button" mat-icon-button aria-label="Previous page" [disabled]="pageIndex() === 0" (click)="pageChange.emit(pageIndex() - 1)">
          <mat-icon>chevron_left</mat-icon>
        </button>
        @for (n of pages(); track n) {
          <button type="button" class="page" [class.selected]="n === pageIndex()" (click)="pageChange.emit(n)">{{ n + 1 }}</button>
        }
        <button type="button" mat-icon-button aria-label="Next page" [disabled]="pageIndex() >= pageCount() - 1" (click)="pageChange.emit(pageIndex() + 1)">
          <mat-icon>chevron_right</mat-icon>
        </button>
      </div>
    </footer>
  `,
  styleUrl: './payroll.shared.scss',
})
export class PayrollPagerBar {
  readonly pageIndex = input.required<number>();
  readonly pageSize = input.required<number>();
  readonly pageCount = input.required<number>();
  readonly pages = input.required<readonly number[]>();
  readonly rangeLabel = input.required<string>();
  readonly pageSizes = input<readonly number[]>([10, 20]);
  readonly pageSizeLabel = input('Items per page');
  readonly pageChange = output<number>();
  readonly sizeChange = output<string>();
}
