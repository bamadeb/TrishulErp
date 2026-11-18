"""Assign-reporting-manager request and the employee rows the screen lists."""

from datetime import date
from typing import Literal

from pydantic import Field

from trishul_api.common.schemas import ApiModel, InputModel, UtcDateTime

ReportingStatus = Literal["Active", "Inactive"]


class ReportingEmployee(ApiModel):
    """One employee on the Reporting Structure screen."""

    id: int
    code: str
    name: str
    designation: str
    department: str
    location: str
    manager_id: int | None
    level: str
    status: ReportingStatus
    manager_effective_from: date | None = None


class ReportingAssignmentCreate(InputModel):
    """Sets the live reporting manager and keeps the date and remarks."""

    employee_id: int
    reporting_manager_id: int
    effective_from: date
    remarks: str | None = Field(None, max_length=300)


class ReportingAssignmentSaved(ApiModel):
    employee_id: int
    previous_manager_id: int | None
    manager_id: int | None
    effective_from: date
    remarks: str | None


class ReportingRemovalCreate(InputModel):
    """Clears the live reporting manager and keeps the closed assignment."""

    employee_id: int
    effective_from: date
    remarks: str = Field(min_length=1, max_length=300)


class ReportingHistoryItem(ApiModel):
    """One saved change of an employee's reporting manager."""

    id: int
    previous_manager_id: int | None
    previous_manager_name: str | None
    manager_id: int | None
    manager_name: str | None
    effective_from: date
    effective_to: date | None
    remarks: str | None
    changed_by: str | None
    status: Literal["Active", "Closed"]
    created_at: UtcDateTime
