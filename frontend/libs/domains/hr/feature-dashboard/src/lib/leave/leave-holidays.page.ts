import { ChangeDetectionStrategy, Component, computed, ElementRef, inject, signal, viewChild } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { MatButton, MatIconButton } from '@angular/material/button';
import { provideNativeDateAdapter } from '@angular/material/core';
import { MatDatepicker, MatDatepickerInput, MatDatepickerToggle } from '@angular/material/datepicker';
import { MAT_DIALOG_DATA, MatDialog, MatDialogModule, MatDialogRef } from '@angular/material/dialog';
import { MatFormField, MatLabel, MatPrefix, MatSuffix } from '@angular/material/form-field';
import { MatIcon } from '@angular/material/icon';
import { MatInput } from '@angular/material/input';
import { MatOption, MatSelect } from '@angular/material/select';
import { MatDrawer, MatDrawerContainer, MatDrawerContent } from '@angular/material/sidenav';
import { MatSlideToggle } from '@angular/material/slide-toggle';
import { MatSnackBar } from '@angular/material/snack-bar';
import { RouterLink } from '@angular/router';
import {
  HolidayCategory,
  HolidayFilters,
  HolidayItem,
  HolidayOption,
  HolidaySummary,
  HolidayWrite,
  LeaveApi,
} from '@trishul/hr-data-access';
import { confirmAction, PageHeader, StatusBadge } from '@trishul/shared-ui';
import { forkJoin } from 'rxjs';

const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
const MONTH_NAMES = ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December'];
const WEEKDAYS = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'];
const PAGE_SIZE = 10;

interface Draft {
  id: number | null;
  rowVersion: string | null;
  name: string;
  date: Date | null;
  type: HolidayCategory | null;
  stateId: number | null;
  stateName: string | null;
  locationId: number | null;
  locationName: string;
  description: string;
  optional: boolean;
  active: boolean;
}

interface ImportRow {
  name: string;
  date: string;
  type: HolidayCategory | '';
  state: string;
  location: string;
  error: string;
}

type DrawerMode = 'add' | 'edit' | 'view';

