// The signed-in user (GET /me) and its branch / brand references come from the generated API client.
// permissions holds core.permission codes, e.g. 'svc.call.assign'; '*' grants everything.
export type {
  Me as CurrentUser,
  BranchRef,
  PrincipalRef,
} from '@trishul/core-api';
