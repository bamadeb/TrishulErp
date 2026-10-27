import { Injectable, inject } from '@angular/core';
import { Observable } from 'rxjs';
import {
  ApiClient,
  PageUserListItem,
  activateUser,
  createUser,
  deactivateUser,
  getUser,
  listEmployees,
  listRoles,
  listUsers,
  resetUserPassword,
  updateUser,
  withRowVersion,
} from '@trishul/core-api';
import {
  EmployeeOption,
  PasswordDelivery,
  PasswordResetResult,
  RoleOption,
  UserCreate,
  UserCreated,
  UserDetail,
  UserQuery,
  UserUpdate,
} from './users.models';

/** /core/users and /core/roles, through ApiClient and the generated functions. */
@Injectable({ providedIn: 'root' })
export class UsersApi {
  private readonly api = inject(ApiClient);

  list(query: UserQuery): Observable<PageUserListItem> {
    return this.api.call(listUsers, query);
  }

  get(userId: number): Observable<UserDetail> {
    return this.api.call(getUser, { userId });
  }

  create(body: UserCreate): Observable<UserCreated> {
    return this.api.call(createUser, { body });
  }

  /** rowVersion from when the user was loaded; a newer change by someone else gives 409. */
  update(
    userId: number,
    rowVersion: string,
    body: UserUpdate,
  ): Observable<UserDetail> {
    return this.api.call(
      updateUser,
      { userId, body },
      withRowVersion(rowVersion),
    );
  }

  deactivate(userId: number): Observable<UserDetail> {
    return this.api.call(deactivateUser, { userId });
  }

  activate(userId: number): Observable<UserDetail> {
    return this.api.call(activateUser, { userId });
  }

  resetPassword(
    userId: number,
    delivery: PasswordDelivery,
  ): Observable<PasswordResetResult> {
    return this.api.call(resetUserPassword, { userId, body: { delivery } });
  }

  roles(): Observable<RoleOption[]> {
    return this.api.call(listRoles);
  }

  /** Active employees matching code, name, mobile or email (at most 20). */
  employees(search: string): Observable<EmployeeOption[]> {
    return this.api.call(listEmployees, { search: search || undefined });
  }
}
