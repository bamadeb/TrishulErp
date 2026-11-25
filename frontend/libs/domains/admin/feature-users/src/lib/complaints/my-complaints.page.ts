import {
  ChangeDetectionStrategy,
  Component,
  DestroyRef,
  inject,
  signal,
} from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { MatButton } from '@angular/material/button';
import { MatSlideToggle } from '@angular/material/slide-toggle';
import { MatFormField, MatLabel, MatPrefix } from '@angular/material/form-field';
import { MatIcon } from '@angular/material/icon';
import { MatInput } from '@angular/material/input';
import { PageEvent } from '@angular/material/paginator';
import { MatOption, MatSelect } from '@angular/material/select';
import { Sort } from '@angular/material/sort';
import { RouterLink } from '@angular/router';
import { Subject, debounceTime, distinctUntilChanged } from 'rxjs';
import {
  COMPLAINT_STATUSES,
  ComplaintListItem,
  ComplaintStatus,
  ComplaintsApi,
  MyComplaintQuery,
} from '@trishul/admin-data-access';
import { PageHeader } from '@trishul/shared-ui';
import { ComplaintTable, sortParam } from './complaint-table';

/** The signed-in user's own complaints, newest first. */
@Component({
  selector: 'trishul-my-complaints-page',
  imports: [
    RouterLink,
    MatButton,
    MatIcon,
    MatFormField,
    MatLabel,
    MatPrefix,
    MatInput,
    MatSelect,
    MatOption,
    MatSlideToggle,
    PageHeader,
    ComplaintTable,
  ],
  changeDetection: ChangeDetectionStrategy.OnPush,
  styleUrl: './complaints.scss',
  template: `
    <trishul-page-header
      title="My complaints"
      subtitle="Complaints you raised, their status and the department's replies"
    >
      <a mat-flat-button routerLink="/complaints/new">
        <mat-icon>add</mat-icon>
        Raise complaint
      </a>
    </trishul-page-header>

    <div class="filters">
      <mat-form-field
        class="search"
        appearance="outline"
        subscriptSizing="dynamic"
      >
        <mat-icon matPrefix>search</mat-icon>
        <input
          matInput
          type="search"
          placeholder="Complaint ID or text"
          aria-label="Search my complaints"
          (input)="onSearch($any($event.target).value)"
        />
      </mat-form-field>
      <mat-form-field appearance="outline" subscriptSizing="dynamic">
        <mat-label>Status</mat-label>
        <mat-select
          [value]="query().status?.[0] ?? null"
          (valueChange)="setStatus($event)"
        >
          <mat-option [value]="null">Any status</mat-option>
          @for (s of statuses; track s) {
            <mat-option [value]="s">{{ s }}</mat-option>
          }
        </mat-select>
      </mat-form-field>
      <mat-slide-toggle
        [checked]="query().openOnly ?? false"
        (change)="update({ openOnly: $event.checked })"
      >
        Open only
      </mat-slide-toggle>
    </div>

    @if (failed()) {
      <p class="error" role="alert">
        Your complaints could not be loaded.
        <button mat-button type="button" (click)="load()">Retry</button>
      </p>
    }

    <trishul-complaint-table
      [items]="items()"
      [total]="total()"
      [page]="query().page ?? 1"
      [pageSize]="query().pageSize ?? 20"
      [loading]="loading()"
      [showRaisedBy]="false"
      emptyText="You have not raised any complaints yet."
      (sortChange)="onSort($event)"
      (pageChange)="onPage($event)"
    />
  `,
})
export class MyComplaintsPage {
  private readonly api = inject(ComplaintsApi);
  private readonly destroyRef = inject(DestroyRef);

  protected readonly statuses = COMPLAINT_STATUSES;
  protected readonly query = signal<MyComplaintQuery>({
    page: 1,
    pageSize: 20,
  });
  protected readonly items = signal<ComplaintListItem[]>([]);
  protected readonly total = signal(0);
  protected readonly loading = signal(false);
  protected readonly failed = signal(false);
  private readonly search$ = new Subject<string>();

  constructor() {
    this.search$
      .pipe(debounceTime(350), distinctUntilChanged(), takeUntilDestroyed())
      .subscribe((search) => this.update({ search: search || undefined }));
    this.load();
  }

  protected load(): void {
    this.loading.set(true);
    this.failed.set(false);
    this.api
      .mine(this.query())
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: (page) => {
          this.items.set(page.items);
          this.total.set(page.total);
          this.loading.set(false);
        },
        error: () => {
          this.failed.set(true);
          this.loading.set(false);
        },
      });
  }

  protected update(changes: Partial<MyComplaintQuery>): void {
    this.query.update((q) => ({ ...q, page: 1, ...changes }));
    this.load();
  }

  protected setStatus(status: ComplaintStatus | null): void {
    this.update({ status: status ? [status] : undefined });
  }

  protected onSearch(value: string): void {
    this.search$.next(value.trim());
  }

  protected onSort(sort: Sort): void {
    this.update({ sort: sortParam(sort) });
  }

  protected onPage(event: PageEvent): void {
    this.query.update((q) => ({
      ...q,
      page: event.pageIndex + 1,
      pageSize: event.pageSize,
    }));
    this.load();
  }
}
