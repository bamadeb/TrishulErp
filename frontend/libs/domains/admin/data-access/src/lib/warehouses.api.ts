import { Injectable, inject } from '@angular/core';
import { Observable } from 'rxjs';
import {
  ApiClient,
  WarehouseBranch,
  WarehouseCreate,
  WarehouseMap,
  WarehouseOut,
  WarehouseUpdate,
  createWarehouse,
  getWarehouseMap,
  updateBranchWarehouse,
  updateWarehouse,
  withRowVersion,
} from '@trishul/core-api';

/**
 * /core/warehouses: the warehouses and which branch each one supplies. A warehouse is a location of
 * type Warehouse; a branch points at the warehouse that supplies it.
 */
@Injectable({ providedIn: 'root' })
export class WarehouseApi {
  private readonly api = inject(ApiClient);

  load(): Observable<WarehouseMap> {
    return this.api.call(getWarehouseMap);
  }

  create(body: WarehouseCreate): Observable<WarehouseOut> {
    return this.api.call(createWarehouse, { body });
  }

  /** rowVersion comes with the warehouse; a newer change by someone else gives 409. */
  update(
    warehouse: WarehouseOut,
    body: WarehouseUpdate,
  ): Observable<WarehouseOut> {
    return this.api.call(
      updateWarehouse,
      { warehouseId: warehouse.id, body },
      withRowVersion(warehouse.rowVersion),
    );
  }

  /** Sets the warehouse that supplies a branch, or null for none. */
  assign(
    branch: WarehouseBranch,
    warehouseId: number | null,
  ): Observable<WarehouseBranch> {
    return this.api.call(
      updateBranchWarehouse,
      { branchId: branch.id, body: { warehouseId } },
      withRowVersion(branch.rowVersion),
    );
  }
}