@Component({
  selector: 'trishul-holiday-import-dialog',
  imports: [MatButton, MatDialogModule],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <h2 mat-dialog-title>Import holidays</h2>
    <mat-dialog-content>
      <p class="file">{{ data.fileName }}</p>
      <p>{{ data.note }}</p>
      @if (data.rows.length) {
        <table>
          <thead><tr><th>Name</th><th>Date</th><th>Type</th><th>Check</th></tr></thead>
          <tbody>
            @for (row of data.rows; track $index) {
              <tr>
                <td>{{ row.name || '—' }}</td>
                <td>{{ row.date || '—' }}</td>
                <td>{{ row.type || '—' }}</td>
                <td [class.bad]="row.error">{{ row.error || 'Ready' }}</td>
              </tr>
            }
          </tbody>
        </table>
      }
    </mat-dialog-content>
    <mat-dialog-actions align="end">
      <button mat-button type="button" [mat-dialog-close]="[]">Cancel</button>
      <button mat-flat-button type="button" color="primary" [disabled]="!valid.length" (click)="close()">Import {{ valid.length }} valid</button>
    </mat-dialog-actions>
  `,
  styles: `
    .file { margin: 0 0 0.35rem; font-weight: 600; }
    p { margin: 0 0 0.75rem; color: #5c6b82; }
    table { width: 100%; border-collapse: collapse; font-size: 0.82rem; }
    th, td { padding: 0.35rem 0.4rem; border-bottom: 1px solid #e3ebf6; text-align: left; }
    .bad { color: #b3261e; }
  `,
})
class HolidayImportDialog {
  private readonly ref = inject(MatDialogRef<HolidayImportDialog, ImportRow[]>);
  protected readonly data = inject<{ fileName: string; note: string; rows: ImportRow[] }>(MAT_DIALOG_DATA);
  protected readonly valid = this.data.rows.filter((row) => !row.error && row.type);

  protected close(): void {
    this.ref.close(this.valid);
  }
}

@Component({
  selector: 'trishul-leave-holidays-page',
  imports: [
    FormsModule, MatButton, MatDatepicker, MatDatepickerInput, MatDatepickerToggle, MatDrawer, MatDrawerContainer,
    MatDrawerContent, MatFormField, MatIcon, MatIconButton, MatInput, MatLabel, MatOption, MatPrefix, MatSelect,
    MatSlideToggle, MatSuffix, PageHeader, RouterLink, StatusBadge,
  ],
  providers: [provideNativeDateAdapter()],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './leave-holidays.page.html',
  styleUrl: './leave-holidays.page.scss',
})
export class LeaveHolidaysPage {
  private readonly api = inject(LeaveApi);
  private readonly dialog = inject(MatDialog);
  private readonly snack = inject(MatSnackBar);
  private readonly drawer = viewChild.required<MatDrawer>('drawer');
  private readonly fileInput = viewChild<ElementRef<HTMLInputElement>>('fileInput');
  private financialYears: number[] = [];
  private loadToken = 0;

  protected readonly weekdays = WEEKDAYS;
  protected readonly severities = { Active: 'success', Inactive: 'neutral' } as const;
  protected readonly years = signal<{ id: number; label: string }[]>([]);
  protected readonly types = signal<HolidayFilters['categories']>([]);
  protected readonly states = signal<HolidayOption[]>([]);
  protected readonly locations = signal<HolidayOption[]>([]);
  protected readonly year = signal(financialYear(new Date()));
  protected readonly basis = signal<'financial' | 'calendar'>('financial');
  protected readonly festivals = signal<string[]>([]);
  protected readonly cursor = signal(new Date(new Date().getFullYear(), new Date().getMonth(), 1));
  protected readonly selected = signal(strip(new Date()));
  protected readonly mode = signal<'calendar' | 'list'>('calendar');
  protected readonly type = signal<HolidayCategory | null>(null);
  protected readonly state = signal<number | null>(null);
  protected readonly location = signal<number | null>(null);
  protected readonly search = signal('');
  protected readonly sortAsc = signal(true);
  protected readonly pageIndex = signal(0);
  protected readonly total = signal(0);
  protected readonly pageRows = signal<HolidayItem[]>([]);
  protected readonly monthHolidays = signal<HolidayItem[]>([]);
  protected readonly summary = signal<HolidaySummary>({ total: 0, upcoming: 0, national: 0, festival: 0, regional: 0, optional: 0 });
  protected readonly loadError = signal('');
  protected readonly drawerMode = signal<DrawerMode | null>(null);
  protected readonly draft = signal<Draft>(emptyDraft());
  protected readonly formError = signal('');

  protected readonly yearLabel = computed(() => this.years().find((item) => item.id === this.year())?.label ?? '');
  protected readonly pageCount = computed(() => Math.max(1, Math.ceil(this.total() / PAGE_SIZE)));
  protected readonly pageNumbers = computed(() => Array.from({ length: this.pageCount() }, (_, index) => index));
  protected readonly cells = computed(() => buildCells(this.cursor(), this.selected(), this.monthHolidays()));
  protected readonly showing = computed(() => {
    const count = this.total();
    if (!count) return 'Showing 0 holidays';
    const start = this.pageIndex() * PAGE_SIZE + 1;
    return `Showing ${start}–${Math.min(count, start + PAGE_SIZE - 1)} of ${count} holidays`;
  });

  constructor() {
    this.api.holidayFilters().subscribe({
      next: (filters) => {
        this.types.set(filters.categories);
        this.states.set(filters.states);
        this.locations.set(filters.locations);
        this.festivals.set(filters.policyFestivals ?? []);
        this.financialYears = filters.financialYears;
        this.applyYearChoices();
      },
      error: (error: unknown) => this.loadError.set(problem(error)),
    });
  }

  protected setBasis(value: 'financial' | 'calendar'): void {
    if (this.basis() === value) return;
    this.basis.set(value);
    this.applyYearChoices();
  }

  protected setYear(value: number): void {
    this.year.set(value);
    this.pageIndex.set(0);
    const month = this.basis() === 'calendar' ? 0 : 3;
    if (!inBasis(iso(this.cursor()), value, this.basis())) {
      this.cursor.set(new Date(value, month, 1));
      this.selected.set(new Date(value, month, 1));
    }
    this.reload();
  }

  protected onType(value: HolidayCategory): void {
    const company = value === 'National' || value === 'Festival';
    this.patch({
      type: value,
      optional: value === 'Optional',
      stateId: company ? null : this.draft().stateId,
      locationId: company ? null : this.draft().locationId,
      stateName: company ? null : this.draft().stateName,
      locationName: company ? 'All Locations' : this.draft().locationName,
      active: value === 'Festival' && this.draft().id == null ? false : this.draft().active,
    });
  }

  private applyYearChoices(): void {
    const financialYears = this.financialYears;
    const today = new Date().getFullYear();
    const ids = this.basis() === 'calendar'
      ? [...new Set([...financialYears, ...financialYears.map((year) => year + 1), today])].sort((a, b) => a - b)
      : [...financialYears].sort((a, b) => a - b);
    this.years.set(ids.map((year) => ({
      id: year,
      label: this.basis() === 'calendar' ? String(year) : `FY ${year}–${year + 1}`,
    })));
    if (!ids.includes(this.year()) && ids.length) this.year.set(ids[ids.length - 1]);
    this.pageIndex.set(0);
    this.reload();
  }

  protected setType(value: HolidayCategory | null): void { this.type.set(value); this.pageIndex.set(0); this.reload(); }
  protected setState(value: number | null): void { this.state.set(value); this.pageIndex.set(0); this.reload(); }
  protected setLocation(value: number | null): void { this.location.set(value); this.pageIndex.set(0); this.reload(); }
  protected setSearch(value: string): void { this.search.set(value); this.pageIndex.set(0); this.reload(); }

  protected reset(): void {
    this.type.set(null);
    this.state.set(null);
    this.location.set(null);
    this.search.set('');
    this.pageIndex.set(0);
    this.reload();
  }

  protected shift(direction: -1 | 1): void {
    const cursor = this.cursor();
    this.cursor.set(new Date(cursor.getFullYear(), cursor.getMonth() + direction, 1));
    this.reload();
  }

  protected goToday(): void {
    const today = strip(new Date());
    this.selected.set(today);
    this.cursor.set(new Date(today.getFullYear(), today.getMonth(), 1));
    const start = financialYear(today);
    if (this.years().some((item) => item.id === start)) this.year.set(start);
    this.reload();
  }

  protected selectDate(date: Date): void {
    const day = strip(date);
    this.selected.set(day);
    if (day.getMonth() !== this.cursor().getMonth() || day.getFullYear() !== this.cursor().getFullYear()) {
      this.cursor.set(new Date(day.getFullYear(), day.getMonth(), 1));
      this.reload();
    }
  }

  protected choose(holiday: HolidayItem, date: Date, event: Event): void {
    event.stopPropagation();
    this.selectDate(date);
    this.openView(holiday);
  }

  protected toggleSort(): void {
    this.sortAsc.update((value) => !value);
    this.pageIndex.set(0);
    this.reload();
  }

  protected goPage(index: number): void {
    this.pageIndex.set(Math.min(Math.max(index, 0), this.pageCount() - 1));
    this.reload();
  }

  protected openAdd(): void {
    this.draft.set(emptyDraft());
    this.formError.set('');
    this.drawerMode.set('add');
    void this.drawer().open();
  }

  protected openEdit(holiday: HolidayItem): void {
    this.draft.set(toDraft(holiday));
    this.formError.set('');
    this.drawerMode.set('edit');
    void this.drawer().open();
  }

  protected openView(holiday: HolidayItem): void {
    this.draft.set(toDraft(holiday));
    this.formError.set('');
    this.drawerMode.set('view');
    void this.drawer().open();
  }

  protected patch(partial: Partial<Draft>): void {
    this.draft.update((current) => ({ ...current, ...partial }));
    this.formError.set('');
  }

  protected stateName(id: number | null): string | null {
    return this.states().find((item) => item.id === id)?.name ?? null;
  }

  protected locationName(id: number | null): string {
    return this.locations().find((item) => item.id === id)?.name ?? 'All Locations';
  }

  protected save(): void {
    const draft = this.draft();
    const message = validate(draft);
    if (message) {
      this.formError.set(message);
      return;
    }
    const body = toWrite(draft);
    const request = draft.id == null || draft.rowVersion == null
      ? this.api.createHoliday(body)
      : this.api.updateHoliday(draft.id, draft.rowVersion, body);
    request.subscribe({
      next: () => {
        this.snack.open(draft.id == null ? 'Holiday added.' : 'Holiday updated.', 'Close', { duration: 2500 });
        this.close();
        this.reload();
      },
      error: (error: unknown) => this.formError.set(problem(error)),
    });
  }

  protected remove(holiday: HolidayItem): void {
    confirmAction(this.dialog, {
      title: 'Delete holiday',
      message: `Delete ${holiday.name}? This removes it from the calendar and the list.`,
      confirmText: 'Delete',
      destructive: true,
    }).subscribe((confirmed) => {
      if (!confirmed) return;
      this.api.deleteHoliday(holiday.id, holiday.rowVersion).subscribe({
        next: () => {
          this.snack.open('Holiday deleted.', 'Close', { duration: 2500 });
          if (this.draft().id === holiday.id) this.close();
          if (this.pageIndex() > 0 && this.pageRows().length === 1) this.pageIndex.update((index) => index - 1);
          this.reload();
        },
        error: (error: unknown) => this.snack.open(problem(error), 'Close', { duration: 4000 }),
      });
    });
  }

  protected close(): void {
    this.drawerMode.set(null);
    void this.drawer().close();
  }

  protected startEdit(): void {
    this.formError.set('');
    this.drawerMode.set('edit');
  }

  protected whenDate(value: Date | null): string {
    return value ? this.when(iso(value)) : '—';
  }

  protected dayDate(value: Date | null): string {
    return value ? dayName(iso(value)) : '—';
  }

  protected browse(): void {
    this.fileInput()?.nativeElement.click();
  }

  protected pickFile(event: Event): void {
    const input = event.target as HTMLInputElement;
    const file = input.files?.[0];
    input.value = '';
    if (!file) return;
    if (!file.name.toLowerCase().endsWith('.csv')) {
      this.dialog.open(HolidayImportDialog, {
        data: { fileName: file.name, note: 'Save the workbook as CSV, then import that file.', rows: [] },
        width: '640px',
        maxWidth: 'calc(100vw - 32px)',
      });
      return;
    }
    file.text().then((text) => {
      const rows = parseCsv(text);
      this.dialog.open<HolidayImportDialog, { fileName: string; note: string; rows: ImportRow[] }, ImportRow[]>(
        HolidayImportDialog,
        {
          data: { fileName: file.name, note: 'Rows with a message are skipped.', rows },
          width: '640px',
          maxWidth: 'calc(100vw - 32px)',
        },
      ).afterClosed().subscribe((chosen) => {
        if (!chosen?.length) return;
        this.importRows(chosen);
      });
    });
  }

  protected exportRows(): void {
    this.api.holidays({ ...this.query(), page: 1, pageSize: 200, sort: 'holidayDate' }).subscribe({
      next: (page) => download(page.items, this.year()),
      error: (error: unknown) => this.snack.open(problem(error), 'Close', { duration: 4000 }),
    });
  }

  protected when(value: string): string {
    const [year, month, day] = value.split('-');
    return `${day}-${MONTHS[Number(month) - 1]}-${year}`;
  }

  protected monthTitle(): string {
    const cursor = this.cursor();
    return `${MONTH_NAMES[cursor.getMonth()]} ${cursor.getFullYear()}`;
  }

  protected tone(holiday: HolidayItem): string {
    if (holiday.optional || holiday.category === 'Optional') return 'optional';
    if (holiday.category === 'Festival') return 'festival';
    return holiday.category === 'Regional' ? 'regional' : 'national';
  }

  protected serial(index: number): number {
    return this.pageIndex() * PAGE_SIZE + index + 1;
  }

  protected dayOf(value: string): string {
    return dayName(value);
  }

  private reload(): void {
    const token = ++this.loadToken;
    const bounds = gridBounds(this.cursor());
    const query = this.query();
    forkJoin({
      summary: this.api.holidaySummary(query),
      page: this.api.holidays({
        ...query,
        page: this.pageIndex() + 1,
        pageSize: PAGE_SIZE,
        sort: this.sortAsc() ? 'holidayDate' : '-holidayDate',
      }),
      calendar: this.api.holidayCalendar({ ...query, startDate: bounds.start, endDate: bounds.end }),
    }).subscribe({
      next: (result) => {
        if (token !== this.loadToken) return;
        this.summary.set(result.summary);
        this.pageRows.set(result.page.items);
        this.total.set(result.page.total);
        this.monthHolidays.set(result.calendar);
        this.loadError.set('');
      },
      error: (error: unknown) => {
        if (token === this.loadToken) this.loadError.set(problem(error));
      },
    });
  }

  private query() {
    const year = this.basis() === 'calendar' ? { calendarYear: this.year() } : { financialYear: this.year() };
    return {
      ...year,
      holidayCategory: this.type(),
      stateId: this.state(),
      locationId: this.location(),
      search: this.search().trim(),
    };
  }

  private importRows(rows: ImportRow[]): void {
    let pending = rows.length;
    let saved = 0;
    let failed = '';
    for (const row of rows) {
      const state = this.states().find((item) => item.name.toLowerCase() === row.state.toLowerCase());
      const location = this.locations().find((item) => item.name.toLowerCase() === row.location.toLowerCase());
      const body: HolidayWrite = {
        name: row.name,
        holidayDate: row.date,
        category: row.type as HolidayCategory,
        stateId: row.type === 'National' || row.type === 'Festival' ? null : state?.id ?? null,
        locationId: row.type === 'National' || row.type === 'Festival' ? null : location?.id ?? null,
        isActive: true,
      };
      this.api.createHoliday(body).subscribe({
        next: () => {
          saved += 1;
          pending -= 1;
          if (!pending) this.finishImport(saved, failed);
        },
        error: (error: unknown) => {
          failed = problem(error);
          pending -= 1;
          if (!pending) this.finishImport(saved, failed);
        },
      });
    }
  }

  private finishImport(saved: number, failed: string): void {
    this.snack.open(failed ? `Imported ${saved}. ${failed}` : `Imported ${saved} holidays.`, 'Close', { duration: 4000 });
    this.reload();
  }
}

function emptyDraft(): Draft {
  return {
    id: null, rowVersion: null, name: '', date: null, type: null, stateId: null, stateName: null,
    locationId: null, locationName: 'All Locations', description: '', optional: false, active: true,
  };
}

function toDraft(holiday: HolidayItem): Draft {
  const [year, month, day] = holiday.holidayDate.split('-').map(Number);
  return {
    id: holiday.id,
    rowVersion: holiday.rowVersion,
    name: holiday.name,
    date: new Date(year, month - 1, day),
    type: holiday.category === 'Optional' ? 'Regional' : holiday.category,
    stateId: holiday.stateId,
    stateName: holiday.stateName,
    locationId: holiday.locationId,
    locationName: holiday.locationName,
    description: holiday.description ?? '',
    optional: holiday.optional,
    active: holiday.isActive,
  };
}

function toWrite(draft: Draft): HolidayWrite {
  const category: HolidayCategory = draft.optional || draft.type === 'Optional' ? 'Optional' : draft.type ?? 'National';
  return {
    name: draft.name.trim(),
    holidayDate: iso(draft.date ?? new Date()),
    category,
    stateId: category === 'National' || category === 'Festival' ? null : draft.stateId,
    locationId: category === 'National' || category === 'Festival' ? null : draft.locationId,
    description: draft.description.trim() || null,
    isActive: draft.active,
  };
}

function validate(draft: Draft): string {
  if (!draft.name.trim()) return 'Holiday name is mandatory.';
  if (!draft.date) return 'Holiday date is mandatory.';
  if (!draft.type && !draft.optional) return 'Holiday type is mandatory.';
  const category = draft.optional || draft.type === 'Optional' ? 'Optional' : draft.type;
  if (category !== 'National' && category !== 'Festival' && draft.stateId == null) {
    return 'State is mandatory for a regional or optional holiday.';
  }
  return '';
}

function buildCells(cursor: Date, selected: Date, holidays: HolidayItem[]) {
  const selectedKey = iso(selected);
  const today = iso(strip(new Date()));
  return datesFor(cursor).map((date) => {
    const key = iso(date);
    return {
      date,
      iso: key,
      inMonth: date.getMonth() === cursor.getMonth() && date.getFullYear() === cursor.getFullYear(),
      isToday: key === today,
      isSelected: key === selectedKey,
      holidays: holidays.filter((item) => item.holidayDate === key).sort((a, b) => a.name.localeCompare(b.name)),
    };
  });
}

function gridBounds(cursor: Date): { start: string; end: string } {
  const dates = datesFor(cursor);
  return { start: iso(dates[0]), end: iso(dates[dates.length - 1]) };
}

function datesFor(cursor: Date): Date[] {
  const first = new Date(cursor.getFullYear(), cursor.getMonth(), 1);
  const start = addDays(first, -first.getDay());
  const days = Array.from({ length: 42 }, (_, index) => addDays(start, index));
  return days.slice(35).every((day) => day.getMonth() !== cursor.getMonth()) ? days.slice(0, 35) : days;
}

function parseCsv(text: string): ImportRow[] {
  const lines = text.split(/\r?\n/).map((line) => line.trim()).filter(Boolean);
  const header = lines[0]?.toLowerCase() ?? '';
  const body = header.includes('holiday') || header.includes('name') ? lines.slice(1) : lines;
  return body.map((line) => {
    const [name = '', date = '', type = '', state = '', location = ''] = splitCsv(line);
    const category = normalType(type);
    let error = '';
    if (!name.trim()) error = 'Holiday name is mandatory.';
    else if (!/^\d{4}-\d{2}-\d{2}$/.test(date)) error = 'Holiday date must be YYYY-MM-DD.';
    else if (!category) error = 'Holiday type is mandatory.';
    else if (category !== 'National' && category !== 'Festival' && !state.trim()) {
      error = 'State is mandatory for a regional or optional holiday.';
    }
    return { name: name.trim(), date, type: category, state: state.trim(), location: location.trim(), error };
  });
}

function splitCsv(line: string): string[] {
  return line.split(',').map((part) => part.trim().replace(/^"|"$/g, ''));
}

function normalType(value: string): HolidayCategory | '' {
  const text = value.trim().toLowerCase();
  if (text === 'national') return 'National';
  if (text === 'festival') return 'Festival';
  if (text === 'regional') return 'Regional';
  if (text === 'optional') return 'Optional';
  return '';
}

function download(items: HolidayItem[], year: number): void {
  const header = ['Holiday Name', 'Date', 'Day', 'Type', 'State', 'Location', 'Description', 'Status'];
  const lines = items.map((item) => [
    item.name, item.holidayDate, item.day, item.category, item.stateName ?? 'All States', item.locationName,
    item.description ?? '', item.isActive ? 'Active' : 'Inactive',
  ].map(csv).join(','));
  const blob = new Blob([[header.join(','), ...lines].join('\n')], { type: 'text/csv' });
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = `holidays-fy-${year}.csv`;
  link.click();
  URL.revokeObjectURL(url);
}

function inBasis(value: string, start: number, basis: 'financial' | 'calendar'): boolean {
  if (basis === 'calendar') return value >= `${start}-01-01` && value <= `${start}-12-31`;
  return value >= `${start}-04-01` && value <= `${start + 1}-03-31`;
}

function financialYear(value: Date): number {
  return value.getMonth() >= 3 ? value.getFullYear() : value.getFullYear() - 1;
}

function dayName(value: string): string {
  const [year, month, day] = value.split('-').map(Number);
  return WEEKDAYS[new Date(year, month - 1, day).getDay()];
}

function strip(value: Date): Date {
  return new Date(value.getFullYear(), value.getMonth(), value.getDate());
}

function addDays(value: Date, days: number): Date {
  const next = strip(value);
  next.setDate(next.getDate() + days);
  return next;
}

function iso(value: Date): string {
  return `${value.getFullYear()}-${String(value.getMonth() + 1).padStart(2, '0')}-${String(value.getDate()).padStart(2, '0')}`;
}

function csv(value: string): string {
  return `"${value.replaceAll('"', '""')}"`;
}

function problem(error: unknown): string {
  const detail = (error as { error?: { detail?: unknown } }).error?.detail;
  return typeof detail === 'string' ? detail : 'The holiday request could not be completed.';
}
