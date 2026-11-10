import { DatePipe } from '@angular/common';
import { ChangeDetectionStrategy, Component, inject, signal } from '@angular/core';
import { FormControl, ReactiveFormsModule } from '@angular/forms';
import { MatIconButton } from '@angular/material/button';
import { MatFormField, MatLabel, MatSuffix } from '@angular/material/form-field';
import { MatIcon } from '@angular/material/icon';
import { MatInput } from '@angular/material/input';
import { MatProgressBar } from '@angular/material/progress-bar';
import { MatOption, MatSelect } from '@angular/material/select';
import { MatTooltip } from '@angular/material/tooltip';
import { RouterLink } from '@angular/router';
import { debounceTime, startWith, switchMap, tap } from 'rxjs';
import { ServiceReportApi, ServiceReportListItem } from '@trishul/service-data-access';
import { PageHeader, StatusBadge, StatusSeverity } from '@trishul/shared-ui';

/** Service > Service reports: find the inspection and service report of any call by report no, call no or customer. */
@Component({
  selector: 'trishul-service-reports-list-page',
  imports: [
    DatePipe,
    RouterLink,
    ReactiveFormsModule,
    MatFormField,
    MatLabel,
    MatSuffix,
    MatIcon,
    MatIconButton,
    MatInput,
    MatProgressBar,
    MatSelect,
    MatOption,
    MatTooltip,
    PageHeader,
    StatusBadge,
  ],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <trishul-page-header
      title="Service reports"
      subtitle="Inspection and service reports submitted by the engineers"
    />
    @if (loading()) {
      <mat-progress-bar mode="indeterminate" />
    }
    <div class="filters">
      <mat-form-field appearance="outline" class="search">
        <mat-label>Search by report no, call no or customer</mat-label>
        <input matInput [formControl]="search" />
        <mat-icon matSuffix>search</mat-icon>
      </mat-form-field>
      <mat-form-field appearance="outline">
        <mat-label>Status</mat-label>
        <mat-select [formControl]="status">
          <mat-option [value]="null">All</mat-option>
          <mat-option value="Draft">Draft</mat-option>
          <mat-option value="Submitted">Submitted</mat-option>
        </mat-select>
      </mat-form-field>
    </div>
    <table class="list">
      <thead>
        <tr>
          <th>Report</th>
          <th>Service call</th>
          <th>Customer</th>
          <th>Engineer</th>
          <th>Status</th>
          <th>Outcome</th>
          <th>Submitted</th>
          <th></th>
        </tr>
      </thead>
      <tbody>
        @for (r of rows(); track r.id) {
          <tr>
            <td>{{ r.reportNo }}</td>
            <td>
              <a [routerLink]="['/service/calls', r.serviceCallId]">{{ r.callNo }}</a>
            </td>
            <td>{{ r.customerName }}</td>
            <td>{{ r.engineerName ?? '—' }}</td>
            <td><trishul-status-badge [status]="r.status" [severities]="severity" /></td>
            <td>{{ r.nextAction ?? '—' }}</td>
            <td>{{ r.submittedAt ? (r.submittedAt | date: 'dd MMM yyyy, HH:mm') : '—' }}</td>
            <td class="end">
              <a
                mat-icon-button
                matTooltip="Open the report"
                [routerLink]="['/service/calls', r.serviceCallId, 'visits', r.serviceVisitId, 'report']"
              >
                <mat-icon>visibility</mat-icon>
              </a>
            </td>
          </tr>
        } @empty {
          <tr>
            <td colspan="8" class="empty">{{ loading() ? 'Loading…' : 'No service reports found.' }}</td>
          </tr>
        }
      </tbody>
    </table>
  `,
  styles: `
    .filters {
      display: flex;
      flex-wrap: wrap;
      gap: 0 1rem;
      margin-top: 0.5rem;
    }
    .search {
      flex: 1 1 22rem;
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
    .empty {
      text-align: center;
      color: var(--mat-sys-on-surface-variant);
    }
  `,
})
export class ServiceReportsListPage {
  private readonly api = inject(ServiceReportApi);

  protected readonly severity: Record<string, StatusSeverity> = { Draft: 'warn', Submitted: 'success' };
  protected readonly loading = signal(true);
  protected readonly rows = signal<ServiceReportListItem[]>([]);
  protected readonly search = new FormControl('', { nonNullable: true });
  protected readonly status = new FormControl<'Draft' | 'Submitted' | null>(null);

  constructor() {
    const text$ = this.search.valueChanges.pipe(startWith(this.search.value), debounceTime(300));
    text$
      .pipe(
        switchMap((text) =>
          this.status.valueChanges.pipe(
            startWith(this.status.value),
            tap(() => this.loading.set(true)),
            switchMap((status) => this.api.searchReports(text, status ?? undefined)),
          ),
        ),
      )
      .subscribe({
        next: (rows) => {
          this.rows.set(rows);
          this.loading.set(false);
        },
        error: () => this.loading.set(false),
      });
  }
}
