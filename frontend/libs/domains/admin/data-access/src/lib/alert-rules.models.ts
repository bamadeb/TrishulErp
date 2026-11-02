import {
  AlertRuleDetail,
  AlertRuleListItem,
  ListAlertRules$Params,
} from '@trishul/core-api';
import { allOf } from '@trishul/shared-util';

export type {
  AlertParamDef,
  AlertRecipientIn,
  AlertRecipientItem,
  AlertRuleCreate,
  AlertRuleDetail,
  AlertRuleFormOptions,
  AlertRuleListItem,
  AlertRuleTestResult,
  AlertRuleUpdate,
  AlertTypeItem,
  NamedOption,
} from '@trishul/core-api';

export type AlertRuleStatusFilter = NonNullable<
  ListAlertRules$Params['status']
>;
export type AlertType = AlertRuleDetail['alertType'];
export type AlertSeverity = AlertRuleDetail['severity'];
export type ReraisePolicy = AlertRuleDetail['reraisePolicy'];
export type RecipientType =
  AlertRuleDetail['recipients'][number]['recipientType'];

/** Query of the alert rule list; page and page size are always set. */
export type AlertRuleQuery = ListAlertRules$Params &
  Required<Pick<ListAlertRules$Params, 'page' | 'pageSize'>>;

export const ALERT_RULE_STATUS_FILTERS = allOf<AlertRuleStatusFilter>()([
  'all',
  'active',
  'inactive',
]);

/** Stops compiling if the API adds a value, so the dropdowns stay in sync. */
export const ALERT_SEVERITIES = allOf<AlertSeverity>()([
  'Info',
  'Warning',
  'Critical',
]);

export const RERAISE_POLICIES = allOf<ReraisePolicy>()([
  'After resolution',
  'Never',
]);

/** Open the Alert Master / change rules. The API checks the same codes. */
export const ALERT_RULE_VIEW_PERMISSIONS = [
  'core.alert.rule.view',
  'core.alert.rule.manage',
] as const;
export const ALERT_RULE_MANAGE_PERMISSION = 'core.alert.rule.manage';

export type AlertRuleRow = AlertRuleListItem;
