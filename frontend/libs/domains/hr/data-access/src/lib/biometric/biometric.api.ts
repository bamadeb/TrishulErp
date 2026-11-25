import { HttpClient, HttpParams } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { Observable } from 'rxjs';
import { ApiConfiguration } from '@trishul/core-api';

export const BIOMETRIC_VIEW_PERMISSIONS = ['hr.biometric.view', 'hr.biometric.manage'] as const;
export const BIOMETRIC_MANAGE_PERMISSION = 'hr.biometric.manage';
export const BIOMETRIC_SYNC_PERMISSIONS = ['hr.biometric.sync', 'hr.biometric.manage'] as const;

export type BiometricDeviceStatus = 'Online' | 'Offline' | 'Maintenance';
export type BiometricSyncStatus = 'Pending' | 'Running' | 'Success' | 'Failed' | 'Skipped';
export type BiometricSyncTrigger = 'Manual' | 'Scheduled';
export type BiometricPunchType = 'IN' | 'OUT' | string;

export interface BiometricPage<T> {
  items: T[];
  total: number;
  page: number;
  pageSize: number;
}

export interface BiometricDevice {
  id: number;
  code: string;
  name: string;
  vendor: string;
  serialNumber: string | null;
  locationName: string | null;
  branchId: number | null;
  externalDeviceId: string | null;
  credentialSecretName: string | null;
  baseUrl: string | null;
  isSyncEnabled: boolean;
  lastSyncedAt: string | null;
  isActive: boolean;
  status: BiometricDeviceStatus;
  createdAt: string;
  rowVersion: string;
}

export interface BiometricDeviceCreate {
  code: string;
  name: string;
  vendor?: string;
  serialNumber?: string | null;
  locationName?: string | null;
  branchId?: number | null;
  externalDeviceId?: string | null;
  credentialSecretName?: string | null;
  baseUrl?: string | null;
  isSyncEnabled?: boolean;
}

export interface BiometricDeviceUpdate {
  name?: string;
  vendor?: string;
  serialNumber?: string | null;
  locationName?: string | null;
  branchId?: number | null;
  externalDeviceId?: string | null;
  credentialSecretName?: string | null;
  baseUrl?: string | null;
  isSyncEnabled?: boolean | null;
  isActive?: boolean | null;
}

export interface BiometricMapping {
  id: number;
  employeeId: number;
  employeeCode: string | null;
  employeeName: string | null;
  departmentName: string | null;
  branchName: string | null;
  biometricUserId: string;
  deviceId: number | null;
  deviceName: string | null;
  effectiveFrom: string;
  effectiveTo: string | null;
  isActive: boolean;
  createdAt: string;
}

export interface BiometricMappingCreate {
  employeeId: number;
  biometricUserId: string;
  deviceId?: number | null;
  effectiveFrom: string;
  effectiveTo?: string | null;
}

export interface BiometricMappingUpdate {
  biometricUserId?: string;
  deviceId?: number | null;
  effectiveFrom?: string;
  effectiveTo?: string | null;
  isActive?: boolean;
}

export interface BiometricPunch {
  id: number;
  deviceId: number;
  deviceName: string | null;
  deviceLocation: string | null;
  employeeId: number | null;
  employeeCode: string | null;
  employeeName: string | null;
  departmentName: string | null;
  biometricUserId: string;
  punchedAt: string;
  punchType: BiometricPunchType | null;
  externalPunchId: string | null;
  source: string;
  syncLogId: number | null;
  createdAt: string;
}

export interface BiometricPunchQuery {
  page?: number;
  pageSize?: number;
  search?: string;
  deviceId?: number;
  employeeId?: number;
  punchType?: string;
  fromAt?: string;
  toAt?: string;
}

export interface BiometricSyncLog {
  id: number;
  deviceId: number | null;
  deviceName: string | null;
  deviceCode: string | null;
  startedAt: string;
  finishedAt: string | null;
  status: BiometricSyncStatus;
  trigger: BiometricSyncTrigger;
  recordsFetched: number;
  recordsInserted: number;
  recordsDuplicate: number;
  errorMessage: string | null;
  createdByUserId: number | null;
}

