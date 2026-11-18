import { NgTemplateOutlet } from '@angular/common';
import { AfterViewInit, ChangeDetectionStrategy, Component, ElementRef, NgZone, OnDestroy, computed, effect, inject, signal, viewChild } from '@angular/core';
import { MatIconButton } from '@angular/material/button';
import { MatDialog } from '@angular/material/dialog';
import { MatSnackBar } from '@angular/material/snack-bar';
import { MatFormField, MatLabel, MatPrefix } from '@angular/material/form-field';
import { MatIcon } from '@angular/material/icon';
import { MatInput } from '@angular/material/input';
import { MatOption, MatSelect } from '@angular/material/select';
import { ReportingApi, ReportingPerson } from '@trishul/hr-data-access';
import { ReportingAssignDialog } from './reporting-assign.dialog';
import { ReportingDetail } from './reporting-detail';
import { ReportingRemoveDialog } from './reporting-remove.dialog';
import { ReportingDemoStore, WIDE_SPAN, laterThanToday } from './reporting.store';

interface OrgNode {
  person: ReportingPerson;
  depth: number;
  children: OrgNode[];
  direct: number;
  team: number;
}

interface TreeCriteria {
  search: string;
  department: string;
  location: string;
  status: 'All' | 'Active' | 'Inactive';
}

@Component({
  selector: 'trishul-reporting-tree',
  imports: [
    NgTemplateOutlet,
    MatIconButton,
    MatFormField,
    MatLabel,
    MatPrefix,
    MatIcon,
    MatInput,
    MatSelect,
    MatOption,
    ReportingDetail,
  ],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './reporting-tree.html',
  styleUrl: './reporting-tree.scss',
})
export class ReportingTree implements AfterViewInit, OnDestroy {
  private readonly host = inject(ElementRef<HTMLElement>);
  private readonly zone = inject(NgZone);
  private readonly dialog = inject(MatDialog);
  private readonly snackBar = inject(MatSnackBar);
  private readonly reporting = inject(ReportingApi);
  private readonly store = inject(ReportingDemoStore);
  private readonly canvas = viewChild<ElementRef<HTMLElement>>('canvas');
  private readonly stage = viewChild<ElementRef<HTMLElement>>('stage');
  private resize: ResizeObserver | null = null;
  private lastFit = 0;
  private layoutKey = '';

  protected readonly people = this.store.people;
  protected readonly search = signal('');
  protected readonly department = signal('All');
  protected readonly location = signal('All');
  protected readonly status = signal<'All' | 'Active' | 'Inactive'>('All');
  protected readonly collapsed = signal<ReadonlySet<number>>(new Set());
  protected readonly zoom = signal(1);
  protected readonly selectedId = signal<number | null>(null);
  protected readonly teamRoot = signal<number | null>(null);
  protected readonly cardWidth = signal(200);
  protected readonly wideSpan = WIDE_SPAN;
  protected readonly unassignedOpen = signal(true);
  protected readonly links = signal<readonly string[]>([]);
  protected readonly board = signal({ w: 0, h: 0 });

  protected readonly departments = computed(() => choices(this.people().map((person) => person.department)));
  protected readonly locations = computed(() => choices(this.people().map((person) => person.location)));

  protected readonly view = computed(() => {
    const criteria: TreeCriteria = {
      search: this.search(),
      department: this.department(),
      location: this.location(),
      status: this.status(),
    };
    const forest = scopeTeam(buildForest(this.people()), this.teamRoot());
    const active = isFiltering(criteria);
    if (!active) return { ...forest, active };
    const match = (person: ReportingPerson) => personMatches(person, criteria);
    return {
      roots: forest.roots.map((root) => prune(root, match)).filter((node): node is OrgNode => node !== null),
      unassigned: forest.unassigned.filter(match),
      active,
    };
  });

