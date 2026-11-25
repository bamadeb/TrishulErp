import { DatePipe } from '@angular/common';
import {
  ChangeDetectionStrategy,
  Component,
  computed,
  input,
  output,
} from '@angular/core';
import { MatIcon } from '@angular/material/icon';
import { MatPaginator, PageEvent } from '@angular/material/paginator';
import { MatProgressBar } from '@angular/material/progress-bar';
import { MatSort, MatSortHeader, Sort } from '@angular/material/sort';
import { MatTableModule } from '@angular/material/table';
import { RouterLink } from '@angular/router';
import {
  ComplaintListItem,
  ComplaintStatus,
} from '@trishul/admin-data-access';
import { StatusBadge, StatusSeverity } from '@trishul/shared-ui';

export const COMPLAINT_STATUS_SEVERITY: Record<ComplaintStatus, StatusSeverity> =
  {
    Open: 'warn',
    'In Progress': 'info',
    'On Hold': 'neutral',
    Resolved: 'success',
    Closed: 'contrast',
  };

/** Sorting the table asks the API for: a field name, '-' first for newest/highest first. */
export function sortParam(sort: Sort): string | undefined {
  if (!sort.direction) return undefined;
  return `${sort.direction === 'desc' ? '-' : ''}${sort.active}`;
}

/** A page of complaints; the number opens the complaint. Shared by My complaints and Department complaints. */
@Component({
  selector: 'trishul-complaint-table',
  imports: [
    DatePipe,
    RouterLink,
    MatTableModule,
    MatSort,
    MatSortHeader,
    MatPaginator,
    MatProgressBar,
    MatIcon,
    StatusBadge,
  ],
  changeDetection: ChangeDetectionStrategy.OnPush,
  styleUrl: './complaints.scss',
  template: `
    <div class="table-card">
      <div class="progress">
        @if (loading()) {
          <mat-progress-bar mode="indeterminate" />
        }
      </div>
      <div class="table-scroll">
        <table
          mat-table
          [dataSource]="items()"
          matSort
          matSortActive="raisedAt"
          matSortDirection="desc"
          (matSortChange)="sortChange.emit($event)"
        >
          <ng-container matColumnDef="complaintNo">
            <th mat-header-cell *matHeaderCellDef mat-sort-header>
              Complaint ID
            </th>
            <td mat-cell *matCellDef="let c">
              <a class="name" [routerLink]="['/complaints', c.id]">{{
                c.complaintNo
              }}</a>
              @if (c.attachmentCount > 0) {
                <span
                  class="muted clip"
                  [attr.aria-label]="c.attachmentCount + ' attachments'"
                >
                  <mat-icon inline>attach_file</mat-icon>{{ c.attachmentCount }}
                </span>
              }
            </td>
          </ng-container>

          <ng-container matColumnDef="raisedAt">
            <th mat-header-cell *matHeaderCellDef mat-sort-header>Raised</th>
            <td mat-cell *matCellDef="let c" class="nowrap">
              {{ c.raisedAt | date: 'dd MMM yyyy, hh:mm a' }}
            </td>
          </ng-container>

          <ng-container matColumnDef="raisedBy">
            <th mat-header-cell *matHeaderCellDef>Raised by</th>
            <td mat-cell *matCellDef="let c">
              {{ c.raisedByName }}
              @if (c.raisedByEmployeeCode) {
                <div class="muted">{{ c.raisedByEmployeeCode }}</div>
              }
            </td>
          </ng-container>

          <ng-container matColumnDef="department">
            <th mat-header-cell *matHeaderCellDef>Department</th>
            <td mat-cell *matCellDef="let c">{{ c.departmentName }}</td>
          </ng-container>

          <ng-container matColumnDef="issue">
            <th mat-header-cell *matHeaderCellDef>Issue</th>
            <td mat-cell *matCellDef="let c">
              <div class="issue">{{ c.issueTypeName }}</div>
              <div class="muted ellipsis" [title]="c.description">
                {{ c.description }}
              </div>
            </td>
          </ng-container>

          <ng-container matColumnDef="status">
            <th mat-header-cell *matHeaderCellDef mat-sort-header>Status</th>
            <td mat-cell *matCellDef="let c">
              <trishul-status-badge
                [status]="c.status"
                [severities]="severity"
              />
              @if (c.statusChangedAt) {
                <div class="muted nowrap">
                  {{ c.statusChangedAt | date: 'dd MMM, hh:mm a' }}
                </div>
              }
            </td>
          </ng-container>

          <tr mat-header-row *matHeaderRowDef="columns(); sticky: true"></tr>
          <tr mat-row *matRowDef="let row; columns: columns()"></tr>
          <tr class="mat-mdc-row" *matNoDataRow>
            <td class="empty" [attr.colspan]="columns().length">
              {{ loading() ? 'Loading…' : emptyText() }}
            </td>
          </tr>
        </table>
      </div>
      <mat-paginator
        [length]="total()"
        [pageIndex]="page() - 1"
        [pageSize]="pageSize()"
        [pageSizeOptions]="[20, 50, 100]"
        aria-label="Pages of complaints"
        (page)="pageChange.emit($event)"
      />
    </div>
  `,
})
export class ComplaintTable {
  readonly items = input.required<ComplaintListItem[]>();
  readonly total = input(0);
  readonly page = input(1);
  readonly pageSize = input(20);
  readonly loading = input(false);
  /** My complaints leaves out who raised it; Department complaints shows it. */
  readonly showRaisedBy = input(true);
  readonly emptyText = input('No complaints match these filters.');
  readonly sortChange = output<Sort>();
  readonly pageChange = output<PageEvent>();

  protected readonly severity = COMPLAINT_STATUS_SEVERITY;
  protected readonly columns = computed(() =>
    this.showRaisedBy()
      ? ['complaintNo', 'raisedAt', 'raisedBy', 'department', 'issue', 'status']
      : ['complaintNo', 'raisedAt', 'department', 'issue', 'status'],
  );
}
