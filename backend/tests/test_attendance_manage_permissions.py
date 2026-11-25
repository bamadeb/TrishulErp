"""Attendance write endpoints must use explicit manage/finalize permissions.

Org-wide reads stay on core.employee.manage. Shift writes, rules saves, and
finalization lock require their dedicated codes — not implied by HR/ADMIN role.
"""

from __future__ import annotations

from collections.abc import Iterable

from fastapi.dependencies.models import Dependant
from fastapi.routing import APIRoute

from trishul_api.modules.hr.attendance.router import router

SHIFT_MANAGE = "hr.attendance.shift.manage"
RULES_MANAGE = "hr.attendance.rules.manage"
FINALIZE = "hr.attendance.finalize"
EMPLOYEE_MANAGE = "core.employee.manage"


def _permission_codes(dependant: Dependant) -> set[str]:
    """Collect codes closed over by require_permission(...) dependencies."""
    found: set[str] = set()
    stack: list[Dependant] = [dependant]
    while stack:
        current = stack.pop()
        stack.extend(current.dependencies)
        call = current.call
        if call is None or not getattr(call, "__closure__", None):
            continue
        for cell in call.__closure__ or ():
            value = cell.cell_contents
            if isinstance(value, tuple) and value and all(isinstance(item, str) for item in value):
                found.update(value)
            elif isinstance(value, str) and "." in value:
                found.add(value)
    return found


def _route(path: str, methods: Iterable[str]) -> APIRoute:
    wanted = {method.upper() for method in methods}
    for route in router.routes:
        if not isinstance(route, APIRoute):
            continue
        if route.path == path and wanted & set(route.methods or ()):
            return route
    raise AssertionError(f"No route {methods} {path}")


def test_shift_mutations_require_shift_manage() -> None:
    for path, methods in (
        ("/hr/attendance/shifts", ("POST",)),
        ("/hr/attendance/shifts/{shiftId}", ("PATCH", "DELETE")),
        ("/hr/attendance/shift-assignments", ("POST",)),
        ("/hr/attendance/shift-assignments/{assignmentId}", ("PATCH", "DELETE")),
    ):
        for method in methods:
            codes = _permission_codes(_route(path, (method,)).dependant)
            assert SHIFT_MANAGE in codes, f"{method} {path} missing {SHIFT_MANAGE}: {codes}"
            assert EMPLOYEE_MANAGE not in codes or SHIFT_MANAGE in codes


def test_rules_save_requires_rules_manage() -> None:
    codes = _permission_codes(_route("/hr/attendance/rules", ("PUT",)).dependant)
    assert RULES_MANAGE in codes
    assert EMPLOYEE_MANAGE not in codes


def test_finalization_lock_requires_finalize() -> None:
    codes = _permission_codes(_route("/hr/attendance/finalization/lock", ("POST",)).dependant)
    assert FINALIZE in codes
    assert EMPLOYEE_MANAGE not in codes


def test_org_reads_remain_on_employee_manage() -> None:
    for path, methods in (
        ("/hr/attendance/shifts", ("GET",)),
        ("/hr/attendance/rules", ("GET",)),
        ("/hr/attendance/finalization", ("GET",)),
        ("/hr/attendance/dashboard", ("GET",)),
        ("/hr/attendance/exceptions", ("GET",)),
        ("/hr/attendance/regularizations", ("GET",)),
    ):
        codes = _permission_codes(_route(path, methods).dependant)
        assert EMPLOYEE_MANAGE in codes, f"GET {path} should allow org HR view: {codes}"
        assert SHIFT_MANAGE not in codes
        assert RULES_MANAGE not in codes
        assert FINALIZE not in codes
