import assert from 'node:assert/strict';
import { describe, it } from 'node:test';
import {
  SALARY_COMPONENTS,
  applyLimits,
  createComponent,
  draftFrom,
  duplicateComponent,
  evaluateFormula,
  previewAmount,
  setComponentActive,
  updateComponent,
  validateDraft,
} from './salary-component.model.ts';

const ORIGINAL = [
  ['Basic', 'Earning', 'Percentage', 50, 'All employees', true],
  ['HRA', 'Earning', 'Percentage', 40, 'All employees', true],
  ['Special allowance', 'Earning', 'Fixed', 5000, 'Grade L2 and above', true],
  ['Conveyance', 'Earning', 'Fixed', 1600, 'Field staff', true],
  ['Provident fund', 'Deduction', 'Percentage', 12, 'Basic, eligible staff', true],
  ['ESI', 'Deduction', 'Percentage', 0.75, 'Gross up to 21,000', true],
  ['Professional tax', 'Deduction', 'Fixed', 200, 'Karnataka payroll', true],
  ['Meal coupon', 'Earning', 'Fixed', 2200, 'Head office', false],
] as const;

describe('salary component master', () => {
  it('keeps the original eight components', () => {
    assert.equal(SALARY_COMPONENTS.length, 8);
    ORIGINAL.forEach((expected, index) => {
      const row = SALARY_COMPONENTS[index];
      assert.equal(row.id, index + 1);
      assert.equal(row.name, expected[0]);
      assert.equal(row.type, expected[1]);
      assert.equal(row.calculation, expected[2]);
      assert.equal(row.value, expected[3]);
      assert.equal(row.applicability, expected[4]);
      assert.equal(row.active, expected[5]);
      assert.equal(validateDraft(draftFrom(row), SALARY_COMPONENTS.map((item) => item.code), row.code), null);
    });
  });

  it('creates, updates, duplicates and deactivates without rewriting history', () => {
    const created = createComponent(SALARY_COMPONENTS, {
      ...draftFrom(SALARY_COMPONENTS[0]),
      code: 'BONUS',
      name: 'Annual bonus',
      calculation: 'Fixed',
      value: 1000,
      statutoryHead: 'None',
    });
    assert.equal(created.ok, true);
    assert.equal(created.row?.id, 9);
    assert.equal(created.row?.history[0].action, 'Created');

    const duplicateCode = createComponent(SALARY_COMPONENTS, draftFrom(SALARY_COMPONENTS[0]));
    assert.equal(duplicateCode.ok, false);

    const basic = SALARY_COMPONENTS[0];
    const updated = updateComponent(basic, { ...draftFrom(basic), value: 55, effectiveFrom: '2026-11-01' }, ['BASIC']);
    assert.equal(updated.ok, true);
    assert.equal(basic.value, 50);
    assert.equal(basic.versions.length, 0);
    assert.equal(updated.row?.value, 55);
    assert.equal(updated.row?.versions.length, 1);
    assert.equal(updated.row?.versions[0].value, 50);
    assert.equal(updated.row?.versions[0].effectiveFrom, '');

    const copied = duplicateComponent(SALARY_COMPONENTS, basic, {
      ...draftFrom(basic),
      code: 'BASIC-COPY',
      name: 'Copy of Basic',
    });
    assert.equal(copied.ok, true);
    assert.equal(copied.row?.id, 9);
    assert.equal(copied.row?.code, 'BASIC-COPY');
    assert.equal(basic.code, 'BASIC');
    assert.equal(copied.row?.history[0].summary, 'Duplicated from BASIC');
    assert.equal(copied.row?.versions.length, 0);

    const inactive = setComponentActive(basic, false);
    assert.equal(basic.active, true);
    assert.equal(inactive.active, false);
    assert.equal(inactive.versions.length, 0);
    assert.equal(inactive.history.at(-1)?.action, 'Deactivated');
    const again = setComponentActive(inactive, true);
    assert.equal(again.history.at(-1)?.action, 'Activated');
    assert.equal(inactive.history.at(-1)?.action, 'Deactivated');
  });

  it('evaluates only arithmetic formulas', () => {
    const variables = { BASIC: 30000, GROSS: 60000, CTC: 720000, HRA: 10000 };
    assert.deepEqual(evaluateFormula('BASIC * 0.4', variables), { ok: true, value: 12000 });
    assert.deepEqual(evaluateFormula('(BASIC + 1000) * 2', variables), { ok: true, value: 62000 });
    assert.deepEqual(evaluateFormula('MIN(BASIC, 15000)', variables), { ok: true, value: 15000 });
    assert.deepEqual(evaluateFormula('MAX(100, 20)', variables), { ok: true, value: 100 });
    assert.deepEqual(evaluateFormula('ROUND(BASIC * 0.333, 2)', variables), { ok: true, value: 9990 });
    assert.equal(evaluateFormula('BASIC / 0', variables).ok, false);
    assert.equal(evaluateFormula('eval(1)', variables).ok, false);
    assert.equal(evaluateFormula('process.exit(1)', variables).ok, false);
    assert.equal(evaluateFormula('BASIC["x"]', variables).ok, false);
    assert.equal(applyLimits(10.6, 'Nearest rupee', null, null), 11);
    assert.equal(applyLimits(10.2, 'Round up', 12, 20), 12);
    assert.equal(applyLimits(18.9, 'Round down', null, 15), 15);

    const preview = previewAmount({
      ...draftFrom(SALARY_COMPONENTS[1]),
      calculation: 'Formula',
      formula: 'MIN(HRA, ROUND(BASIC * 0.5))',
    }, { basic: 30000, gross: 60000, ctc: 720000, other: 10000 });
    assert.equal(preview.ok, true);
    if (preview.ok) assert.equal(preview.value, 10000);
  });
});
