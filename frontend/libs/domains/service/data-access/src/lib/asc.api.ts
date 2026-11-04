import { Injectable, inject } from '@angular/core';
import { Observable } from 'rxjs';
import {
  ApiClient,
  PageServiceContractListItem,
  activateContractPlan,
  applyServiceContractImport,
  cancelServiceContract,
  createContractPlan,
  createServiceContract,
  deactivateContractPlan,
  getServiceContract,
  getServiceContractFormOptions,
  listContractPlans,
  listServiceContracts,
  previewServiceContractImport,
  renewServiceContract,
  updateContractPlan,
  updateServiceContract,
  withRowVersion,
} from '@trishul/core-api';
import {
  AscImportResult,
  AscQuery,
  ContractFormOptions,
  ContractPlanCreate,
  ContractPlanItem,
  ContractPlanUpdate,
  ServiceContractCreate,
  ServiceContractDetail,
  ServiceContractRenew,
  ServiceContractUpdate,
} from './asc.models';

/** /svc/service-contracts (ASC), /svc/contract-plans and the register upload. */
@Injectable({ providedIn: 'root' })
export class AscApi {
  private readonly api = inject(ApiClient);

  list(query: AscQuery): Observable<PageServiceContractListItem> {
    return this.api.call(listServiceContracts, query);
  }

  get(contractId: number): Observable<ServiceContractDetail> {
    return this.api.call(getServiceContract, { contractId });
  }

  create(body: ServiceContractCreate): Observable<ServiceContractDetail> {
    return this.api.call(createServiceContract, { body });
  }

  /** rowVersion from when the contract was loaded; a newer change by someone else gives 409. */
  update(
    contractId: number,
    rowVersion: string,
    body: ServiceContractUpdate,
  ): Observable<ServiceContractDetail> {
    return this.api.call(
      updateServiceContract,
      { contractId, body },
      withRowVersion(rowVersion),
    );
  }

  renew(
    contractId: number,
    body: ServiceContractRenew,
  ): Observable<ServiceContractDetail> {
    return this.api.call(renewServiceContract, { contractId, body });
  }

  cancel(contractId: number): Observable<ServiceContractDetail> {
    return this.api.call(cancelServiceContract, { contractId });
  }

  /** Active plans of the selected brand and the engineers of a branch. */
  formOptions(branchId?: number): Observable<ContractFormOptions> {
    return this.api.call(getServiceContractFormOptions, { branchId });
  }

  plans(
    status: 'active' | 'inactive' | 'all' = 'active',
  ): Observable<ContractPlanItem[]> {
    return this.api.call(listContractPlans, { status });
  }

  createPlan(body: ContractPlanCreate): Observable<ContractPlanItem> {
    return this.api.call(createContractPlan, { body });
  }

  updatePlan(
    planId: number,
    rowVersion: string,
    body: ContractPlanUpdate,
  ): Observable<ContractPlanItem> {
    return this.api.call(
      updateContractPlan,
      { planId, body },
      withRowVersion(rowVersion),
    );
  }

  setPlanActive(planId: number, active: boolean): Observable<ContractPlanItem> {
    return this.api.call(
      active ? activateContractPlan : deactivateContractPlan,
      { planId },
    );
  }

  /** Dry run: what uploading the register would do. Nothing is saved. */
  previewImport(file: File, branchId: number): Observable<AscImportResult> {
    return this.api.call(previewServiceContractImport, {
      body: this.body(file, branchId),
    });
  }

  applyImport(file: File, branchId: number): Observable<AscImportResult> {
    return this.api.call(applyServiceContractImport, {
      body: this.body(file, branchId),
    });
  }

  // The generated body types the file as string (OpenAPI binary); at runtime it is sent as the File.
  private body(
    file: File,
    branchId: number,
  ): { file: string; branchId: number } {
    return { file: file as unknown as string, branchId };
  }
}
