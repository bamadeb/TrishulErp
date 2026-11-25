import {
  ChangeDetectionStrategy,
  Component,
  DestroyRef,
  inject,
  signal,
} from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { MatButton } from '@angular/material/button';
import { provideNativeDateAdapter } from '@angular/material/core';
import {
  MatDatepicker,
  MatDatepickerInput,
  MatDatepickerToggle,
} from '@angular/material/datepicker';
import {
  MatFormField,
  MatLabel,
  MatPrefix,
  MatSuffix,
} from '@angular/material/form-field';
import { MatIcon } from '@angular/material/icon';
import { MatInput } from '@angular/material/input';
import { PageEvent } from '@angular/material/paginator';
import { MatOption, MatSelect } from '@angular/material/select';
import { MatSlideToggle } from '@angular/material/slide-toggle';
import { Sort } from '@angular/material/sort';
import { RouterLink } from '@angular/router';
import { Subject, debounceTime, distinctUntilChanged } from 'rxjs';
import {
  COMPLAINT_MANAGE_ALL_PERMISSION,
  COMPLAINT_STATUSES,
  ComplaintDepartmentRef,
  ComplaintListItem,
  ComplaintQuery,
  ComplaintStatus,
  ComplaintsApi,
} from '@trishul/admin-data-access';
import { HasPermission } from '@trishul/core-auth';
import { PageHeader } from '@trishul/shared-ui';
import { ComplaintTable, sortParam } from './complaint-table';

/** A date picked in the browser as yyyy-mm-dd (an Indian calendar date for the API). */
function isoDate(value: Date | null): string | undefined {
  if (!value) return undefined;
  const month = String(value.getMonth() + 1).padStart(2, '0');
  const day = String(value.getDate()).padStart(2, '0');
  return `${value.getFullYear()}-${month}-${day}`;
}

/** Complaints of the departments the user leads (every department for a Super Admin). */
@Component({
  selector: 'trishul-department-complaints-page',
  imports: [
    RouterLink,
    MatButton,
    MatIcon,
    MatFormField,
    MatLabel,
    MatPrefix,
    MatSuffix,
    MatInput,
    MatSelect,
    MatOption,
    MatSlideToggle,
    MatDatepicker,
    MatDatepickerInput,
    MatDatepickerToggle,
    HasPermission,
    PageHeader,
    ComplaintTable,
  ],
  providers: [provideNativeDateAdapter()],
  changeDetection: ChangeDetectionStrategy.OnPush,
  styleUrl: './complaints.scss',
  template: `
    <trishul-page-header
      title="Department complaints"
      [subtitle]="subtitle()"
    >
      <a
        mat-stroked-button
        routerLink="/complaints/issue-types"
        *trishulHasPermission="manageAll"
      >
        <mat-icon>category</mat-icon>
        Issue types
      </a>
    </trishul-page-header>

    @if (noAccess()) {
      <p class="notice" role="status">
        <mat-icon>info</mat-icon>
        You do not lead a department, so there are no complaints to manage
        here. HR sets each department's head in Organization; an administrator
        can give a role the "Manage department complaints" permission.
      </p>
    } @else {
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
            placeholder="Complaint ID, text, employee name or code"
            aria-label="Search complaints"
            (input)="onSearch($any($event.target).value)"
          />
        </mat-form-field>
        @if (departments().length > 1) {
          <mat-form-field appearance="outline" subscriptSizing="dynamic">
            <mat-label>Department</mat-label>
            <mat-select
              [value]="query().departmentId ?? null"
              (valueChange)="update({ departmentId: $event ?? undefined })"
            >
              <mat-option [value]="null">All my departments</mat-option>
              @for (d of departments(); track d.id) {
                <mat-option [value]="d.id">{{ d.name }}</mat-option>
              }
            </mat-select>
          </mat-form-field>
        }
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
        <mat-form-field appearance="outline" subscriptSizing="dynamic">
          <mat-label>Raised from</mat-label>
          <input
            matInput
            [matDatepicker]="fromPicker"
            (dateChange)="update({ raisedFrom: iso($event.value) })"
          />
          <mat-datepicker-toggle matSuffix [for]="fromPicker" />
          <mat-datepicker #fromPicker />
        </mat-form-field>
        <mat-form-field appearance="outline" subscriptSizing="dynamic">
          <mat-label>Raised to</mat-label>
          <input
            matInput
            [matDatepicker]="toPicker"
            (dateChange)="update({ raisedTo: iso($event.value) })"
          />
          <mat-datepicker-toggle matSuffix [for]="toPicker" />
          <mat-datepicker #toPicker />
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
          The complaints could not be loaded.
          <button mat-button type="button" (click)="load()">Retry</button>
        </p>
      }

      <trishul-complaint-table
        [items]="items()"
        [total]="total()"
        [page]="query().page ?? 1"
        [pageSize]="query().pageSize ?? 20"
        [loading]="loading()"
        (sortChange)="onSort($event)"
        (pageChange)="onPage($event)"
      />
    }
  `,
})
export class DepartmentComplaintsPage {
  private readonly api = inject(ComplaintsApi);
  private readonly destroyRef = inject(DestroyRef);

  protected readonly manageAll = COMPLAINT_MANAGE_ALL_PERMISSION;
  protected readonly statuses = COMPLAINT_STATUSES;
  protected readonly iso = isoDate;
  protected readonly query = signal<ComplaintQuery>({
    page: 1,
    pageSize: 20,
    openOnly: true,
  });
  protected readonly items = signal<ComplaintListItem[]>([]);
  protected readonly total = signal(0);
  protected readonly loading = signal(false);
  protected readonly failed = signal(false);
  protected readonly noAccess = signal(false);
  protected readonly departments = signal<ComplaintDepartmentRef[]>([]);
  protected readonly subtitle = signal('Complaints raised to your department');
  private readonly search$ = new Subject<string>();

  constructor() {
    this.search$
      .pipe(debounceTime(350), distinctUntilChanged(), takeUntilDestroyed())
      .subscribe((search) => this.update({ search: search || undefined }));
    this.api
      .access()
      .pipe(takeUntilDestroyed())
      .subscribe((access) => {
        this.departments.set(access.managedDepartments);
        if (!access.managedDepartments.length) {
          this.noAccess.set(true);
          return;
        }
        this.subtitle.set(
          access.canManageAll
            ? 'Complaints raised to every department'
            : `Complaints raised to ${access.managedDepartments.map((d) => d.name).join(', ')}`,
        );
        this.load();
      });
  }

  protected load(): void {
    this.loading.set(true);
    this.failed.set(false);
    this.api
      .list(this.query())
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

  protected update(changes: Partial<ComplaintQuery>): void {
    this.query.update((q) => ({ ...q, page: 1, ...changes }));
    this.load();
  }

  protected setStatus(status: ComplaintStatus | null): void {
    // Picking a status shows it whether or not it is open.
    this.update({
      status: status ? [status] : undefined,
      openOnly: status ? false : this.query().openOnly,
    });
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
