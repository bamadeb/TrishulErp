import { BranchRef } from './auth.models';
import { branchGroups, branchPlace, branchesOfWarehouse, warehousesOf } from './branch-options';

const branch = (over: Partial<BranchRef> & Pick<BranchRef, 'id' | 'name'>): BranchRef => ({
  code: over.name.toUpperCase(),
  branchType: 'Branch',
  warehouseId: null,
  warehouseName: null,
  regionId: null,
  regionName: null,
  ...over,
});

const BRANCHES: BranchRef[] = [
  branch({ id: 1, name: 'Head office', branchType: 'Head office' }),
  branch({ id: 10, name: 'Jharsuguda Warehouse', branchType: 'Warehouse', warehouseId: 10, warehouseName: 'Jharsuguda Warehouse' }),
  branch({ id: 20, name: 'Rourkela', warehouseId: 10, warehouseName: 'Jharsuguda Warehouse', regionId: 5, regionName: 'Western' }),
  branch({ id: 30, name: 'Barbil', warehouseId: 11, warehouseName: 'Barbil Warehouse', regionId: 6, regionName: 'Mining belt' }),
];

describe('branch options', () => {
  it('lists each warehouse once, by name', () => {
    expect(warehousesOf(BRANCHES).map((w) => w.name)).toEqual(['Barbil Warehouse', 'Jharsuguda Warehouse']);
  });

  it('narrows to the chosen warehouse, or keeps all of them', () => {
    expect(branchesOfWarehouse(BRANCHES, 10).map((b) => b.id)).toEqual([10, 20]);
    expect(branchesOfWarehouse(BRANCHES, null)).toHaveLength(4);
  });

  it('shows region and warehouse for a branch only', () => {
    expect(branchPlace(BRANCHES[2])).toBe('Western · Jharsuguda Warehouse');
    expect(branchPlace(BRANCHES[1])).toBe('');
    expect(branchPlace(BRANCHES[0])).toBe('');
  });

  it('groups branches under their warehouse, warehouse first, unsupplied ones last', () => {
    const groups = branchGroups(BRANCHES);
    expect(groups.map((g) => g.label)).toEqual(['Barbil Warehouse', 'Jharsuguda Warehouse', 'Other']);
    expect(groups[1].branches.map((b) => b.name)).toEqual(['Jharsuguda Warehouse', 'Rourkela']);
    expect(groups[2].branches.map((b) => b.name)).toEqual(['Head office']);
  });
});
