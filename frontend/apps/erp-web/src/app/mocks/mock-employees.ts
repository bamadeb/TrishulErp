import { HttpErrorResponse, HttpRequest } from '@angular/common/http';
import {
  CompanyOption,
  DepartmentOption,
  DesignationOption,
  EmployeeCreate,
  EmployeeDetail,
  EmployeeUpdate,
  PageEmployeeListItem,
} from '@trishul/core-api';
import { MockRoute } from '@trishul/core-http';

/** In-memory /core/employees and its option lists for mock mode and the end-to-end tests. */

const companies: CompanyOption[] = [
  { id: 1, name: 'Trishul' },
  { id: 2, name: 'Kashi Sales' },
];
const departments: DepartmentOption[] = [
  { id: 1, code: 'SVC', name: 'Service' },
  { id: 2, code: 'SAL', name: 'Sales' },
];
const designations: DesignationOption[] = [
  { id: 1, code: 'TL', name: 'Team Lead', departmentId: 1 },
  { id: 2, code: 'SE', name: 'Service Engineer', departmentId: 1 },
];
const branchNames: Record<number, string> = {
  1: 'Pune',
  2: 'Mumbai',
  3: 'Nagpur',
};

let nextId = 100;
let version = 1;
const rowVersion = () => btoa(`emp-rv-${version++}`);

type Seed = {
  id: number;
  employeeCode: string;
  firstName: string;
  lastName: string | null;
  mobile: string | null;
  email: string | null;
  companyId: number;
  branchId: number;
  departmentId: number | null;
  designationId: number | null;
  reportingManagerId: number | null;
  employeeType: EmployeeDetail['employeeType'];
  status: EmployeeDetail['status'];
  isActive: boolean;
  userId: number | null;
  dateOfJoining: string | null;
  dateOfExit: string | null;
  mobilePlatform: EmployeeDetail['mobilePlatform'];
};

const named = (id: number | null): string | null => {
  const e = seeds.find((s) => s.id === id);
  return e ? [e.firstName, e.lastName].filter(Boolean).join(' ') : null;
};

function detail(s: Seed): EmployeeDetail {
  return {
    ...s,
    fullName: [s.firstName, s.lastName].filter(Boolean).join(' '),
    hasLogin: s.userId !== null,
    branchName: branchNames[s.branchId] ?? null,
    department: s.departmentId
      ? (departments.find((d) => d.id === s.departmentId)?.name ?? null)
      : null,
    designation: s.designationId
      ? (designations.find((d) => d.id === s.designationId)?.name ?? null)
      : null,
    companyName: companies.find((c) => c.id === s.companyId)?.name ?? null,
    reportingManagerName: named(s.reportingManagerId),
    createdAt: new Date().toISOString(),
    rowVersion: rowVersion(),
  };
}

const seeds: Seed[] = [
  {
    id: 10,
    employeeCode: 'EMP0010',
    firstName: 'Rahul',
    lastName: 'Patil',
    mobile: '9822000010',
    email: 'rahul.patil@trishul.co',
    companyId: 1,
    branchId: 1,
    departmentId: 1,
    designationId: 1,
    reportingManagerId: null,
    employeeType: 'Permanent',
    status: 'Active',
    isActive: true,
    userId: 2,
    dateOfJoining: '2021-04-01',
    dateOfExit: null,
    mobilePlatform: 'Android',
  },
  {
    id: 11,
    employeeCode: 'EMP0011',
    firstName: 'Sneha',
    lastName: 'Kulkarni',
    mobile: '9822000011',
    email: 'sneha.k@trishul.co',
    companyId: 1,
    branchId: 1,
    departmentId: 1,
    designationId: 2,
    reportingManagerId: 10,
    employeeType: 'Permanent',
    status: 'Active',
    isActive: true,
    userId: null,
    dateOfJoining: '2022-07-15',
    dateOfExit: null,
    mobilePlatform: null,
  },
  {
    id: 12,
    employeeCode: 'EMP0012',
    firstName: 'Amit',
    lastName: 'Joshi',
    mobile: null,
    email: null,
    companyId: 2,
    branchId: 2,
    departmentId: null,
    designationId: null,
    reportingManagerId: null,
    employeeType: 'Contract',
    status: 'Notice',
    isActive: true,
    userId: null,
    dateOfJoining: null,
    dateOfExit: null,
    mobilePlatform: null,
  },
];

function find(params: Record<string, string>, req: HttpRequest<unknown>): Seed {
  const seed = seeds.find((s) => s.id === Number(params['employeeId']));
  if (!seed) {
    throw new HttpErrorResponse({
      status: 404,
      url: req.url,
      error: { status: 404, title: 'Not found', detail: 'Employee not found.' },
    });
  }
  return seed;
}

function problem(
  req: HttpRequest<unknown>,
  status: number,
  title: string,
  detail: string,
): never {
  throw new HttpErrorResponse({
    status,
    url: req.url,
    error: { status, title, detail },
  });
}

