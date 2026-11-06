import { BranchRef } from './auth.models';

/** A warehouse the signed-in user's branches are supplied from. */
export interface WarehouseOption {
  id: number;
  name: string;
}

/** The distinct warehouses behind the user's branches, by name. */
export function warehousesOf(branches: readonly BranchRef[]): WarehouseOption[] {
  const found = new Map<number, string>();
  for (const branch of branches) {
    if (branch.warehouseId != null && branch.warehouseName) {
      found.set(branch.warehouseId, branch.warehouseName);
    }
  }
  return [...found].map(([id, name]) => ({ id, name })).sort((a, b) => a.name.localeCompare(b.name));
}

/** The branches a warehouse supplies (and the warehouse itself); all of them when none is chosen. */
export function branchesOfWarehouse(
  branches: readonly BranchRef[],
  warehouseId: number | null,
): BranchRef[] {
  return warehouseId == null ? [...branches] : branches.filter((b) => b.warehouseId === warehouseId);
}

/** "Region · Warehouse" for a branch; empty for warehouses and for branches not mapped yet. */
export function branchPlace(branch: BranchRef): string {
  if (branch.branchType === 'Warehouse') return '';
  return [branch.regionName, branch.warehouseName].filter(Boolean).join(' · ');
}

/** One warehouse and the branches it supplies (the warehouse itself first), for a grouped dropdown. */
export interface BranchGroup {
  label: string;
  /** True for a warehouse's group; false for the group of branches no warehouse supplies. */
  warehouse: boolean;
  branches: BranchRef[];
}

/** Groups the branches by warehouse; branches no warehouse supplies (e.g. the head office) go last. */
export function branchGroups(branches: readonly BranchRef[]): BranchGroup[] {
  const byWarehouse = new Map<number, BranchRef[]>();
  const others: BranchRef[] = [];
  for (const branch of branches) {
    if (branch.warehouseId == null) {
      others.push(branch);
    } else {
      const members = byWarehouse.get(branch.warehouseId) ?? [];
      members.push(branch);
      byWarehouse.set(branch.warehouseId, members);
    }
  }
  const groups = [...byWarehouse].map(([warehouseId, members]) => ({
    label: members[0].warehouseName ?? '',
    warehouse: true,
    branches: members.sort(
      (a, b) =>
        Number(b.id === warehouseId) - Number(a.id === warehouseId) ||
        a.name.localeCompare(b.name),
    ),
  }));
  groups.sort((a, b) => a.label.localeCompare(b.label));
  if (others.length) {
    groups.push({
      label: groups.length ? 'Other' : 'Branches',
      warehouse: false,
      branches: others.sort((a, b) => a.name.localeCompare(b.name)),
    });
  }
  return groups;
}
