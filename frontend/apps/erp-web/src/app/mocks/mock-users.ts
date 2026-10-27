import { HttpErrorResponse, HttpRequest } from '@angular/common/http';
import {
  EmployeeOption,
  PageUserListItem,
  RoleGrant,
  RoleOption,
  UserCreate,
  UserCreated,
  UserDetail,
  UserUpdate,
} from '@trishul/core-api';
import { MockRoute } from '@trishul/core-http';

/** In-memory /core/users, /core/roles and /core/employees for mock mode and the end-to-end tests. */

const roles: RoleOption[] = [
  { id: 1, code: 'ADMIN', name: 'Administrator', description: null },
  { id: 2, code: 'BACK_OFFICE', name: 'Back office', description: null },
  { id: 3, code: 'TEAM_LEAD', name: 'Service Team Lead', description: null },
  {
    id: 4,
    code: 'SERVICE_ENGINEER',
    name: 'Service engineer',
    description: null,
  },
];
const branchNames: Record<number, string> = {
  1: 'Pune',
  2: 'Mumbai',
  3: 'Nagpur',
};

let nextId = 3;
let version = 1;
const rowVersion = () => btoa(`mock-rv-${version++}`);
const now = () => new Date().toISOString();

function grant(roleId: number, branchId: number | null): RoleGrant {
  const role = roles.find((r) => r.id === roleId) ?? roles[0];
  return {
    roleId,
    roleCode: role.code,
    roleName: role.name,
    branchId,
    branchName: branchId ? (branchNames[branchId] ?? null) : null,
  };
}

type MockEmployee = Omit<EmployeeOption, 'linkedUserId'>;

const employees: MockEmployee[] = [
  {
    id: 10,
    employeeCode: 'EMP0010',
    firstName: 'Rahul',
    lastName: 'Patil',
    mobile: '9822000010',
    email: 'rahul.patil@trishul.co',
    designation: 'Team Lead',
    department: 'Service',
    branchName: 'Pune',
  },
  {
    id: 11,
    employeeCode: 'EMP0011',
    firstName: 'Sneha',
    lastName: 'Kulkarni',
    mobile: '9822000011',
    email: 'sneha.k@trishul.co',
    designation: 'Back office executive',
    department: 'Service',
    branchName: 'Pune',
  },
  {
    id: 12,
    employeeCode: 'EMP0012',
    firstName: 'Amit',
    lastName: 'Joshi',
    mobile: null,
    email: null,
    designation: 'Service engineer',
    department: 'Service',
    branchName: 'Mumbai',
  },
];

const NOT_LINKED = {
  employeeId: null,
  employeeCode: null,
  firstName: null,
  lastName: null,
  designation: null,
  department: null,
};

/** The user's employee fields, phone and display name, as the API derives them. */
function linkEmployee(user: UserDetail, employeeId: number | null): void {
  const employee = employees.find((e) => e.id === employeeId);
  Object.assign(
    user,
    employee
      ? {
          employeeId: employee.id,
          employeeCode: employee.employeeCode,
          firstName: employee.firstName,
          lastName: employee.lastName,
          designation: employee.designation,
          department: employee.department,
        }
      : NOT_LINKED,
  );
  user.phone = user.mobile ?? employee?.mobile ?? null;
  user.displayName = employee
    ? [employee.firstName, employee.lastName].filter(Boolean).join(' ')
    : user.username;
}

const users: UserDetail[] = [
  {
    id: 1,
    username: 'demo.admin',
    email: 'demo.admin@example.com',
    mobile: null,
    phone: null,
    displayName: 'Demo Admin',
    ...NOT_LINKED,
    isActive: true,
    isLocked: false,
    createdAt: now(),
    roles: [grant(1, null)],
    defaultBranchId: 1,
    principalIds: [1, 2],
    signInStatus: 'development',
    rowVersion: rowVersion(),
  },
  {
    id: 2,
    username: 'rahul.patil@trishul.co',
    email: 'rahul.patil@trishul.co',
    mobile: '9876543210',
    phone: '9876543210',
    displayName: 'Rahul Patil',
    employeeId: 10,
    employeeCode: 'EMP0010',
    firstName: 'Rahul',
    lastName: 'Patil',
    designation: 'Team Lead',
    department: 'Service',
    isActive: true,
    isLocked: false,
    createdAt: now(),
    roles: [grant(3, 1)],
    defaultBranchId: 1,
    principalIds: [1],
    signInStatus: 'active',
    rowVersion: rowVersion(),
  },
];

function checkEmployee(
  req: HttpRequest<unknown>,
  employeeId: number | null | undefined,
  userId?: number,
): void {
  const other = users.find(
    (u) => employeeId && u.employeeId === employeeId && u.id !== userId,
  );
  if (other) {
    problem(
      req,
      409,
      'Already exists',
      `This employee is already linked to user ${other.username}.`,
    );
  }
}