  protected readonly detail = computed(() => {
    const id = this.selectedId();
    const person = this.people().find((row) => row.id === id);
    if (!person) return null;
    const node = findNode(buildForest(this.people()).roots, person.id);
    const manager = person.managerId == null ? null : this.people().find((row) => row.id === person.managerId) ?? null;
    return { person, manager, node };
  });

  constructor() {
    effect(() => {
      this.view();
      this.collapsed();
      queueMicrotask(() => this.draw());
    });
    effect(() => {
      const id = this.teamRoot();
      if (id != null && !this.people().some((person) => person.id === id)) this.teamRoot.set(null);
    });
    effect(() => {
      const active = isFiltering({
        search: this.search(),
        department: this.department(),
        location: this.location(),
        status: this.status(),
      });
      if (!active) return;
      queueMicrotask(() => {
        this.host.nativeElement.querySelector('.card.hit')?.scrollIntoView({ block: 'nearest', inline: 'center' });
      });
    });
  }

  ngAfterViewInit(): void {
    const canvas = this.canvas()?.nativeElement;
    const stage = this.stage()?.nativeElement;
    this.resize = new ResizeObserver(() => this.zone.run(() => this.draw()));
    if (canvas) this.resize.observe(canvas);
    if (stage) this.resize.observe(stage);
    this.draw();
  }

