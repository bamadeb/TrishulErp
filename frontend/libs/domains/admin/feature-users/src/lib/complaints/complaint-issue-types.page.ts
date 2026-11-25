import {
  ChangeDetectionStrategy,
  Component,
  DestroyRef,
  computed,
  inject,
  signal,
} from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { FormsModule } from '@angular/forms';
import { MatButton, MatIconButton } from '@angular/material/button';
import { MatFormField, MatLabel } from '@angular/material/form-field';
import { MatIcon } from '@angular/material/icon';
import { MatInput } from '@angular/material/input';
import { MatProgressBar } from '@angular/material/progress-bar';
import { MatOption, MatSelect } from '@angular/material/select';
import { MatSlideToggle } from '@angular/material/slide-toggle';
import { MatSnackBar } from '@angular/material/snack-bar';
import { MatTableModule } from '@angular/material/table';
import { MatTooltip } from '@angular/material/tooltip';
import { RouterLink } from '@angular/router';
import {
  ComplaintDepartmentRef,
  ComplaintIssueTypeItem,
  ComplaintsApi,
} from '@trishul/admin-data-access';
import { PageHeader, StatusBadge, StatusSeverity } from '@trishul/shared-ui';

interface Draft {
  name: string;
  description: string;
  sortOrder: number;
}

const ACTIVE_SEVERITY: Record<string, StatusSeverity> = {
  Active: 'success',
  Inactive: 'neutral',
};

