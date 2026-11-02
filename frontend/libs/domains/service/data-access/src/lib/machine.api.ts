import { Injectable, inject } from '@angular/core';
import { Observable } from 'rxjs';
import {
  ApiClient,
  PageMachineListItem,
  activateMachine,
  createMachine,
  deactivateMachine,
  getMachine,
  getMachineFormOptions,
  listMachines,
  updateMachine,
  withRowVersion,
} from '@trishul/core-api';
import {
  MachineCreate,
  MachineDetail,
  MachineFormOptions,
  MachineQuery,
  MachineUpdate,
} from './machine.models';

/** /svc/machines and the form's option lists, through ApiClient and the generated functions. */
@Injectable({ providedIn: 'root' })
export class MachineApi {
  private readonly api = inject(ApiClient);

  list(query: MachineQuery): Observable<PageMachineListItem> {
    return this.api.call(listMachines, query);
  }

  get(machineId: number): Observable<MachineDetail> {
    return this.api.call(getMachine, { machineId });
  }

  create(body: MachineCreate): Observable<MachineDetail> {
    return this.api.call(createMachine, { body });
  }

  /** rowVersion from when the machine was loaded; a newer change by someone else gives 409. */
  update(
    machineId: number,
    rowVersion: string,
    body: MachineUpdate,
  ): Observable<MachineDetail> {
    return this.api.call(
      updateMachine,
      { machineId, body },
      withRowVersion(rowVersion),
    );
  }

  deactivate(machineId: number): Observable<MachineDetail> {
    return this.api.call(deactivateMachine, { machineId });
  }

  activate(machineId: number): Observable<MachineDetail> {
    return this.api.call(activateMachine, { machineId });
  }

  /** Models of the selected brand. */
  formOptions(): Observable<MachineFormOptions> {
    return this.api.call(getMachineFormOptions);
  }
}
