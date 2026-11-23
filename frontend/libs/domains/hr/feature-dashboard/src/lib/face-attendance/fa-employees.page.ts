import {
  ChangeDetectionStrategy,
  Component,
  OnInit,
  computed,
  inject,
  signal,
} from '@angular/core';
import { FormsModule } from '@angular/forms';
import { MatButton, MatIconButton } from '@angular/material/button';
import { MatCheckbox } from '@angular/material/checkbox';
import { MatDialog } from '@angular/material/dialog';
import {
  MatFormField,
  MatLabel,
  MatPrefix,
} from '@angular/material/form-field';
import { MatIcon } from '@angular/material/icon';
import { MatInput } from '@angular/material/input';
import { MatPaginator, PageEvent } from '@angular/material/paginator';
import { MatProgressBar } from '@angular/material/progress-bar';
import { MatOption, MatSelect } from '@angular/material/select';
import { MatSnackBar } from '@angular/material/snack-bar';
import { MatTooltip } from '@angular/material/tooltip';
import { AuthStore } from '@trishul/core-auth';
import {
  AttendanceEmployee,
  AttendancePolicy,
  FACE_ATTENDANCE_MANAGE_PERMISSION,
  FACE_REGISTER_PERMISSION,
  FaceAttendanceApi,
  WorkLocation,
} from '@trishul/hr-data-access';
import { StatusBadge } from '@trishul/shared-ui';
import { forkJoin } from 'rxjs';
import {
  FaAssignPolicyDialog,
  FaAssignPolicyDialogData,
} from './fa-assign-policy.dialog';
import {
  FaRegisterFaceDialog,
  FaRegisterFaceDialogData,
} from './fa-register-face.dialog';
import { FACE_STATUS_SEVERITIES } from './face-attendance.shared';

type Readiness = '' | 'ready' | 'no-policy' | 'no-face' | 'pending-face';