/** Issue types per department (Super Admin). The raise form shows the chosen department's active types. */
@Component({
  selector: 'trishul-complaint-issue-types-page',
  imports: [
    FormsModule,
    RouterLink,
    MatTableModule,
    MatButton,
    MatIconButton,
    MatIcon,
    MatFormField,
    MatLabel,
    MatInput,
    MatSelect,
    MatOption,
    MatSlideToggle,
    MatProgressBar,
    MatTooltip,
    PageHeader,
    StatusBadge,
  ],
  changeDetection: ChangeDetectionStrategy.OnPush,
  styleUrl: './complaints.scss',
  styles: `
    .add {
      display: flex;
      flex-wrap: wrap;
      gap: 0.75rem;
      align-items: center;
      margin-bottom: 1rem;
    }
    .add .wide {
      flex: 2 1 16rem;
    }
    .add .narrow {
      flex: 0 1 7rem;
    }
    .add mat-form-field {
      flex: 1 1 12rem;
    }
    .mat-column-sortOrder {
      width: 6rem;
    }
    .mat-column-used {
      width: 7rem;
    }
    .mat-column-status {
      width: 7rem;
    }
    .mat-column-actions {
      width: 8rem;
      text-align: right;
    }
    td mat-form-field {
      width: 100%;
    }
  `,
  template: `
    <trishul-page-header
      title="Complaint issue types"
      subtitle="What a complaint to each department can be about"
    >
      <a mat-button routerLink="/complaints/department">
        <mat-icon>arrow_back</mat-icon> Department complaints
      </a>
    </trishul-page-header>

    <div class="filters">
      <mat-form-field appearance="outline" subscriptSizing="dynamic">
        <mat-label>Department</mat-label>
        <mat-select
          [value]="departmentId()"
          (valueChange)="departmentId.set($event)"
        >
          <mat-option [value]="null">All departments</mat-option>
          @for (d of departments(); track d.id) {
            <mat-option [value]="d.id">{{ d.name }}</mat-option>
          }
        </mat-select>
      </mat-form-field>
      <mat-slide-toggle
        [checked]="showInactive()"
        (change)="showInactive.set($event.checked)"
      >
        Show switched-off types
      </mat-slide-toggle>
    </div>

    <form class="add card" (ngSubmit)="add()" aria-label="Add an issue type">
      <mat-form-field appearance="outline" subscriptSizing="dynamic">
        <mat-label>Department</mat-label>
        <mat-select
          name="dept"
          required
          [ngModel]="newDepartmentId()"
          (ngModelChange)="newDepartmentId.set($event)"
        >
          @for (d of departments(); track d.id) {
            <mat-option [value]="d.id">{{ d.name }}</mat-option>
          }
        </mat-select>
      </mat-form-field>
      <mat-form-field appearance="outline" subscriptSizing="dynamic">
        <mat-label>Issue type</mat-label>
        <input
          matInput
          name="name"
          required
          maxlength="80"
          [ngModel]="draft().name"
          (ngModelChange)="patchDraft({ name: $event })"
        />
      </mat-form-field>
      <mat-form-field class="wide" appearance="outline" subscriptSizing="dynamic">
        <mat-label>Help text (optional)</mat-label>
        <input
          matInput
          name="description"
          maxlength="300"
          [ngModel]="draft().description"
          (ngModelChange)="patchDraft({ description: $event })"
        />
      </mat-form-field>
      <mat-form-field class="narrow" appearance="outline" subscriptSizing="dynamic">
        <mat-label>Order</mat-label>
        <input
          matInput
          name="sortOrder"
          type="number"
          min="0"
          max="9999"
          [ngModel]="draft().sortOrder"
          (ngModelChange)="patchDraft({ sortOrder: +$event })"
        />
      </mat-form-field>
      <button
        mat-flat-button
        type="submit"
        [disabled]="busy() || !newDepartmentId() || draft().name.trim().length < 2"
      >
        <mat-icon>add</mat-icon> Add
      </button>
    </form>

    <div class="table-card">
      <div class="progress">
        @if (busy()) {
          <mat-progress-bar mode="indeterminate" />
        }
      </div>
      <div class="table-scroll">
        <table mat-table [dataSource]="shown()">
          <ng-container matColumnDef="department">
            <th mat-header-cell *matHeaderCellDef>Department</th>
            <td mat-cell *matCellDef="let t">{{ t.departmentName }}</td>
          </ng-container>
          <ng-container matColumnDef="name">
            <th mat-header-cell *matHeaderCellDef>Issue type</th>
            <td mat-cell *matCellDef="let t">
              @if (editingId() === t.id) {
                <mat-form-field appearance="outline" subscriptSizing="dynamic">
                  <input
                    matInput
                    aria-label="Issue type"
                    maxlength="80"
                    [ngModel]="edit().name"
                    (ngModelChange)="patchEdit({ name: $event })"
                  />
                </mat-form-field>
                <mat-form-field appearance="outline" subscriptSizing="dynamic">
                  <input
                    matInput
                    aria-label="Help text"
                    placeholder="Help text"
                    maxlength="300"
                    [ngModel]="edit().description"
                    (ngModelChange)="patchEdit({ description: $event })"
                  />
                </mat-form-field>
              } @else {
                <span class="issue">{{ t.name }}</span>
                @if (t.description) {
                  <div class="muted">{{ t.description }}</div>
                }
              }
            </td>
          </ng-container>
          <ng-container matColumnDef="sortOrder">
            <th mat-header-cell *matHeaderCellDef>Order</th>
            <td mat-cell *matCellDef="let t">
              @if (editingId() === t.id) {
                <mat-form-field appearance="outline" subscriptSizing="dynamic">
                  <input
                    matInput
                    type="number"
                    aria-label="Order"
                    min="0"
                    max="9999"
                    [ngModel]="edit().sortOrder"
                    (ngModelChange)="patchEdit({ sortOrder: +$event })"
                  />
                </mat-form-field>
              } @else {
                {{ t.sortOrder }}
              }
            </td>
          </ng-container>
          <ng-container matColumnDef="used">
            <th mat-header-cell *matHeaderCellDef>Complaints</th>
            <td mat-cell *matCellDef="let t">{{ t.complaintCount }}</td>
          </ng-container>
          <ng-container matColumnDef="status">
            <th mat-header-cell *matHeaderCellDef>Status</th>
            <td mat-cell *matCellDef="let t">
              <trishul-status-badge
                [status]="t.isActive ? 'Active' : 'Inactive'"
                [severities]="activeSeverity"
              />
            </td>
          </ng-container>
          <ng-container matColumnDef="actions">
            <th mat-header-cell *matHeaderCellDef>
              <span class="sr-only">Actions</span>
            </th>
            <td mat-cell *matCellDef="let t">
              @if (editingId() === t.id) {
                <button
                  mat-icon-button
                  type="button"
                  matTooltip="Save"
                  aria-label="Save issue type"
                  [disabled]="busy() || edit().name.trim().length < 2"
                  (click)="saveEdit(t)"
                >
                  <mat-icon>check</mat-icon>
                </button>
                <button
                  mat-icon-button
                  type="button"
                  matTooltip="Cancel"
                  aria-label="Cancel"
                  (click)="editingId.set(null)"
                >
                  <mat-icon>close</mat-icon>
                </button>
              } @else {
                <button
                  mat-icon-button
                  type="button"
                  matTooltip="Edit"
                  [attr.aria-label]="'Edit ' + t.name"
                  (click)="startEdit(t)"
                >
                  <mat-icon>edit</mat-icon>
                </button>
                <button
                  mat-icon-button
                  type="button"
                  [matTooltip]="t.isActive ? 'Switch off' : 'Switch on'"
                  [attr.aria-label]="(t.isActive ? 'Switch off ' : 'Switch on ') + t.name"
                  [disabled]="busy()"
                  (click)="toggle(t)"
                >
                  <mat-icon>{{ t.isActive ? 'block' : 'check_circle' }}</mat-icon>
                </button>
              }
            </td>
          </ng-container>
          <tr mat-header-row *matHeaderRowDef="columns; sticky: true"></tr>
          <tr mat-row *matRowDef="let row; columns: columns"></tr>
          <tr class="mat-mdc-row" *matNoDataRow>
            <td class="empty" [attr.colspan]="columns.length">
              {{ busy() ? 'Loading…' : 'No issue types yet.' }}
            </td>
          </tr>
        </table>
      </div>
    </div>
  `,
})
export class ComplaintIssueTypesPage {
  private readonly api = inject(ComplaintsApi);
  private readonly snackBar = inject(MatSnackBar);
  private readonly destroyRef = inject(DestroyRef);

