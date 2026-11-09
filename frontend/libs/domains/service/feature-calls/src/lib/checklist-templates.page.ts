import { ChangeDetectionStrategy, Component, inject, signal } from '@angular/core';
import { MatButton, MatIconButton } from '@angular/material/button';
import { MatDialog } from '@angular/material/dialog';
import { MatIcon } from '@angular/material/icon';
import { MatProgressBar } from '@angular/material/progress-bar';
import { MatSlideToggle } from '@angular/material/slide-toggle';
import { MatSnackBar } from '@angular/material/snack-bar';
import { MatTooltip } from '@angular/material/tooltip';
import { AuthStore } from '@trishul/core-auth';
import {
  CHECKLIST_MANAGE_PERMISSION,
  ChecklistTemplateOut,
  ServiceReportApi,
} from '@trishul/service-data-access';
import { PageHeader } from '@trishul/shared-ui';
import {
  ChecklistTemplateDialog,
  ChecklistTemplateDialogData,
} from './checklist-template.dialog';

/** Service > Inspection checklists: the questions engineers answer in a service report. */
@Component({
  selector: 'trishul-checklist-templates-page',
  imports: [
    MatButton,
    MatIconButton,
    MatIcon,
    MatProgressBar,
    MatSlideToggle,
    MatTooltip,
    PageHeader,
  ],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <trishul-page-header
      title="Inspection checklists"
      subtitle="The questions an engineer answers on site, before and during the repair"
    >
      @if (canManage) {
        <button mat-flat-button type="button" (click)="open()">
          <mat-icon>add</mat-icon> Add checklist
        </button>
      }
    </trishul-page-header>
    @if (loading()) {
      <mat-progress-bar mode="indeterminate" />
    }
    <div class="toolbar">
      <mat-slide-toggle [checked]="showInactive()" (change)="toggleInactive($event.checked)">
        Show inactive
      </mat-slide-toggle>
    </div>
    <table class="list">
      <thead>
        <tr>
          <th>Checklist</th>
          <th>Brand</th>
          <th>Call type</th>
          <th>Questions</th>
          <th>Status</th>
          <th></th>
        </tr>
      </thead>
      <tbody>
        @for (t of templates(); track t.id) {
          <tr [class.inactive]="!t.isActive">
            <td>{{ t.name }}</td>
            <td>{{ t.principalName ?? 'All brands' }}</td>
            <td>{{ t.callType ?? 'All call types' }}</td>
            <td>
              {{ t.items.length }}
              <span class="muted">({{ required(t) }} required)</span>
            </td>
            <td>{{ t.isActive ? 'Active' : 'Inactive' }}</td>
            <td class="end">
              <button
                mat-icon-button
                type="button"
                [matTooltip]="canManage ? 'Edit' : 'View'"
                (click)="open(t)"
              >
                <mat-icon>{{ canManage ? 'edit' : 'visibility' }}</mat-icon>
              </button>
            </td>
          </tr>
        } @empty {
          <tr>
            <td colspan="6" class="empty">
              {{ loading() ? 'Loading…' : 'No checklists yet. Reports start with an empty checklist.' }}
            </td>
          </tr>
        }
      </tbody>
    </table>
  `,
  styles: `
    .toolbar {
      margin: 0.5rem 0 1rem;
    }
    .list {
      width: 100%;
      border-collapse: collapse;
      background: var(--mat-sys-surface);
    }
    th,
    td {
      padding: 0.6rem 0.75rem;
      text-align: left;
      border-bottom: 1px solid var(--mat-sys-outline-variant);
    }
    th {
      font: var(--mat-sys-label-medium);
      color: var(--mat-sys-on-surface-variant);
    }
    .end {
      text-align: right;
    }
    .inactive td {
      color: var(--mat-sys-on-surface-variant);
    }
    .muted {
      color: var(--mat-sys-on-surface-variant);
    }
    .empty {
      text-align: center;
      color: var(--mat-sys-on-surface-variant);
    }
  `,
})
export class ChecklistTemplatesPage {
  private readonly api = inject(ServiceReportApi);
  private readonly dialog = inject(MatDialog);
  private readonly snackBar = inject(MatSnackBar);

  protected readonly canManage = inject(AuthStore).hasPermission(CHECKLIST_MANAGE_PERMISSION);
  protected readonly loading = signal(true);
  protected readonly templates = signal<ChecklistTemplateOut[]>([]);
  protected readonly showInactive = signal(false);

  constructor() {
    this.load();
  }

  protected required(t: ChecklistTemplateOut): number {
    return t.items.filter((i) => i.isMandatory).length;
  }

  protected toggleInactive(on: boolean): void {
    this.showInactive.set(on);
    this.load();
  }

  protected open(template?: ChecklistTemplateOut): void {
    if (!this.canManage && !template) return;
    this.dialog
      .open<ChecklistTemplateDialog, ChecklistTemplateDialogData, ChecklistTemplateOut>(
        ChecklistTemplateDialog,
        { data: { template, readonly: !this.canManage }, maxWidth: '95vw' },
      )
      .afterClosed()
      .subscribe((saved) => {
        if (!saved) return;
        this.snackBar.open('Checklist saved', 'OK', { duration: 3000 });
        this.load();
      });
  }

  private load(): void {
    this.loading.set(true);
    this.api.templates(this.showInactive()).subscribe({
      next: (rows) => {
        this.templates.set(rows);
        this.loading.set(false);
      },
      error: () => this.loading.set(false),
    });
  }
}