function find(
  params: Record<string, string>,
  req: HttpRequest<unknown>,
): UserDetail {
  const user = users.find((u) => u.id === Number(params['userId']));
  if (!user) {
    throw new HttpErrorResponse({
      status: 404,
      url: req.url,
      error: { status: 404, title: 'Not found', detail: 'User not found.' },
    });
  }
  return user;
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

export const mockUserRoutes: MockRoute[] = [
  {
    method: 'GET',
    path: '/core/users',
    handle: (req): PageUserListItem => {
      const page = Number(req.params.get('page') ?? 1);
      const pageSize = Number(req.params.get('pageSize') ?? 20);
      const search = (req.params.get('search') ?? '').toLowerCase();
      const status = req.params.get('status') ?? 'active';
      const roleId = req.params.get('roleId');
      const rows = users.filter(
        (u) =>
          (status === 'all' || u.isActive === (status === 'active')) &&
          (!roleId || u.roles.some((g) => g.roleId === Number(roleId))) &&
          (!search ||
            [u.username, u.displayName, u.phone, u.employeeCode].some((v) =>
              v?.toLowerCase().includes(search),
            )),
      );
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
    path: '/core/users/:userId',
    handle: (req, params) => find(params, req),
  },
  {
    method: 'POST',
    path: '/core/users',
    handle: (req): UserCreated => {
      const body = req.body as UserCreate;
      const email = body.email.trim().toLowerCase();
      if (users.some((u) => u.username === email)) {
        problem(
          req,
          409,
          'Already exists',
          'A user with this email already exists.',
        );
      }
      checkEmployee(req, body.employeeId);
      const user: UserDetail = {
        id: nextId++,
        username: email,
        email,
        mobile: body.mobile ?? null,
        phone: null,
        displayName: email,
        ...NOT_LINKED,
        isActive: true,
        isLocked: false,
        createdAt: now(),
        roles: body.roles.map((r) => grant(r.roleId, r.branchId ?? null)),
        defaultBranchId: body.defaultBranchId ?? null,
        principalIds: body.principalIds ?? [],
        signInStatus: 'password-change-required',
        rowVersion: rowVersion(),
      };
      linkEmployee(user, body.employeeId ?? null);
      users.push(user);
      return {
        ...user,
        temporaryPassword: body.delivery === 'show' ? 'Mock#Temp12345' : null,
      };
    },
  },
  {
    method: 'PATCH',
    path: '/core/users/:userId',
    handle: (req, params) => {
      const user = find(params, req);
      if (req.headers.get('If-Match') !== `"${user.rowVersion}"`) {
        problem(
          req,
          409,
          'Record changed',
          'Another user changed this record after you opened it.',
        );
      }
      const body = req.body as UserUpdate;
      checkEmployee(req, body.employeeId, user.id);
      if ('mobile' in body) user.mobile = body.mobile ?? null;
      if ('defaultBranchId' in body)
        user.defaultBranchId = body.defaultBranchId ?? null;
      if (body.roles)
        user.roles = body.roles.map((r) => grant(r.roleId, r.branchId ?? null));
      if (body.principalIds) user.principalIds = body.principalIds;
      linkEmployee(
        user,
        'employeeId' in body ? (body.employeeId ?? null) : user.employeeId,
      );
      user.rowVersion = rowVersion();
      return user;
    },
  },
  {
    method: 'POST',
    path: '/core/users/:userId/deactivate',
    handle: (req, params) => {
      const user = find(params, req);
      if (user.id === 1)
        problem(
          req,
          400,
          'Bad request',
          "You can't deactivate your own account.",
        );
      Object.assign(user, {
        isActive: false,
        signInStatus: 'disabled',
        rowVersion: rowVersion(),
      });
      return user;
    },
  },
  {
    method: 'POST',
    path: '/core/users/:userId/activate',
    handle: (req, params) => {
      const user = find(params, req);
      Object.assign(user, {
        isActive: true,
        signInStatus: 'active',
        rowVersion: rowVersion(),
      });
      return user;
    },
  },
  {
    method: 'POST',
    path: '/core/users/:userId/reset-password',
    handle: (req, params) => {
      const user = find(params, req);
      const delivery = (req.body as { delivery: 'email' | 'show' }).delivery;
      user.signInStatus =
        delivery === 'show' ? 'password-change-required' : 'reset-required';
      return {
        delivery,
        temporaryPassword: delivery === 'show' ? 'Mock#Reset12345' : null,
        signInStatus: user.signInStatus,
      };
    },
  },
  { method: 'GET', path: '/core/roles', handle: () => roles },
  {
    method: 'GET',
    path: '/core/employees',
    handle: (req): EmployeeOption[] => {
      const search = (req.params.get('search') ?? '').toLowerCase();
      return employees
        .filter((e) =>
          [
            e.employeeCode,
            `${e.firstName} ${e.lastName ?? ''}`,
            e.mobile,
            e.email,
          ].some((v) => !search || v?.toLowerCase().includes(search)),
        )
        .map((e) => ({
          ...e,
          linkedUserId: users.find((u) => u.employeeId === e.id)?.id ?? null,
        }));
    },
  },
];
