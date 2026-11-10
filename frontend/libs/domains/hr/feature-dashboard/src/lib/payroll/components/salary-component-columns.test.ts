import assert from 'node:assert/strict';
import { describe, it } from 'node:test';
import {
  defaultHiddenColumns,
  isFixedSalaryColumn,
  setSalaryColumnVisible,
  visibleSalaryColumns,
} from './salary-component-columns.ts';

function keys(hidden: readonly string[]): string[] {
  return visibleSalaryColumns(hidden as never).map((column) => column.key);
}

describe('salary component columns', () => {
  it('keeps the five fixed columns through hide, show all and reset', () => {
    const fixed = ['index', 'code', 'name', 'status', 'actions'];
    let hidden = defaultHiddenColumns();
    assert.deepEqual(keys(hidden), [
      'index', 'code', 'name', 'type', 'calculation', 'basis', 'amount', 'applicability', 'status', 'actions',
    ]);
    assert.equal(keys(hidden).filter((key) => !fixed.includes(key)).length, 5);

    for (const key of fixed) {
      hidden = setSalaryColumnVisible(hidden, key as never, false);
      assert.equal(isFixedSalaryColumn(key as never), true);
    }
    for (const key of fixed) assert.equal(keys(hidden).includes(key), true);

    for (const key of ['type', 'calculation', 'basis', 'amount', 'applicability', 'effectiveFrom', 'tax', 'statutory', 'gross'] as const) {
      hidden = setSalaryColumnVisible(hidden, key, false);
    }
    assert.deepEqual(keys(hidden), fixed);

    hidden = setSalaryColumnVisible(hidden, 'pf', true);
    hidden = setSalaryColumnVisible(hidden, 'esi', true);
    hidden = setSalaryColumnVisible(hidden, 'proration', true);
    hidden = setSalaryColumnVisible(hidden, 'tax', true);
    hidden = setSalaryColumnVisible(hidden, 'lastModified', true);
    const shown = keys(hidden);
    assert.equal(shown.indexOf('name') < shown.indexOf('pf'), true);
    assert.equal(shown.indexOf('lastModified') < shown.indexOf('status'), true);
    assert.deepEqual(shown.slice(0, 3), ['index', 'code', 'name']);
    assert.deepEqual(shown.slice(-2), ['status', 'actions']);

    hidden = [];
    assert.equal(keys(hidden).filter((key) => fixed.includes(key)).length, fixed.length);
    hidden = defaultHiddenColumns();
    assert.equal(keys(hidden).includes('effectiveFrom'), false);
    assert.equal(keys(hidden).includes('type'), true);
  });
});