function duplicate(
  req: HttpRequest<unknown>,
  code: string | undefined,
  mobile: string | null | undefined,
  selfId: number | null,
): void {
  if (code && seeds.some((s) => s.employeeCode === code && s.id !== selfId)) {
    problem(
      req,
      409,
      'Already exists',
      `Employee code '${code}' is already in use.`,
    );
  }
  if (mobile && seeds.some((s) => s.mobile === mobile && s.id !== selfId)) {
    problem(
      req,
      409,
      'Already exists',
      `Mobile number '${mobile}' is already used by another employee.`,
    );
  }
}

export const mockEmployeeRoutes: MockRoute[] = [
  {
    method: 'GET',
    path: '/core/employees',
    handle: (req): PageEmployeeListItem => {
      const page = Number(req.params.get('page') ?? 1);
      const pageSize = Number(req.params.get('pageSize') ?? 20);
      const search = (req.params.get('search') ?? '').toLowerCase();
      const status = req.params.get('status') ?? 'active';
      const branchId = req.params.get('branchId');
      const employeeType = req.params.get('employeeType');
      const rows = seeds
        .filter(
          (s) =>
            (status === 'all' || s.isActive === (status === 'active')) &&
            (!branchId || s.branchId === Number(branchId)) &&
            (!employeeType || s.employeeType === employeeType) &&
            (!search ||
              [s.employeeCode, s.firstName, s.lastName, s.mobile, s.email].some(
                (v) => v?.toLowerCase().includes(search),
              )),
        )
        .map(detail);
      return {
        items: rows.slice((page - 1) * pageSize, page * pageSize),
        total: rows.length,
        page,
        pageSize,
      };
    },
  },
  {
    method: 'GET',
    path: '/core/employees/:employeeId',
    handle: (req, params) => detail(find(params, req)),
  },
  {
    method: 'POST',
    path: '/core/employees',
    handle: (req): EmployeeDetail => {
      const body = req.body as EmployeeCreate;
      duplicate(req, body.employeeCode, body.mobile, null);
      const seed: Seed = {
        id: nextId++,
        employeeCode: body.employeeCode,
        firstName: body.firstName,
        lastName: body.lastName ?? null,
        mobile: body.mobile ?? null,
        email: body.email ?? null,
        companyId: body.companyId,
        branchId: body.branchId,
        departmentId: body.departmentId ?? null,
        designationId: body.designationId ?? null,
        reportingManagerId: body.reportingManagerId ?? null,
        employeeType: body.employeeType,
        status: body.status ?? 'Active',
        isActive: true,
        userId: null,
        dateOfJoining: body.dateOfJoining ?? null,
        dateOfExit: body.dateOfExit ?? null,
        mobilePlatform: body.mobilePlatform ?? null,
      };
      seeds.push(seed);
      return detail(seed);
    },
  },
  {
    method: 'PATCH',
    path: '/core/employees/:employeeId',
    handle: (req, params) => {
      const seed = find(params, req);
      const body = req.body as EmployeeUpdate;
      duplicate(req, body.employeeCode ?? undefined, body.mobile, seed.id);
      Object.assign(seed, {
        employeeCode: body.employeeCode ?? seed.employeeCode,
        firstName: body.firstName ?? seed.firstName,
        lastName: 'lastName' in body ? (body.lastName ?? null) : seed.lastName,
        mobile: 'mobile' in body ? (body.mobile ?? null) : seed.mobile,
        email: 'email' in body ? (body.email ?? null) : seed.email,
        companyId: body.companyId ?? seed.companyId,
        branchId: body.branchId ?? seed.branchId,
        departmentId:
          'departmentId' in body
            ? (body.departmentId ?? null)
            : seed.departmentId,
        designationId:
          'designationId' in body
            ? (body.designationId ?? null)
            : seed.designationId,
        reportingManagerId:
          'reportingManagerId' in body
            ? (body.reportingManagerId ?? null)
            : seed.reportingManagerId,
        employeeType: body.employeeType ?? seed.employeeType,
        status: body.status ?? seed.status,
        dateOfJoining:
          'dateOfJoining' in body
            ? (body.dateOfJoining ?? null)
            : seed.dateOfJoining,
        dateOfExit:
          'dateOfExit' in body ? (body.dateOfExit ?? null) : seed.dateOfExit,
        mobilePlatform:
          'mobilePlatform' in body
            ? (body.mobilePlatform ?? null)
            : seed.mobilePlatform,
      });
      return detail(seed);
    },
  },
  {
    method: 'POST',
    path: '/core/employees/:employeeId/deactivate',
    handle: (req, params) => {
      const seed = find(params, req);
      if (seed.userId !== null) {
        problem(
          req,
          400,
          'Bad request',
          'This employee has an active sign-in account. Deactivate the user first.',
        );
      }
      seed.isActive = false;
      return detail(seed);
    },
  },
  {
    method: 'POST',
    path: '/core/employees/:employeeId/activate',
    handle: (req, params) => {
      const seed = find(params, req);
      seed.isActive = true;
      return detail(seed);
    },
  },
  { method: 'GET', path: '/core/companies', handle: () => companies },
  { method: 'GET', path: '/core/departments', handle: () => departments },
  { method: 'GET', path: '/core/designations', handle: () => designations },
];
