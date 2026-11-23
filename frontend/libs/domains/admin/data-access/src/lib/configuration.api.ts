import { Injectable, inject } from '@angular/core';
import { Observable } from 'rxjs';
import {
  ApiClient,
  ServiceSettings,
  TrackingConfigParameter,
  getServiceSettings,
  listTrackingConfigParameters,
  updateServiceSettings,
  updateTrackingConfigParameter,
  withRowVersion,
} from '@trishul/core-api';

export type { ServiceSettings, TrackingConfigParameter } from '@trishul/core-api';

/** Change the tracking parameters the mobile app fetches. */
export const TRACKING_CONFIG_PERMISSION = 'trk.config.manage';

/** Change service settings, such as the pending-call limit per engineer. */
export const SERVICE_CONFIG_PERMISSION = 'svc.config.manage';

/** /svc/settings: service settings kept in the system settings table. */
@Injectable({ providedIn: 'root' })
export class ServiceSettingsApi {
  private readonly api = inject(ApiClient);

  get(): Observable<ServiceSettings> {
    return this.api.call(getServiceSettings);
  }

  update(maxPendingCalls: number): Observable<ServiceSettings> {
    return this.api.call(updateServiceSettings, { body: { maxPendingCalls } });
  }
}

/** /trk/tracking-config: the trip-tracking parameters (intervals, radii, thresholds) of the mobile app. */
@Injectable({ providedIn: 'root' })
export class TrackingConfigApi {
  private readonly api = inject(ApiClient);

  list(): Observable<TrackingConfigParameter[]> {
    return this.api.call(listTrackingConfigParameters);
  }

  /** A number for int / decimal parameters, text for string ones; null clears a "to be calibrated" one. */
  update(
    parameter: TrackingConfigParameter,
    value: number | string | null,
  ): Observable<TrackingConfigParameter> {
    return this.api.call(
      updateTrackingConfigParameter,
      { code: parameter.code, body: { value } },
      withRowVersion(parameter.rowVersion),
    );
  }
}
