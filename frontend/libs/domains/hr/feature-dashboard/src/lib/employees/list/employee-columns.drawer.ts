import {
  ChangeDetectionStrategy,
  Component,
  effect,
  input,
  output,
  signal,
} from '@angular/core';
import {
  CdkDrag,
  CdkDragDrop,
  CdkDragHandle,
  CdkDropList,
  moveItemInArray,
} from '@angular/cdk/drag-drop';
import { MatButton } from '@angular/material/button';
import { MatCheckbox } from '@angular/material/checkbox';
import { MatFormField, MatPrefix } from '@angular/material/form-field';
import { MatIcon } from '@angular/material/icon';
import { MatInput } from '@angular/material/input';
import {
  EMPLOYEE_COLUMNS,
  EmployeeColumnDef,
} from './employee-directory.prefs';

interface DraftColumn extends EmployeeColumnDef {
  checked: boolean;
}

/** Right-hand panel that shows, hides and reorders the employee table columns. */
@Component({
  selector: 'trishul-employee-columns-drawer',
  imports: [
    CdkDropList,
    CdkDrag,
    CdkDragHandle,
    MatButton,
    MatCheckbox,
    MatFormField,
    MatPrefix,
    MatIcon,
    MatInput,
  ],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <aside class="drawer" role="dialog" aria-label="Customize columns">
      <header>
        <h2>Customize Columns</h2>
        <button mat-icon-button type="button" aria-label="Close" (click)="dismissed.emit()">
          <mat-icon>close</mat-icon>
        </button>
      </header>
      <mat-form-field appearance="outline" subscriptSizing="dynamic" class="search">
        <mat-icon matPrefix>search</mat-icon>
        <input
          matInput
          type="search"
          placeholder="Search columns..."
          aria-label="Search columns"
          [value]="term()"
          (input)="term.set($any($event.target).value)"
        />
      </mat-form-field>
      <div
        class="list"
        cdkDropList
        [cdkDropListDisabled]="!!term().trim()"
        (cdkDropListDropped)="drop($event)"
      >
        @for (column of visible(); track column.id) {
          <div class="row" cdkDrag>
            <mat-checkbox
              [checked]="column.checked"
              (change)="toggle(column.id, $event.checked)"
            >
              {{ column.label }}
            </mat-checkbox>
            <button
              cdkDragHandle
              type="button"
              class="handle"
              aria-label="Drag to reorder"
              [disabled]="!!term().trim()"
            >
              <mat-icon>drag_indicator</mat-icon>
            </button>
          </div>
        }
      </div>
      <footer>
        <button mat-button type="button" (click)="reset()">Reset to Default</button>
        <span class="spacer"></span>
        <button mat-button type="button" (click)="dismissed.emit()">Cancel</button>
        <button mat-flat-button color="primary" type="button" (click)="apply()">Apply</button>
      </footer>
    </aside>
  `,
  styles: `
    :host {
      /* 3.5rem matches the application topbar, so the panel stays in the content area. */
      position: fixed;
      z-index: 200;
      top: 3.5rem;
      right: 0;
      bottom: 0;
      display: flex;
      flex-direction: column;
      width: min(22rem, 100%);
      max-width: 100%;
      box-sizing: border-box;
      overflow: hidden;
      background: var(--mat-sys-surface);
      isolation: isolate;
    }
    .drawer {
      display: flex;
      flex: 1 1 auto;
      flex-direction: column;
      width: 100%;
      min-height: 0;
      overflow: hidden;
      background: var(--mat-sys-surface);
      border-left: 1px solid var(--mat-sys-outline-variant);
      box-shadow: -8px 0 24px rgb(0 0 0 / 12%);
    }
    header {
      display: flex;
      flex-shrink: 0;
      align-items: center;
      justify-content: space-between;
      padding: 0.75rem 0.75rem 0.25rem 1rem;
      background: var(--mat-sys-surface);
    }
    h2 {
      margin: 0;
      font: var(--mat-sys-title-medium);
    }
    .search {
      flex-shrink: 0;
      box-sizing: border-box;
      width: auto;
      margin: 0.25rem 1rem 0.75rem;
      background: var(--mat-sys-surface);
    }
    .list {
      flex: 1 1 auto;
      min-height: 0;
      overflow-x: hidden;
      overflow-y: auto;
      padding: 0 0.5rem;
      background: var(--mat-sys-surface);
    }
    .row {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 0.5rem;
      padding: 0.15rem 0.5rem;
      border-radius: var(--mat-sys-corner-small);
      background: var(--mat-sys-surface);
    }
    .row.cdk-drag-preview {
      box-shadow: 0 2px 8px rgb(0 0 0 / 16%);
    }
    .handle {
      display: grid;
      place-items: center;
      border: 0;
      background: transparent;
      color: var(--mat-sys-on-surface-variant);
      cursor: grab;
    }
    .handle:disabled {
      cursor: default;
      opacity: 0.4;
    }
    footer {
      display: flex;
      flex-shrink: 0;
      flex-wrap: wrap;
      align-items: center;
      gap: 0.5rem;
      box-sizing: border-box;
      max-width: 100%;
      padding: 0.75rem 1rem;
      background: var(--mat-sys-surface);
      border-top: 1px solid var(--mat-sys-outline-variant);
    }
    .spacer {
      flex: 1;
    }
  `,
})
export class EmployeeColumnsDrawer {
  readonly selected = input.required<readonly string[]>();
  readonly dismissed = output<void>();
  readonly applied = output<string[]>();

  protected readonly term = signal('');
  private readonly draft = signal<DraftColumn[]>([]);
  protected readonly visible = () => {
    const query = this.term().trim().toLowerCase();
    const rows = this.draft();
    return query ? rows.filter((column) => column.label.toLowerCase().includes(query)) : rows;
  };

  constructor() {
    effect(() => {
      const selected = new Set(this.selected());
      const known = new Map(EMPLOYEE_COLUMNS.map((column) => [column.id, column]));
      const ordered = [
        ...this.selected().filter((id) => known.has(id)),
        ...EMPLOYEE_COLUMNS.map((column) => column.id).filter((id) => !selected.has(id)),
      ];
      this.draft.set(
        ordered.map((id) => ({ ...known.get(id)!, checked: selected.has(id) })),
      );
      this.term.set('');
    });
  }

  protected toggle(id: string, checked: boolean): void {
    this.draft.update((rows) =>
      rows.map((column) => (column.id === id ? { ...column, checked } : column)),
    );
  }

  protected drop(event: CdkDragDrop<DraftColumn[]>): void {
    if (this.term().trim()) {
      return;
    }
    this.draft.update((rows) => {
      const next = [...rows];
      moveItemInArray(next, event.previousIndex, event.currentIndex);
      return next;
    });
  }

  protected reset(): void {
    this.draft.set(
      EMPLOYEE_COLUMNS.map((column) => ({ ...column, checked: column.defaultVisible })),
    );
    this.term.set('');
  }

  protected apply(): void {
    this.applied.emit(this.draft().filter((column) => column.checked).map((column) => column.id));
  }
}
