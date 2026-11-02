import { Injectable, inject } from '@angular/core';
import { Observable } from 'rxjs';
import {
  ApiClient,
  activateRole,
  createRole,
  deactivateRole,
  getRole,
  listPermissions,
  listRoles,
  updateRole,
  withRowVersion,
} from '@trishul/core-api';
import {
  PermissionItem,
  RoleCreate,
  RoleDetail,
  RoleListItem,
  RoleQuery,
  RoleUpdate,
} from './roles.models';

/** /core/roles and /core/permissions, through ApiClient and the generated functions. */
@Injectable({ providedIn: 'root' })
export class RolesApi {
  private readonly api = inject(ApiClient);

  list(query: RoleQuery): Observable<RoleListItem[]> {
    return this.api.call(listRoles, query);
  }

  get(roleId: number): Observable<RoleDetail> {
    return this.api.call(getRole, { roleId });
  }

  create(body: RoleCreate): Observable<RoleDetail> {
    return this.api.call(createRole, { body });
  }

  /** rowVersion from when the role was loaded; a newer change by someone else gives 409. */
  update(
    roleId: number,
    rowVersion: string,
    body: RoleUpdate,
  ): Observable<RoleDetail> {
    return this.api.call(
      updateRole,
      { roleId, body },
      withRowVersion(rowVersion),
    );
  }

  deactivate(roleId: number): Observable<RoleDetail> {
    return this.api.call(deactivateRole, { roleId });
  }

  activate(roleId: number): Observable<RoleDetail> {
    return this.api.call(activateRole, { roleId });
  }

  /** Every active permission, by module then code. */
  permissions(): Observable<PermissionItem[]> {
    return this.api.call(listPermissions);
  }
}
