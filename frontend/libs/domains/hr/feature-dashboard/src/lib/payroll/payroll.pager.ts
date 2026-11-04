import { Signal, computed, signal } from '@angular/core';

/** Client-side search and paging for the payroll prototype tables. */
export function payrollPager<T>(rows: Signal<readonly T[]>, textOf: (row: T) => string) {
  const search = signal('');
  const pageIndex = signal(0);
  const pageSize = signal(10);

  const filtered = computed(() => {
    const term = search().trim().toLowerCase();
    const source = rows();
    if (!term) return source;
    return source.filter((row) => textOf(row).toLowerCase().includes(term));
  });

  const pageCount = computed(() => Math.max(1, Math.ceil(filtered().length / pageSize())));

  const pageRows = computed(() => {
    const start = pageIndex() * pageSize();
    return filtered().slice(start, start + pageSize());
  });

  const pages = computed(() => {
    const count = pageCount();
    const current = pageIndex();
    if (count <= 7) return Array.from({ length: count }, (_, index) => index);
    const start = Math.max(0, Math.min(current - 3, count - 7));
    return Array.from({ length: 7 }, (_, index) => start + index);
  });

  const rangeLabel = computed(() => {
    const total = filtered().length;
    if (!total) return '0 of 0';
    const start = pageIndex() * pageSize() + 1;
    const end = Math.min(total, start + pageRows().length - 1);
    return `${start}–${end} of ${total}`;
  });

  return {
    search,
    pageIndex,
    pageSize,
    filtered,
    pageRows,
    pageCount,
    pages,
    rangeLabel,
    onSearch(value: string): void {
      search.set(value);
      pageIndex.set(0);
    },
    onPageSize(value: string): void {
      pageSize.set(Number(value));
      pageIndex.set(0);
    },
    goTo(index: number): void {
      pageIndex.set(Math.min(Math.max(index, 0), pageCount() - 1));
    },
    rowNumber(index: number): number {
      return pageIndex() * pageSize() + index + 1;
    },
  };
}
