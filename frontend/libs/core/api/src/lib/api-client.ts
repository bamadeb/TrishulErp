import { HttpClient, HttpContext } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { Observable, map } from 'rxjs';
import { ApiConfiguration } from '../generated/api-configuration';
import { StrictHttpResponse } from '../generated/strict-http-response';

type ApiFnRequired<P, R> = (
  http: HttpClient,
  rootUrl: string,
  params: P,
  context?: HttpContext,
) => Observable<StrictHttpResponse<R>>;
type ApiFnOptional<P, R> = (
  http: HttpClient,
  rootUrl: string,
  params?: P,
  context?: HttpContext,
) => Observable<StrictHttpResponse<R>>;

/**
 * Calls a generated API function and returns the response body:
 *
 *   api.call(listServiceCalls, { page: 1, pageSize: 20 })
 *
 * The root URL comes from ApiConfiguration (provideTrishulHttp sets it to apiBaseUrl), so no
 * service builds URLs itself.
 */
@Injectable({ providedIn: 'root' })
export class ApiClient {
  private readonly http = inject(HttpClient);
  private readonly config = inject(ApiConfiguration);

  call<P, R>(
    fn: ApiFnRequired<P, R>,
    params: P,
    context?: HttpContext,
  ): Observable<R>;
  call<P, R>(
    fn: ApiFnOptional<P, R>,
    params?: P,
    context?: HttpContext,
  ): Observable<R>;
  call<P, R>(
    fn: ApiFnRequired<P, R> | ApiFnOptional<P, R>,
    params: P,
    context?: HttpContext,
  ): Observable<R> {
    return fn(this.http, this.config.rootUrl, params, context).pipe(
      map((response) => response.body),
    );
  }
}
