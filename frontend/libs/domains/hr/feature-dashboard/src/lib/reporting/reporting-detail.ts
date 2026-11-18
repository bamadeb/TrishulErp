import { NgTemplateOutlet } from '@angular/common';
import { ChangeDetectionStrategy, Component, computed, effect, inject, input, output, signal } from '@angular/core';
import { RouterLink } from '@angular/router';
import { MatButton, MatIconButton } from '@angular/material/button';
import { MatDialog } from '@angular/material/dialog';
import { MatIcon } from '@angular/material/icon';
import { AuthStore } from '@trishul/core-auth';
import { ReportingApi, ReportingHistoryItem, ReportingPerson } from '@trishul/hr-data-access';
import { ReportingReportsDialog } from './reporting-reports.dialog';
import { WIDE_SPAN, laterThanToday } from './reporting.store';

type DetailTab = 'overview' | 'reporting' | 'history';

@Component({
  selector: 'trishul-reporting-detail',
  imports: [NgTemplateOutlet, RouterLink, MatButton, MatIconButton, MatIcon],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './reporting-detail.html',
  styleUrl: './reporting-detail.scss',
  host: { class: 'drawer' },
})
export class ReportingDetail {
  private readonly api = inject(ReportingApi);
  private readonly auth = inject(AuthStore);
  private readonly dialog = inject(MatDialog);
  private request = 0;
  private seenId = 0;
  private loadedFor = '';

  readonly person = input.required<ReportingPerson>();
  readonly manager = input<ReportingPerson | null>(null);
  readonly depth = input(1);
  readonly direct = input(0);
  readonly team = input(0);
  readonly reports = input<readonly ReportingPerson[]>([]);
  readonly path = input<readonly ReportingPerson[]>([]);

  readonly closed = output<void>();
  readonly picked = output<number>();
  readonly changed = output<void>();
  readonly removed = output<void>();
  readonly focusTree = output<void>();
  readonly focusTeam = output<number>();

  protected readonly tab = signal<DetailTab>('overview');
  protected readonly history = signal<ReportingHistoryItem[] | null>(null);
  protected readonly historyError = signal('');
  protected readonly canManage = computed(() =>
    this.auth.hasAnyPermission(['core.employee.manage', 'hr.organization.manage']),
  );
  protected readonly indirect = computed(() => Math.max(0, this.team() - this.direct()));

  constructor() {
    effect(() => {
      const person = this.person();
      const stamp = `${person.id}:${person.managerId ?? ''}`;
      const onHistory = this.tab() === 'history';
      if (this.seenId !== person.id) {
        this.seenId = person.id;
        this.loadedFor = '';
        this.tab.set('overview');
        this.history.set(null);
        this.historyError.set('');
      }
      if (onHistory && this.loadedFor !== stamp) this.load(person.id, stamp);
    });
  }

  protected shown(name: string): string {
    const trimmed = name.trim();
    if (trimmed !== trimmed.toUpperCase()) return trimmed;
    return trimmed.toLowerCase().replace(/(^|[\s'-])([a-z])/g, (_, lead: string, letter: string) => `${lead}${letter.toUpperCase()}`);
  }

  protected initials(name: string): string {
    const parts = this.shown(name).split(' ').filter(Boolean);
    return ((parts[0]?.[0] ?? '') + (parts[1]?.[0] ?? '')).toUpperCase();
  }

  protected show(next: DetailTab): void {
    this.tab.set(next);
  }

  protected close(event: Event): void {
    event.stopPropagation();
    this.closed.emit();
  }

  protected previewCount(): number {
    return Math.min(3, this.reports().length);
  }

  protected wideSpan(): boolean {
    return this.reports().length >= WIDE_SPAN;
  }

  protected startsLater(): boolean {
    return laterThanToday(this.person().managerEffectiveFrom);
  }

  protected scheduled(row: ReportingHistoryItem): boolean {
    return row.status === 'Active' && laterThanToday(row.effectiveFrom);
  }

  protected openReports(): void {
    this.dialog
      .open(ReportingReportsDialog, {
        data: { managerName: this.shown(this.person().name), reports: [...this.reports()] },
        width: '52rem',
        maxWidth: '95vw',
        maxHeight: '90vh',
        autoFocus: 'first-tabbable',
      })
      .afterClosed()
      .subscribe((id: unknown) => {
        if (typeof id === 'number') this.picked.emit(id);
      });
  }

  protected day(value: string | null): string {
    if (!value) return '—';
    if (/^\d{4}-\d{2}-\d{2}$/.test(value)) {
      const [year, month, day] = value.split('-');
      return `${day}-${month}-${year}`;
    }
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) return value;
    const day = String(date.getDate()).padStart(2, '0');
    const month = String(date.getMonth() + 1).padStart(2, '0');
    return `${day}-${month}-${date.getFullYear()}`;
  }

  private load(id: number, stamp: string): void {
    const token = ++this.request;
    this.loadedFor = stamp;
    this.history.set(null);
    this.historyError.set('');
    this.api.history(id).subscribe({
      next: (rows) => {
        if (token !== this.request) return;
        this.history.set(rows);
      },
      error: () => {
        if (token !== this.request) return;
        this.loadedFor = '';
        this.history.set([]);
        this.historyError.set('The reporting history could not be loaded.');
      },
    });
  }
}
