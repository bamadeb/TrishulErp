import { Injectable, inject } from '@angular/core';
import { Observable } from 'rxjs';
import {
  ApiClient,
  PageAlertRuleListItem,
  activateAlertRule,
  createAlertRule,
  deactivateAlertRule,
  getAlertRule,
  getAlertRuleFormOptions,
  listAlertRules,
  testAlertRule,
  updateAlertRule,
  withRowVersion,
} from '@trishul/core-api';
import {
  AlertRuleCreate,
  AlertRuleDetail,
  AlertRuleFormOptions,
  AlertRuleQuery,
  AlertRuleTestResult,
  AlertRuleUpdate,
} from './alert-rules.models';

/** /core/alert-rules (Alert Master), through ApiClient and the generated functions. */
@Injectable({ providedIn: 'root' })
export class AlertRulesApi {
  private readonly api = inject(ApiClient);

  list(query: AlertRuleQuery): Observable<PageAlertRuleListItem> {
    return this.api.call(listAlertRules, query);
  }

  get(alertRuleId: number): Observable<AlertRuleDetail> {
    return this.api.call(getAlertRule, { alertRuleId });
  }

  create(body: AlertRuleCreate): Observable<AlertRuleDetail> {
    return this.api.call(createAlertRule, { body });
  }

  /** rowVersion from when the rule was loaded; a newer change by someone else gives 409. */
  update(
    alertRuleId: number,
    rowVersion: string,
    body: AlertRuleUpdate,
  ): Observable<AlertRuleDetail> {
    return this.api.call(
      updateAlertRule,
      { alertRuleId, body },
      withRowVersion(rowVersion),
    );
  }

  deactivate(alertRuleId: number): Observable<AlertRuleDetail> {
    return this.api.call(deactivateAlertRule, { alertRuleId });
  }

  activate(alertRuleId: number): Observable<AlertRuleDetail> {
    return this.api.call(activateAlertRule, { alertRuleId });
  }

  /** Dry run of the saved rule: what matches now and who would be told. */
  test(alertRuleId: number): Observable<AlertRuleTestResult> {
    return this.api.call(testAlertRule, { alertRuleId });
  }

  /** Alert types (with their settings), roles, users, brands and branches. */
  formOptions(): Observable<AlertRuleFormOptions> {
    return this.api.call(getAlertRuleFormOptions);
  }
}