/** Every active employee with today's policy and face status: what still stops them from punching. */
@Component({
  selector: 'trishul-fa-employees-page',
  imports: [
    FormsModule,
    MatButton,
    MatCheckbox,
    MatFormField,
    MatIcon,
    MatIconButton,
    MatInput,
    MatLabel,
    MatOption,
    MatPaginator,
    MatPrefix,
    MatProgressBar,
    MatSelect,
    MatTooltip,
    StatusBadge,
  ],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    @if (loading()) {
      <mat-progress-bar mode="indeterminate" />
    }
    @if (error()) {
      <p class="error">{{ error() }}</p>
    }
    <section class="panel">
      <div class="panel-head">
        <div>
          <h2>Employees</h2>
          <p>
            {{ readyCount() }} of {{ rows().length }} can punch from the app. An
            employee needs a policy and an approved face.
          </p>
        </div>
        @if (canManage() && selected().size) {
          <button
            mat-flat-button
            type="button"
            (click)="assign(selectedRows())"
          >
            <mat-icon>rule</mat-icon>
            Set policy for {{ selected().size }} selected
          </button>
        }
      </div>

      <div class="filters">
        <mat-form-field appearance="outline" subscriptSizing="dynamic">
          <mat-icon matPrefix>search</mat-icon>
          <input
            matInput
            type="search"
            placeholder="Search name or code"
            [ngModel]="search()"
            (ngModelChange)="search.set($event); page.set(0)"
          />
        </mat-form-field>
        <mat-form-field appearance="outline" subscriptSizing="dynamic">
          <mat-label>Branch</mat-label>
          <mat-select
            [ngModel]="branch()"
            (ngModelChange)="branch.set($event); page.set(0)"
          >
            <mat-option [value]="0">All branches</mat-option>
            @for (b of branches(); track b.id) {
              <mat-option [value]="b.id">{{ b.name }}</mat-option>
            }
          </mat-select>
        </mat-form-field>
        <mat-form-field appearance="outline" subscriptSizing="dynamic">
          <mat-label>Show</mat-label>
          <mat-select
            [ngModel]="readiness()"
            (ngModelChange)="readiness.set($event); page.set(0)"
          >
            <mat-option value="">Everyone</mat-option>
            <mat-option value="ready">Ready to punch</mat-option>
            <mat-option value="no-policy">No policy</mat-option>
            <mat-option value="no-face">No face registered</mat-option>
            <mat-option value="pending-face"
              >Face waiting for approval</mat-option
            >
          </mat-select>
        </mat-form-field>
      </div>

      <div class="table-wrap">
        <table>
          <thead>
            <tr>
              @if (canManage()) {
                <th>
                  <mat-checkbox
                    [checked]="allOnPageSelected()"
                    [indeterminate]="
                      !allOnPageSelected() && someOnPageSelected()
                    "
                    (change)="togglePage($event.checked)"
                    aria-label="Select all on this page"
                  />
                </th>
              }
              <th>Employee</th>
              <th>Branch</th>
              <th>Policy</th>
              <th>Work locations</th>
              <th>Face</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            @for (row of pageRows(); track row.employeeId) {
              <tr>
                @if (canManage()) {
                  <td>
                    <mat-checkbox
                      [checked]="selected().has(row.employeeId)"
                      (change)="toggle(row.employeeId, $event.checked)"
                      [attr.aria-label]="'Select ' + row.employeeName"
                    />
                  </td>
                }
                <td>
                  <strong>{{ row.employeeName }}</strong
                  ><br />
                  <span class="muted"
                    >{{ row.employeeCode
                    }}{{
                      row.departmentName ? ' · ' + row.departmentName : ''
                    }}</span
                  >
                </td>
                <td>{{ row.branchName || '—' }}</td>
                <td>
                  @if (row.policyCode) {
                    {{ row.policyCode }}
                    <span class="muted">({{ row.policyMode }})</span>
                  } @else {
                    <span class="muted">Not set</span>
                  }
                </td>
                <td>{{ row.workLocationNames.join(', ') || '—' }}</td>
                <td>
                  <trishul-status-badge
                    [status]="row.faceStatus"
                    [severities]="faceSeverities"
                  />
                </td>
                <td class="actions-cell">
                  @if (canManage()) {
                    <button
                      mat-icon-button
                      type="button"
                      matTooltip="Set policy"
                      (click)="assign([row])"
                    >
                      <mat-icon>rule</mat-icon>
                    </button>
                  }
                  @if (canRegister()) {
                    <button
                      mat-icon-button
                      type="button"
                      [matTooltip]="
                        row.faceStatus === 'Not registered'
                          ? 'Register face'
                          : 'Register a new face'
                      "
                      (click)="registerFace(row)"
                    >
                      <mat-icon>add_a_photo</mat-icon>
                    </button>
                  }
                </td>
              </tr>
            } @empty {
              <tr>
                <td colspan="7">
                  <div class="empty">
                    <mat-icon>badge</mat-icon>
                    {{
                      loading()
                        ? 'Loading employees…'
                        : 'No employees match your filters.'
                    }}
                  </div>
                </td>
              </tr>
            }
          </tbody>
        </table>
      </div>
      <mat-paginator
        class="pager"
        [length]="filtered().length"
        [pageIndex]="page()"
        [pageSize]="pageSize()"
        [pageSizeOptions]="[10, 25, 50, 100]"
        (page)="onPage($event)"
      />
    </section>
  `,
  styleUrl: './face-attendance.shared.scss',
})
export class FaEmployeesPage implements OnInit {
  private readonly api = inject(FaceAttendanceApi);
  private readonly auth = inject(AuthStore);
  private readonly dialog = inject(MatDialog);
  private readonly snackBar = inject(MatSnackBar);

  protected readonly faceSeverities = FACE_STATUS_SEVERITIES;
  protected readonly canManage = computed(() =>
    this.auth.hasPermission(FACE_ATTENDANCE_MANAGE_PERMISSION),
  );
  protected readonly canRegister = computed(() =>
    this.auth.hasPermission(FACE_REGISTER_PERMISSION),
  );
  protected readonly loading = signal(true);
  protected readonly error = signal<string | null>(null);
  protected readonly rows = signal<AttendanceEmployee[]>([]);
  private readonly policies = signal<AttendancePolicy[]>([]);
  private readonly locations = signal<WorkLocation[]>([]);
  protected readonly search = signal('');
  protected readonly branch = signal(0);
  protected readonly readiness = signal<Readiness>('');
  protected readonly page = signal(0);
  protected readonly pageSize = signal(25);
  protected readonly selected = signal(new Set<number>());

  protected readonly branches = computed(() => {
    const seen = new Map<number, string>();
    for (const r of this.rows())
      if (r.branchId && r.branchName) seen.set(r.branchId, r.branchName);
    return [...seen]
      .map(([id, name]) => ({ id, name }))
      .sort((a, b) => a.name.localeCompare(b.name));
  });
  protected readonly readyCount = computed(
    () => this.rows().filter((r) => isReady(r)).length,
  );
  protected readonly filtered = computed(() => {
    const q = this.search().trim().toLowerCase();
    const branch = this.branch();
    const readiness = this.readiness();
    return this.rows().filter((r) => {
      if (branch && r.branchId !== branch) return false;
      if (readiness === 'ready' && !isReady(r)) return false;
      if (readiness === 'no-policy' && r.policyId) return false;
      if (
        readiness === 'no-face' &&
        r.faceStatus !== 'Not registered' &&
        r.faceStatus !== 'Rejected'
      )
        return false;
      if (readiness === 'pending-face' && r.faceStatus !== 'Pending approval')
        return false;
      return (
        !q || `${r.employeeName} ${r.employeeCode}`.toLowerCase().includes(q)
      );
    });
  });
  protected readonly pageRows = computed(() => {
    const start = this.page() * this.pageSize();
    return this.filtered().slice(start, start + this.pageSize());
  });
  protected readonly allOnPageSelected = computed(
    () =>
      this.pageRows().length > 0 &&
      this.pageRows().every((r) => this.selected().has(r.employeeId)),
  );
  protected readonly someOnPageSelected = computed(() =>
    this.pageRows().some((r) => this.selected().has(r.employeeId)),
  );
  protected readonly selectedRows = computed(() =>
    this.rows().filter((r) => this.selected().has(r.employeeId)),
  );

  ngOnInit(): void {
    this.reload();
  }

  protected onPage(event: PageEvent): void {
    this.page.set(event.pageIndex);
    this.pageSize.set(event.pageSize);
  }

  protected toggle(id: number, on: boolean): void {
    const next = new Set(this.selected());
    if (on) next.add(id);
    else next.delete(id);
    this.selected.set(next);
  }

  protected togglePage(on: boolean): void {
    const next = new Set(this.selected());
    for (const r of this.pageRows()) {
      if (on) next.add(r.employeeId);
      else next.delete(r.employeeId);
    }
    this.selected.set(next);
  }

  protected assign(employees: AttendanceEmployee[]): void {
    const data: FaAssignPolicyDialogData = {
      employees,
      policies: this.policies(),
      locations: this.locations(),
    };
    this.dialog
      .open(FaAssignPolicyDialog, { data, width: '32rem' })
      .afterClosed()
      .subscribe((saved?: boolean) => {
        if (!saved) return;
        this.snackBar.open(
          employees.length === 1
            ? 'Policy saved.'
            : `Policy saved for ${employees.length} employees.`,
          'OK',
          { duration: 3000 },
        );
        this.selected.set(new Set());
        this.reload();
      });
  }

  protected registerFace(employee: AttendanceEmployee): void {
    const data: FaRegisterFaceDialogData = { employee };
    this.dialog
      .open(FaRegisterFaceDialog, { data, width: '32rem' })
      .afterClosed()
      .subscribe((saved?: boolean) => {
        if (!saved) return;
        this.snackBar.open(
          'Face registered. A different HR user must approve it (Face approvals).',
          'OK',
          {
            duration: 5000,
          },
        );
        this.reload();
      });
  }

  private reload(): void {
    this.loading.set(true);
    this.error.set(null);
    forkJoin({
      employees: this.api.listEmployees(),
      policies: this.api.listPolicies(),
      locations: this.api.listLocations(),
    }).subscribe({
      next: ({ employees, policies, locations }) => {
        this.rows.set(employees);
        this.policies.set(policies);
        this.locations.set(locations);
        this.loading.set(false);
      },
      error: () => {
        this.error.set('Employees could not be loaded.');
        this.loading.set(false);
      },
    });
  }
}

function isReady(r: AttendanceEmployee): boolean {
  return !!r.policyId && r.faceStatus === 'Active';
}
