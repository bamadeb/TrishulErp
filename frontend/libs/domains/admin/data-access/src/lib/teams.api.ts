import { Injectable, inject } from '@angular/core';
import { Observable } from 'rxjs';
import {
  ApiClient,
  activateTeam,
  createTeam,
  deactivateTeam,
  getTeam,
  listTeamEmployeeOptions,
  listTeams,
  updateTeam,
  withRowVersion,
} from '@trishul/core-api';
import {
  TeamCreate,
  TeamDetail,
  TeamEmployeeOption,
  TeamListItem,
  TeamQuery,
  TeamUpdate,
} from './teams.models';

/** /core/teams, through ApiClient and the generated functions. */
@Injectable({ providedIn: 'root' })
export class TeamsApi {
  private readonly api = inject(ApiClient);

  list(query: TeamQuery): Observable<TeamListItem[]> {
    return this.api.call(listTeams, query);
  }

  get(teamId: number): Observable<TeamDetail> {
    return this.api.call(getTeam, { teamId });
  }

  create(body: TeamCreate): Observable<TeamDetail> {
    return this.api.call(createTeam, { body });
  }

  /** rowVersion from when the team was loaded; a newer change by someone else gives 409. */
  update(
    teamId: number,
    rowVersion: string,
    body: TeamUpdate,
  ): Observable<TeamDetail> {
    return this.api.call(
      updateTeam,
      { teamId, body },
      withRowVersion(rowVersion),
    );
  }

  deactivate(teamId: number): Observable<TeamDetail> {
    return this.api.call(deactivateTeam, { teamId });
  }

  activate(teamId: number): Observable<TeamDetail> {
    return this.api.call(activateTeam, { teamId });
  }

  /** Active employees of the branch, to pick the lead and members. */
  employeeOptions(branchId: number): Observable<TeamEmployeeOption[]> {
    return this.api.call(listTeamEmployeeOptions, { branchId });
  }
}
