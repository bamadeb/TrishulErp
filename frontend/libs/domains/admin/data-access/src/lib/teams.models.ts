import { ListTeams$Params, TeamListItem } from '@trishul/core-api';
import { allOf } from '@trishul/shared-util';

export type {
  TeamCreate,
  TeamDetail,
  TeamEmployeeOption,
  TeamListItem,
  TeamMemberItem,
  TeamUpdate,
} from '@trishul/core-api';

export type TeamStatusFilter = NonNullable<ListTeams$Params['status']>;
export type TeamType = TeamListItem['teamType'];
export type TeamQuery = ListTeams$Params;

export const TEAM_STATUS_FILTERS = allOf<TeamStatusFilter>()([
  'active',
  'inactive',
  'all',
]);

export const TEAM_TYPES = allOf<TeamType>()(['Service', 'Sales', 'Back office']);

/** Open the team screens / change teams. The API checks the same codes (modules/core/teams/router.py). */
export const TEAM_VIEW_PERMISSIONS = [
  'core.team.view',
  'core.team.manage',
] as const;
export const TEAM_MANAGE_PERMISSION = 'core.team.manage';

export type TeamRow = TeamListItem;