export interface BiometricSyncLogQuery {
  page?: number;
  pageSize?: number;
  deviceId?: number;
  status?: BiometricSyncStatus;
  trigger?: BiometricSyncTrigger;
}

export interface BiometricPunchTrendPoint {
  hour: string;
  checkIn: number;
  checkOut: number;
}

export interface BiometricDashboard {
  registeredDevices: number;
  mappedEmployees: number;
  todaysPunches: number;
  lastSyncAt: string | null;
  lastSyncStatus: BiometricSyncStatus | null;
  syncFailures: number;
  deviceStatus: {
    online: number;
    offline: number;
    maintenance: number;
  };
  punchTrend: BiometricPunchTrendPoint[];
  recentPunches: BiometricPunch[];
  integrationStatus: 'Ready' | 'Disabled' | 'Blocked';
  integrationMessage: string;
}

@Injectable({ providedIn: 'root' })
export class BiometricApi {
  private readonly http = inject(HttpClient);
  private readonly config = inject(ApiConfiguration);

  private get base(): string {
    return `${this.config.rootUrl}/hr/biometric`;
  }

  dashboard(): Observable<BiometricDashboard> {
    return this.http.get<BiometricDashboard>(`${this.base}/dashboard`);
  }

  listDevices(): Observable<BiometricDevice[]> {
    return this.http.get<BiometricDevice[]>(`${this.base}/devices`);
  }

  createDevice(body: BiometricDeviceCreate): Observable<BiometricDevice> {
    return this.http.post<BiometricDevice>(`${this.base}/devices`, body);
  }

  updateDevice(deviceId: number, body: BiometricDeviceUpdate): Observable<BiometricDevice> {
    return this.http.patch<BiometricDevice>(`${this.base}/devices/${deviceId}`, body);
  }

  listMappings(params?: { employeeId?: number; deviceId?: number }): Observable<BiometricMapping[]> {
    let httpParams = new HttpParams();
    if (params?.employeeId) httpParams = httpParams.set('employeeId', String(params.employeeId));
    if (params?.deviceId) httpParams = httpParams.set('deviceId', String(params.deviceId));
    return this.http.get<BiometricMapping[]>(`${this.base}/mappings`, { params: httpParams });
  }

  createMapping(body: BiometricMappingCreate): Observable<BiometricMapping> {
    return this.http.post<BiometricMapping>(`${this.base}/mappings`, body);
  }

  updateMapping(mappingId: number, body: BiometricMappingUpdate): Observable<BiometricMapping> {
    return this.http.patch<BiometricMapping>(`${this.base}/mappings/${mappingId}`, body);
  }

  deactivateMapping(mappingId: number): Observable<BiometricMapping> {
    return this.http.delete<BiometricMapping>(`${this.base}/mappings/${mappingId}`);
  }

  listPunches(query: BiometricPunchQuery = {}): Observable<BiometricPage<BiometricPunch>> {
    let params = new HttpParams()
      .set('page', String(query.page ?? 1))
      .set('pageSize', String(query.pageSize ?? 20));
    if (query.search?.trim()) params = params.set('search', query.search.trim());
    if (query.deviceId) params = params.set('deviceId', String(query.deviceId));
    if (query.employeeId) params = params.set('employeeId', String(query.employeeId));
    if (query.punchType) params = params.set('punchType', query.punchType);
    if (query.fromAt) params = params.set('fromAt', query.fromAt);
    if (query.toAt) params = params.set('toAt', query.toAt);
    return this.http.get<BiometricPage<BiometricPunch>>(`${this.base}/punches`, { params });
  }

  listSyncLogs(query: BiometricSyncLogQuery = {}): Observable<BiometricPage<BiometricSyncLog>> {
    let params = new HttpParams()
      .set('page', String(query.page ?? 1))
      .set('pageSize', String(query.pageSize ?? 20));
    if (query.deviceId) params = params.set('deviceId', String(query.deviceId));
    if (query.status) params = params.set('status', query.status);
    if (query.trigger) params = params.set('trigger', query.trigger);
    return this.http.get<BiometricPage<BiometricSyncLog>>(`${this.base}/sync-logs`, { params });
  }

  runSync(body: { deviceId?: number | null } = {}): Observable<BiometricSyncLog> {
    return this.http.post<BiometricSyncLog>(`${this.base}/sync`, body);
  }
}