  protected readonly columns = [
    'department',
    'name',
    'sortOrder',
    'used',
    'status',
    'actions',
  ];
  protected readonly activeSeverity = ACTIVE_SEVERITY;
  protected readonly items = signal<ComplaintIssueTypeItem[]>([]);
  protected readonly departments = signal<ComplaintDepartmentRef[]>([]);
  protected readonly departmentId = signal<number | null>(null);
  protected readonly showInactive = signal(false);
  protected readonly busy = signal(false);
  protected readonly newDepartmentId = signal<number | null>(null);
  protected readonly draft = signal<Draft>({
    name: '',
    description: '',
    sortOrder: 0,
  });
  protected readonly editingId = signal<number | null>(null);
  protected readonly edit = signal<Draft>({
    name: '',
    description: '',
    sortOrder: 0,
  });

  protected readonly shown = computed(() =>
    this.items().filter(
      (t) =>
        (this.departmentId() === null ||
          t.departmentId === this.departmentId()) &&
        (this.showInactive() || t.isActive),
    ),
  );

  constructor() {
    this.api
      .access()
      .pipe(takeUntilDestroyed())
      .subscribe((access) => this.departments.set(access.managedDepartments));
    this.load();
  }

  private load(): void {
    this.busy.set(true);
    this.api
      .issueTypes()
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: (list) => {
          this.items.set(list);
          this.busy.set(false);
        },
        error: () => this.busy.set(false),
      });
  }

  protected patchDraft(changes: Partial<Draft>): void {
    this.draft.update((d) => ({ ...d, ...changes }));
  }

  protected patchEdit(changes: Partial<Draft>): void {
    this.edit.update((d) => ({ ...d, ...changes }));
  }

  protected add(): void {
    const departmentId = this.newDepartmentId();
    const draft = this.draft();
    if (!departmentId || draft.name.trim().length < 2) return;
    this.busy.set(true);
    this.api
      .createIssueType({
        departmentId,
        name: draft.name.trim(),
        description: draft.description.trim() || null,
        sortOrder: draft.sortOrder || 0,
      })
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: (created) => {
          this.snackBar.open(`Issue type ${created.name} added.`, 'OK', {
            duration: 3000,
          });
          this.draft.set({ name: '', description: '', sortOrder: 0 });
          this.load();
        },
        error: () => this.busy.set(false),
      });
  }

  protected startEdit(item: ComplaintIssueTypeItem): void {
    this.edit.set({
      name: item.name,
      description: item.description ?? '',
      sortOrder: item.sortOrder,
    });
    this.editingId.set(item.id);
  }

  protected saveEdit(item: ComplaintIssueTypeItem): void {
    const edit = this.edit();
    this.busy.set(true);
    this.api
      .updateIssueType(item, {
        name: edit.name.trim(),
        description: edit.description.trim() || null,
        sortOrder: edit.sortOrder || 0,
      })
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: () => {
          this.editingId.set(null);
          this.load();
        },
        error: () => this.busy.set(false),
      });
  }

  protected toggle(item: ComplaintIssueTypeItem): void {
    this.busy.set(true);
    this.api
      .updateIssueType(item, { isActive: !item.isActive })
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: () => this.load(),
        error: () => this.busy.set(false),
      });
  }
}
