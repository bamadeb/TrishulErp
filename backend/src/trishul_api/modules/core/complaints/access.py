"""Who may see and work which complaints.

* Every signed-in user raises complaints and sees their own (and only their own) complaints, whatever their role
  (core.complaint.raise is still granted to every role but no longer checked).
* A department's leaders see and work the department's complaints. The leaders are the department's head
  (hr.department.head_employee_id) and every employee of the department whose role has core.complaint.manage.
* core.complaint.manage_all (Super Admin) sees and works every department's complaints and maintains the
  issue types.

The person who raised a complaint can always open it, whatever their role does today.
"""

from dataclasses import dataclass

from sqlalchemy import Select, select
from sqlalchemy.orm import Session

from trishul_api.auth import CurrentUser
from trishul_api.db.models import AppUser, Complaint, Department, Employee, Permission, Role, RolePermission, UserRole

RAISE = "core.complaint.raise"
MANAGE = "core.complaint.manage"
MANAGE_ALL = "core.complaint.manage_all"
SYSTEM_USERNAME = "system"


@dataclass(frozen=True)
class ComplaintAccess:
    all_departments: bool
    led_department_ids: frozenset[int]
    """Departments the user leads (as head, or with core.complaint.manage in their own department)."""
    head_department_ids: frozenset[int]

    @property
    def manages_any(self) -> bool:
        return self.all_departments or bool(self.led_department_ids)

    def manages(self, department_id: int) -> bool:
        return self.all_departments or department_id in self.led_department_ids


def complaint_access(db: Session, user: CurrentUser) -> ComplaintAccess:
    heads: set[int] = set()
    led: set[int] = set()
    if user.employee_id is not None:
        heads = set(
            db.scalars(
                select(Department.id).where(Department.head_employee_id == user.employee_id, Department.is_active)
            )
        )
        led |= heads
        if user.can(MANAGE):
            own = db.scalar(
                select(Employee.department_id)
                .join(Department, Department.id == Employee.department_id)
                .where(Employee.id == user.employee_id, Department.is_active)
            )
            if own is not None:
                led.add(own)
    return ComplaintAccess(
        all_departments=user.can(MANAGE_ALL),
        led_department_ids=frozenset(led),
        head_department_ids=frozenset(heads),
    )


def can_open(db: Session, user: CurrentUser, complaint: Complaint) -> bool:
    return complaint.raised_by_user_id == user.id or complaint_access(db, user).manages(complaint.department_id)


def _active_users(statement: Select[int]) -> Select[int]:
    return statement.where(AppUser.is_active, ~AppUser.is_locked, AppUser.username != SYSTEM_USERNAME)


def department_leader_user_ids(db: Session, department_id: int) -> set[int]:
    """Active logins of the department's head and of its employees whose role has core.complaint.manage."""
    users: set[int] = set()
    head = db.scalar(select(Department.head_employee_id).where(Department.id == department_id))
    if head is not None:
        users |= set(db.scalars(_active_users(select(AppUser.id).where(AppUser.employee_id == head))))
    managers = _active_users(
        select(AppUser.id)
        .distinct()
        .join(Employee, Employee.id == AppUser.employee_id)
        .join(UserRole, UserRole.app_user_id == AppUser.id)
        .join(Role, Role.id == UserRole.role_id)
        .join(RolePermission, RolePermission.role_id == Role.id)
        .join(Permission, Permission.id == RolePermission.permission_id)
        .where(
            Employee.department_id == department_id,
            Employee.is_active,
            UserRole.is_active,
            Role.is_active,
            RolePermission.is_active,
            Permission.is_active,
            Permission.code == MANAGE,
        )
    )
    users |= set(db.scalars(managers))
    return users


def super_admin_user_ids(db: Session) -> set[int]:
    """Active logins whose role has core.complaint.manage_all: told when a department has no leader."""
    statement = _active_users(
        select(AppUser.id)
        .distinct()
        .join(UserRole, UserRole.app_user_id == AppUser.id)
        .join(Role, Role.id == UserRole.role_id)
        .join(RolePermission, RolePermission.role_id == Role.id)
        .join(Permission, Permission.id == RolePermission.permission_id)
        .where(
            UserRole.is_active,
            Role.is_active,
            RolePermission.is_active,
            Permission.is_active,
            Permission.code == MANAGE_ALL,
        )
    )
    return set(db.scalars(statement))
