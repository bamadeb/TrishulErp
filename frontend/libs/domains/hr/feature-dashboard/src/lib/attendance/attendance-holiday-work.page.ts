import { DatePipe } from '@angular/common';
import { HttpErrorResponse } from '@angular/common/http';
import { ChangeDetectionStrategy, Component, OnInit, computed, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { MatButton } from '@angular/material/button';
import { provideNativeDateAdapter } from '@angular/material/core';
import { MatDatepicker, MatDatepickerInput, MatDatepickerToggle } from '@angular/material/datepicker';
import { MatFormField, MatSuffix } from '@angular/material/form-field';
import { MatIcon } from '@angular/material/icon';
import { MatInput } from '@angular/material/input';
import { MatSnackBar } from '@angular/material/snack-bar';
import { ActivatedRoute, Router, RouterLink } from '@angular/router';
import { AttendanceApi, CompOffAuthorizationItem, CompOffReport, LeaveApi, MineHoliday } from '@trishul/hr-data-access';
import { catchError, of } from 'rxjs';

const MAX_FILE = 5 * 1024 * 1024;

const KIND_LABEL: Record<string, string> = {
  WEEKLY_OFF: 'Weekly off',
  COMPANY_HOLIDAY: 'Company holiday',
  NON_WORKING: 'Declared non-working day',
};

/** Employee request for work done on a declared holiday. Reuses regularization submit. */
@Component({
  selector: 'trishul-attendance-holiday-work-page',
  imports: [
    DatePipe,
    FormsModule,
    MatButton,
    MatDatepicker,
    MatDatepickerInput,
    MatDatepickerToggle,
    MatFormField,
    MatSuffix,
    MatIcon,
    MatInput,
    RouterLink,
  ],
  providers: [provideNativeDateAdapter()],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './attendance-holiday-work.page.html',
  styleUrl: './attendance-holiday-work.page.scss',
})
export class AttendanceHolidayWorkPage implements OnInit {
  private readonly attendance = inject(AttendanceApi);
  private readonly leave = inject(LeaveApi);
  private readonly snackBar = inject(MatSnackBar);
  private readonly router = inject(Router);
  private readonly route = inject(ActivatedRoute);

  protected readonly holidays = signal<MineHoliday[]>([]);
  protected readonly authorizations = signal<CompOffAuthorizationItem[]>([]);
  protected readonly reports = signal<CompOffReport[]>([]);
  protected readonly eligibleDates = signal<string[]>([]);
  protected readonly holidayDate = signal<Date | null>(null);
  protected readonly punchIn = signal('09:00');
  protected readonly punchOut = signal('18:00');
  protected readonly reason = signal('');
  protected readonly authorizeCode = signal('');
  protected readonly authorizeDate = signal('');
  protected readonly authorizeNote = signal('');
  protected readonly authorizing = signal(false);
  protected readonly fileName = signal<string | null>(null);
  protected readonly fileSize = signal<string | null>(null);
  protected readonly submitting = signal(false);
  protected readonly loadError = signal<string | null>(null);
  /** Filled from GET /hr/attendance/mine for the signed-in employee — never a hardcoded id. */
  private employeeId: number | null = null;

  protected readonly selected = computed(() => {
    const day = this.holidayDate();
    if (!day) return null;
    const iso = toIso(day);
    return this.holidays().find((item) => item.holidayDate.slice(0, 10) === iso) ?? null;
  });

  protected readonly chosen = computed(() => {
    const day = this.holidayDate();
    if (!day) return null;
    const iso = toIso(day);
    return this.authorizations().find((item) => item.workDate.slice(0, 10) === iso && item.status === 'Authorized') ?? null;
  });

  protected readonly canSubmit = computed(
    () =>
      (!!this.selected() || this.isEligibleDate(this.holidayDate())) &&
      !!this.punchIn() &&
      !!this.punchOut() &&
      this.reason().trim().length > 0 &&
      !this.submitting(),
  );

  ngOnInit(): void {
    const today = new Date();
    const year = today.getMonth() >= 3 ? today.getFullYear() : today.getFullYear() - 1;
    const requested = this.route.snapshot.queryParamMap.get('date');
    if (requested && /^\d{4}-\d{2}-\d{2}$/.test(requested)) {
      this.eligibleDates.update((rows) => (rows.includes(requested) ? rows : [...rows, requested]));
      this.holidayDate.set(parseIso(requested));
    }
    this.leave
      .mineHolidays(year)
      .pipe(catchError(() => of([] as MineHoliday[])))
      .subscribe((rows) => {
        const holidays = [...rows].sort((a, b) => a.holidayDate.localeCompare(b.holidayDate));
        this.holidays.set(holidays);
        if (!holidays.length && !this.eligibleDates().length) {
          this.loadError.set('No declared holidays were found for this year.');
        }
        if (!this.holidayDate()) {
          const upcoming =
            holidays.find((item) => item.holidayDate.slice(0, 10) >= toIso(today)) ?? holidays[0];
          if (upcoming) this.holidayDate.set(parseIso(upcoming.holidayDate));
        }
      });
    this.loadAuthorizations();
    this.leave.compOffReports().subscribe({
      next: (rows) => this.reports.set(rows),
      error: () => this.reports.set([]),
    });
    const month = requested ? Number(requested.slice(5, 7)) : today.getMonth() + 1;
    const forYear = requested ? Number(requested.slice(0, 4)) : today.getFullYear();
    this.attendance.mine(forYear, month).subscribe({
      next: (page) => {
        if (page.employeeId) this.employeeId = page.employeeId;
        const eligible = page.items
          .filter(
            (row) =>
              (row.status === 'Holiday' || row.status === 'Off Day') &&
              !!row.firstIn &&
              !!row.lastOut,
          )
          .map((row) => row.date.slice(0, 10));
        this.eligibleDates.update((rows) => [...new Set([...rows, ...eligible])]);
        const match = requested
          ? page.items.find((row) => row.date.slice(0, 10) === requested)
          : null;
        if (match?.firstIn) this.punchIn.set(clockToInput(match.firstIn));
        if (match?.lastOut) this.punchOut.set(clockToInput(match.lastOut));
      },
      error: () => undefined,
    });
  }

  protected holidayOnly = (date: Date | null): boolean => {
    if (!date) return false;
    const iso = toIso(date);
    return (
      this.holidays().some((item) => item.holidayDate.slice(0, 10) === iso) ||
      this.eligibleDates().includes(iso)
    );
  };

  private isEligibleDate(value: Date | null): boolean {
    if (!value) return false;
    return this.eligibleDates().includes(toIso(value));
  }

  private loadAuthorizations(): void {
    this.leave.compOffAuthorizations('mine').subscribe({
      next: (rows) => this.authorizations.set(rows),
      error: () => this.authorizations.set([]),
    });
  }

  protected kindLabel(value: string): string {
    return KIND_LABEL[value] ?? value;
  }

  protected authorize(): void {
    const workDate = this.authorizeDate();
    const code = this.authorizeCode().trim();
    if (!workDate || !code || this.authorizing()) return;
    const report = this.reports().find((item) => item.employeeCode.toLowerCase() === code.toLowerCase());
    this.authorizing.set(true);
    this.leave
      .authorizeCompOff({
        employeeId: report?.employeeId ?? null,
        employeeCode: report ? null : code,
        workDate,
        remarks: this.authorizeNote().trim() || null,
      })
      .subscribe({
        next: () => {
          this.authorizing.set(false);
          this.authorizeNote.set('');
          this.snackBar.open('Holiday or weekly-off work authorized.', 'OK', { duration: 2500 });
          this.loadAuthorizations();
        },
        error: (err: unknown) => {
          this.authorizing.set(false);
          this.snackBar.open(messageFrom(err), 'OK', { duration: 4000 });
        },
      });
  }

  protected typeLabel(value: string | undefined): string {
    if (!value) return 'Holiday';
    if (/company/i.test(value)) return 'Company Holiday';
    return value.endsWith('Holiday') ? value : `${value} Holiday`;
  }

  protected onFile(event: Event): void {
    const file = (event.target as HTMLInputElement).files?.[0];
    if (!file) return;
    const allowed = ['application/pdf', 'image/jpeg', 'image/png'];
    if (!allowed.includes(file.type)) {
      this.snackBar.open('Attach a PDF, JPG, or PNG file.', 'OK', { duration: 3000 });
      return;
    }
    if (file.size > MAX_FILE) {
      this.snackBar.open('Attachment must be 5 MB or smaller.', 'OK', { duration: 3000 });
      return;
    }
    this.fileName.set(file.name);
    this.fileSize.set(file.size < 1024 * 1024 ? `${Math.max(1, Math.round(file.size / 1024))} KB` : `${(file.size / (1024 * 1024)).toFixed(1)} MB`);
  }

  protected clearFile(): void {
    this.fileName.set(null);
    this.fileSize.set(null);
  }

  protected submit(): void {
    const day = this.holidayDate();
    const employeeId = this.employeeId;
    if ((!this.selected() && !this.isEligibleDate(day)) || !day || !this.canSubmit()) return;
    if (employeeId == null) {
      this.snackBar.open('Your employee profile could not be resolved. Sign in again and retry.', 'OK', {
        duration: 4000,
      });
      return;
    }
    const reason = `Compensation: Compensatory Off (Comp Off)\n${this.reason().trim()}`.slice(0, 250);
    this.submitting.set(true);
    this.attendance
      .createMineRegularization({
        employeeId,
        attendanceDate: toIso(day),
        requestType: 'Holiday Work',
        requestedIn: clockLabel(this.punchIn()),
        requestedOut: clockLabel(this.punchOut()),
        reason,
        attachmentName: this.fileName(),
      })
      .subscribe({
        next: () => {
          this.submitting.set(false);
          this.snackBar.open('Holiday work request submitted.', 'OK', { duration: 2500 });
          void this.router.navigate(['/hr/attendance/my-regularization']);
        },
        error: (err: unknown) => {
          this.submitting.set(false);
          this.snackBar.open(messageFrom(err), 'OK', { duration: 4000 });
        },
      });
  }
}

function toIso(value: Date): string {
  const year = value.getFullYear();
  const month = String(value.getMonth() + 1).padStart(2, '0');
  const day = String(value.getDate()).padStart(2, '0');
  return `${year}-${month}-${day}`;
}

function parseIso(value: string): Date {
  const [year, month, day] = value.slice(0, 10).split('-').map(Number);
  return new Date(year!, (month ?? 1) - 1, day ?? 1);
}

function clockToInput(value: string): string {
  const match = value.trim().match(/^(\d{1,2}):(\d{2})\s*(AM|PM)?$/i);
  if (!match) return value.includes(':') ? value.slice(0, 5) : '09:00';
  let hour = Number(match[1]);
  const minute = match[2] ?? '00';
  const suffix = (match[3] || '').toUpperCase();
  if (suffix === 'PM' && hour < 12) hour += 12;
  if (suffix === 'AM' && hour === 12) hour = 0;
  return `${String(hour).padStart(2, '0')}:${minute}`;
}

function clockLabel(value: string): string {
  const [hourText, minuteText] = value.split(':');
  const hour = Number(hourText);
  const minute = Number(minuteText ?? 0);
  if (!Number.isFinite(hour)) return value;
  const suffix = hour >= 12 ? 'PM' : 'AM';
  const hour12 = hour % 12 || 12;
  return `${String(hour12).padStart(2, '0')}:${String(minute).padStart(2, '0')} ${suffix}`;
}

function messageFrom(err: unknown): string {
  if (err instanceof HttpErrorResponse) {
    const detail = (err.error as { detail?: unknown } | null)?.detail;
    if (typeof detail === 'string') return detail;
  }
  return 'Could not submit the holiday work request.';
}