  ngOnDestroy(): void {
    this.resize?.disconnect();
    this.resize = null;
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

  protected hit(person: ReportingPerson): boolean {
    return this.view().active && personMatches(person, this.criteria());
  }

  protected opened(node: OrgNode): boolean {
    if (this.view().active && node.children.length > 0) return true;
    return !this.collapsed().has(node.person.id);
  }

  protected pick(id: number): void {
    this.selectedId.set(id);
    const ancestors = new Set<number>();
    const walk = (node: OrgNode, parents: number[]): boolean => {
      if (node.person.id === id) {
        parents.forEach((parent) => ancestors.add(parent));
        return true;
      }
      return node.children.some((child) => walk(child, [...parents, node.person.id]));
    };
    buildForest(this.people()).roots.forEach((root) => walk(root, []));
    if (ancestors.size) {
      this.collapsed.update((current) => {
        const next = new Set(current);
        ancestors.forEach((parent) => next.delete(parent));
        return next;
      });
    }
    queueMicrotask(() => this.focusCard(id));
  }

  protected closePanel(): void {
    this.selectedId.set(null);
  }

  protected toggle(event: Event, id: number): void {
    event.stopPropagation();
    this.collapsed.update((current) => {
      const next = new Set(current);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  protected expandAll(): void {
    this.collapsed.set(new Set());
  }

  protected collapseAll(): void {
    const ids = new Set<number>();
    const walk = (node: OrgNode): void => {
      if (node.direct > 0) ids.add(node.person.id);
      node.children.forEach(walk);
    };
    buildForest(this.people()).roots.forEach(walk);
    this.collapsed.set(ids);
  }

  protected zoomBy(delta: number): void {
    this.zoom.update((value) => clamp(Math.round((value + delta) * 10) / 10));
  }

  protected fit(): void {
    this.zoom.set(1);
    requestAnimationFrame(() => this.zone.run(() => this.draw()));
  }

  protected showTeam(id: number): void {
    this.teamRoot.set(id);
    this.collapsed.update((current) => {
      const next = new Set(current);
      next.delete(id);
      return next;
    });
  }

  protected clearTeam(): void {
    this.teamRoot.set(null);
  }

  protected canFocusTeam(): boolean {
    const id = this.selectedId();
    if (id == null || this.teamRoot() === id) return false;
    return (findNode(buildForest(this.people()).roots, id)?.direct ?? 0) > 0;
  }

  protected teamName(id: number): string {
    const person = this.people().find((row) => row.id === id);
    return person ? this.shown(person.name) : 'this manager';
  }

  protected later(person: ReportingPerson): boolean {
    return laterThanToday(person.managerEffectiveFrom);
  }

  protected cardTitle(node: OrgNode): string | null {
    const notes: string[] = [];
    if (node.direct >= WIDE_SPAN) notes.push(`Wide span of control: ${node.direct} direct reports`);
    if (this.later(node.person)) notes.push(`Manager change starts ${this.day(node.person.managerEffectiveFrom)}`);
    return notes.length ? notes.join('. ') : null;
  }

  protected day(value: string | null | undefined): string {
    if (!value) return '';
    const [year, month, day] = value.slice(0, 10).split('-');
    return year && month && day ? `${day}-${month}-${year}` : value;
  }

  protected exportBranch(): void {
    const header = ['Employee ID', 'Name', 'Designation', 'Department', 'Location', 'Reporting Manager', 'Level', 'Direct Reports', 'Status'];
    const lines = this.exportPeople().map((row) => {
      const manager = row.managerId == null ? 'Not assigned' : this.people().find((person) => person.id === row.managerId)?.name ?? 'Not assigned';
      const direct = String(this.people().filter((person) => person.managerId === row.id).length);
      return [row.code, row.name, row.designation, row.department, row.location, manager, row.level, direct, row.status]
        .map((value) => `"${value.replaceAll('"', '""')}"`)
        .join(',');
    });
    const blob = new Blob([[header.join(','), ...lines].join('\n')], { type: 'text/csv' });
    const link = document.createElement('a');
    link.href = URL.createObjectURL(blob);
    link.download = 'reporting-team.csv';
    link.click();
    URL.revokeObjectURL(link.href);
  }

  protected refresh(): void {
    this.reporting.list().subscribe((rows) => this.store.replace(rows));
  }

  protected reportsOf(node: OrgNode | null): ReportingPerson[] {
    return node?.children.map((child) => child.person) ?? [];
  }

  protected chain(person: ReportingPerson): ReportingPerson[] {
    const rows: ReportingPerson[] = [];
    const seen = new Set<number>();
    let current = person.managerId;
    while (current != null && !seen.has(current)) {
      seen.add(current);
      const manager = this.people().find((row) => row.id === current);
      if (!manager) break;
      rows.unshift(manager);
      current = manager.managerId;
    }
    return rows;
  }

  protected focusCard(id: number): void {
    this.host.nativeElement.querySelector(`[data-id="${id}"]`)?.scrollIntoView({ block: 'nearest', inline: 'center' });
  }

  protected assign(person: ReportingPerson): void {
    this.dialog
      .open(ReportingAssignDialog, { data: { employeeId: person.id }, width: '34rem', panelClass: 'reporting-assign-dialog' })
      .afterClosed()
      .subscribe((saved) => {
        if (!saved) return;
        this.refresh();
        this.snackBar.open('Reporting manager updated.', 'Close', { duration: 2500 });
      });
  }

  protected remove(person: ReportingPerson): void {
    const manager = person.managerId == null ? null : this.people().find((row) => row.id === person.managerId) ?? null;
    if (!manager) return;
    const node = findNode(buildForest(this.people()).roots, person.id);
    this.dialog
      .open(ReportingRemoveDialog, {
        data: {
          employeeId: person.id,
          employeeName: this.shown(person.name),
          employeeCode: person.code,
          managerName: this.shown(manager.name),
          hasTeam: (node?.direct ?? 0) > 0,
        },
        width: '32rem',
      })
      .afterClosed()
      .subscribe((saved) => {
        if (!saved) return;
        this.refresh();
        this.snackBar.open('Reporting manager removed.', 'Close', { duration: 2500 });
      });
  }

  private criteria(): TreeCriteria {
    return { search: this.search(), department: this.department(), location: this.location(), status: this.status() };
  }

  private exportPeople(): ReportingPerson[] {
    const selected = this.selectedId();
    const full = buildForest(this.people());
    if (selected != null) {
      const node = findNode(full.roots, selected);
      if (node) return flatten(node);
      const person = this.people().find((row) => row.id === selected);
      return person ? [person] : [];
    }
    const visible = this.view();
    return [...visible.roots.flatMap((node) => flatten(node)), ...visible.unassigned];
  }

  private applyCardWidth(stage: HTMLElement): void {
    const canvas = this.canvas()?.nativeElement;
    if (!canvas || canvas.clientWidth < 240) return;
    const available = canvas.clientWidth - 32;
    const layout = `${this.teamRoot() ?? 0}|${[...this.collapsed()].sort((left, right) => left - right).join(',')}|${this.view().active}`;
    if (layout === this.layoutKey && this.lastFit > 0 && Math.abs(available - this.lastFit) < 24) return;
    this.layoutKey = layout;
    const width = cardWidthFor(this.view().roots, (node) => this.opened(node), available);
    if (width === this.cardWidth()) {
      this.lastFit = available;
      return;
    }
    this.lastFit = available;
    this.cardWidth.set(width);
    stage.style.setProperty('--card', `${width}px`);
  }

  private draw(): void {
    const stage = this.stage()?.nativeElement;
    if (!stage) return;
    this.applyCardWidth(stage);
    const cards = [...stage.querySelectorAll<HTMLElement>('.card[data-id]')];
    const at = new Map<number, Box>();
    for (const card of cards) at.set(Number(card.dataset['id']), box(card, stage));
    const grouped = new Map<number, Box[]>();
    for (const card of cards) {
      const parent = card.dataset['parent'];
      if (!parent) continue;
      const parentId = Number(parent);
      const child = at.get(Number(card.dataset['id']));
      if (!at.has(parentId) || !child) continue;
      const list = grouped.get(parentId) ?? [];
      list.push(child);
      grouped.set(parentId, list);
    }
    const paths: string[] = [];
    for (const [parentId, children] of grouped) {
      const parent = at.get(parentId);
      if (!parent) continue;
      const path = elbow(parent, children);
      if (path) paths.push(path);
    }
    const w = stage.offsetWidth;
    const h = stage.offsetHeight;
    const current = this.links();
    const size = this.board();
    if (size.w === w && size.h === h && current.length === paths.length && current.every((path, index) => path === paths[index])) return;
    this.board.set({ w, h });
    this.links.set(paths);
  }
}

interface Box {
  x: number;
  y: number;
  w: number;
  h: number;
}

function box(el: HTMLElement, root: HTMLElement): Box {
  let x = 0;
  let y = 0;
  let node: HTMLElement | null = el;
  while (node && node !== root) {
    x += node.offsetLeft;
    y += node.offsetTop;
    node = node.offsetParent as HTMLElement | null;
  }
  return { x, y, w: el.offsetWidth, h: el.offsetHeight };
}

function elbow(parent: Box, kids: readonly Box[]): string {
  const start = parent.y + parent.h + 1;
  const stops = kids.map((kid) => kid.y - 1);
  const first = Math.min(...stops);
  if (first - start < 4) return '';
  const mid = Math.round((start + first) / 2);
  const px = Math.round(parent.x + parent.w / 2);
  const centers = kids.map((kid) => Math.round(kid.x + kid.w / 2));
  const left = Math.min(...centers);
  const right = Math.max(...centers);
  if (kids.length === 1 && Math.abs(centers[0] - px) <= 1) return `M ${px} ${start} V ${stops[0]}`;
  const parts = [`M ${px} ${start} V ${mid}`];
  parts.push(`M ${Math.min(left, px)} ${mid} H ${Math.max(right, px)}`);
  kids.forEach((_, index) => {
    if (stops[index] - mid < 1) return;
    parts.push(`M ${centers[index]} ${mid} V ${stops[index]}`);
  });
  return parts.join(' ');
}

function scopeTeam(
  forest: { roots: OrgNode[]; unassigned: ReportingPerson[] },
  id: number | null,
): { roots: OrgNode[]; unassigned: ReportingPerson[] } {
  if (id == null) return forest;
  const node = findNode(forest.roots, id);
  return node ? { roots: [node], unassigned: [] } : { roots: [], unassigned: [] };
}

function flatten(node: OrgNode): ReportingPerson[] {
  return [node.person, ...node.children.flatMap((child) => flatten(child))];
}

function cardWidthFor(roots: readonly OrgNode[], opened: (node: OrgNode) => boolean, available: number): number {
  const fits = (card: number) => forestWidth(roots, opened, card) <= available;
  if (fits(200)) return 200;
  if (!fits(148)) return 148;
  let low = 148;
  let high = 200;
  while (high - low > 1) {
    const mid = Math.round((low + high) / 2);
    if (fits(mid)) low = mid;
    else high = mid;
  }
  return low;
}

function forestWidth(roots: readonly OrgNode[], opened: (node: OrgNode) => boolean, card: number): number {
  const width = (node: OrgNode): number => {
    const kids = opened(node) ? node.children : [];
    const inner = kids.reduce((sum, child) => sum + width(child), 0);
    return Math.max(card + 2, inner) + 6;
  };
  return roots.reduce((sum, root) => sum + width(root), 0);
}

function buildForest(people: readonly ReportingPerson[]): { roots: OrgNode[]; unassigned: ReportingPerson[] } {
  const known = new Set(people.map((person) => person.id));
  const grouped = new Map<number, ReportingPerson[]>();
  for (const person of people) {
    if (person.managerId == null || !known.has(person.managerId)) continue;
    const list = grouped.get(person.managerId) ?? [];
    list.push(person);
    grouped.set(person.managerId, list);
  }
  const reports = (id: number) => grouped.get(id)?.length ?? 0;
  const roots = people.filter((person) => (person.managerId == null || !known.has(person.managerId)) && reports(person.id) > 0);
  const unassigned = people.filter((person) => (person.managerId == null || !known.has(person.managerId)) && reports(person.id) === 0);
  const node = (person: ReportingPerson, depth: number): OrgNode => {
    const children = (grouped.get(person.id) ?? []).slice().sort(byName).map((child) => node(child, depth + 1));
    return { person, depth, children, direct: children.length, team: children.reduce((sum, child) => sum + 1 + child.team, 0) };
  };
  return { roots: roots.sort(byName).map((person) => node(person, 1)), unassigned: unassigned.sort(byName) };
}

function prune(node: OrgNode, match: (person: ReportingPerson) => boolean): OrgNode | null {
  const children = node.children.map((child) => prune(child, match)).filter((child): child is OrgNode => child !== null);
  if (!match(node.person) && children.length === 0) return null;
  return { ...node, children };
}

function findNode(nodes: readonly OrgNode[], id: number): OrgNode | null {
  for (const node of nodes) {
    if (node.person.id === id) return node;
    const child = findNode(node.children, id);
    if (child) return child;
  }
  return null;
}

function personMatches(person: ReportingPerson, criteria: TreeCriteria): boolean {
  if (criteria.department !== 'All' && person.department !== criteria.department) return false;
  if (criteria.location !== 'All' && person.location !== criteria.location) return false;
  if (criteria.status !== 'All' && person.status !== criteria.status) return false;
  const term = criteria.search.trim().toLowerCase();
  return !term || `${person.code} ${person.name}`.toLowerCase().includes(term);
}

function isFiltering(criteria: TreeCriteria): boolean {
  return criteria.search.trim() !== '' || criteria.department !== 'All' || criteria.location !== 'All' || criteria.status !== 'All';
}

function byName(left: ReportingPerson, right: ReportingPerson): number {
  return left.name.localeCompare(right.name);
}

function choices(values: string[]): string[] {
  return [...new Set(values)].sort((left, right) => left.localeCompare(right));
}

function clamp(value: number): number {
  return Math.min(1.4, Math.max(0.5, value));
}
