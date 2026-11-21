import { Injectable, inject } from '@angular/core';
import { Observable } from 'rxjs';
import {
  ApiClient,
  TrackingConfigParameter,
  listTrackingConfigParameters,
  updateTrackingConfigParameter,
  withRowVersion,
} from '@trishul/core-api';

export type { TrackingConfigParameter } from '@trishul/core-api';

/** Change the tracking parameters the mobile app fetches. */
export const TRACKING_CONFIG_PERMISSION = 'trk.config.manage';

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
