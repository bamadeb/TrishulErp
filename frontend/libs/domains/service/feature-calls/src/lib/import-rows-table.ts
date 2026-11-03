import { DatePipe, NgTemplateOutlet } from '@angular/common';
import { ChangeDetectionStrategy, Component, input } from '@angular/core';
import { MatTableModule } from '@angular/material/table';
import { RouterLink } from '@angular/router';
import { BydImportRow, FieldChange } from '@trishul/service-data-access';
import { StatusBadge, StatusSeverity } from '@trishul/shared-ui';

const ACTION_LABELS: Record<string, string> = {
  insert: 'New call',
  update: 'Update',
  skip: 'Skipped',
};
const ACTION_SEVERITY: Partial<Record<string, StatusSeverity>> = {
  'New call': 'success',
  Update: 'info',
  Skipped: 'neutral',
};
const LINK_SEVERITY: Partial<Record<string, StatusSeverity>> = {
  Linked: 'success',
  'Needs linking': 'warn',
};
/** Dates in a change are ISO 8601 UTC from the API; shown in local time. */
const ISO_DATE = /^\d{4}-\d{2}-\d{2}T/;

/** The rows of a BYD file and what the import did with each: used by the import page and the import log. */
@Component({
  selector: 'trishul-import-rows-table',
  imports: [
    MatTableModule,
    RouterLink,
    DatePipe,
    NgTemplateOutlet,
    StatusBadge,
  ],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './import-rows-table.html',
  styleUrl: './byd-import.page.scss',
})
export class ImportRowsTable {
  readonly rows = input.required<readonly BydImportRow[]>();

  protected readonly columns = [
    'rowNumber',
    'c4CTicketId',
    'call',
    'account',
    'action',
    'linking',
    'changes',
    'messages',
  ];
  protected readonly actionSeverity = ACTION_SEVERITY;
  protected readonly linkSeverity = LINK_SEVERITY;

  protected actionLabel(action: string): string {
    return ACTION_LABELS[action] ?? action;
  }

  protected linkLabel(row: BydImportRow): string {
    return row.needsLinking ? 'Needs linking' : 'Linked';
  }

  protected isDate(value: FieldChange['old']): boolean {
    return value !== null && ISO_DATE.test(value);
  }
}
