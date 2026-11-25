# Hand-written until the model generator is re-run. Keep these columns in step with
# migration 0048_complaints.

"""Complaint management: issue types per department, complaints and their history."""

import datetime as dt
from typing import Literal

import sqlalchemy as sa
from sqlalchemy.dialects import mssql
from sqlalchemy.orm import Mapped, declared_attr, mapped_column

from trishul_api.db.models.base import Audited, Base

_SCHEMA = {"schema": "core"}

ComplaintStatus = Literal["Open", "In Progress", "On Hold", "Resolved", "Closed"]
ComplaintHistoryAction = Literal["Raised", "Status changed", "Note"]


class _Standard:
    """created/updated/is_active/row_version, as on every Trishul table."""

    created_at: Mapped[dt.datetime] = mapped_column(mssql.DATETIME2(0), server_default=sa.FetchedValue())
    created_by_user_id: Mapped[int | None] = mapped_column(sa.BigInteger())
    updated_at: Mapped[dt.datetime | None] = mapped_column(mssql.DATETIME2(0))
    updated_by_user_id: Mapped[int | None] = mapped_column(sa.BigInteger())
    is_active: Mapped[bool] = mapped_column(sa.Boolean(), server_default=sa.FetchedValue())
    row_version: Mapped[bytes] = mapped_column(
        mssql.ROWVERSION(), server_default=sa.FetchedValue(), server_onupdate=sa.FetchedValue()
    )

    @declared_attr.directive
    def __mapper_args__(cls) -> dict[str, object]:
        return {"version_id_col": cls.__table__.c.row_version, "version_id_generator": False}  # type: ignore[attr-defined]


class ComplaintIssueType(Audited, _Standard, Base):
    """An issue type a complaint to a department can be about."""

    __tablename__ = "complaint_issue_type"
    __table_args__ = _SCHEMA

    id: Mapped[int] = mapped_column(sa.BigInteger(), primary_key=True)
    department_id: Mapped[int] = mapped_column(sa.BigInteger(), sa.ForeignKey("hr.department.id"))
    name: Mapped[str] = mapped_column(sa.NVARCHAR(80))
    description: Mapped[str | None] = mapped_column(sa.NVARCHAR(300))
    sort_order: Mapped[int] = mapped_column(sa.Integer(), server_default=sa.FetchedValue())


class Complaint(Audited, _Standard, Base):
    """A complaint raised by an employee to a department."""

    __tablename__ = "complaint"
    __table_args__ = _SCHEMA

    id: Mapped[int] = mapped_column(sa.BigInteger(), primary_key=True)
    company_id: Mapped[int] = mapped_column(sa.BigInteger(), sa.ForeignKey("core.company.id"))
    complaint_no: Mapped[str] = mapped_column(sa.NVARCHAR(30))
    department_id: Mapped[int] = mapped_column(sa.BigInteger(), sa.ForeignKey("hr.department.id"))
    issue_type_id: Mapped[int] = mapped_column(sa.BigInteger(), sa.ForeignKey("core.complaint_issue_type.id"))
    description: Mapped[str] = mapped_column(sa.NVARCHAR(2000))
    status: Mapped[ComplaintStatus] = mapped_column(sa.NVARCHAR(20), server_default=sa.FetchedValue())
    raised_by_user_id: Mapped[int] = mapped_column(sa.BigInteger(), sa.ForeignKey("core.app_user.id"))
    raised_by_employee_id: Mapped[int | None] = mapped_column(sa.BigInteger(), sa.ForeignKey("core.employee.id"))
    branch_id: Mapped[int | None] = mapped_column(sa.BigInteger(), sa.ForeignKey("core.branch.id"))
    raised_at: Mapped[dt.datetime] = mapped_column(mssql.DATETIME2(0))
    raised_via: Mapped[str | None] = mapped_column(sa.NVARCHAR(10), doc="Web | Android | iOS | API")
    status_changed_at: Mapped[dt.datetime | None] = mapped_column(mssql.DATETIME2(0))
    resolved_at: Mapped[dt.datetime | None] = mapped_column(mssql.DATETIME2(0))
    closed_at: Mapped[dt.datetime | None] = mapped_column(mssql.DATETIME2(0))


class ComplaintHistory(Base):
    """Append-only: the complaint was raised, its status changed, or a note was added."""

    __tablename__ = "complaint_history"
    __table_args__ = _SCHEMA

    id: Mapped[int] = mapped_column(sa.BigInteger(), primary_key=True)
    complaint_id: Mapped[int] = mapped_column(sa.BigInteger(), sa.ForeignKey("core.complaint.id"))
    action: Mapped[ComplaintHistoryAction] = mapped_column(sa.NVARCHAR(20))
    from_status: Mapped[str | None] = mapped_column(sa.NVARCHAR(20))
    to_status: Mapped[ComplaintStatus] = mapped_column(sa.NVARCHAR(20))
    note: Mapped[str | None] = mapped_column(sa.NVARCHAR(1000))
    changed_by_user_id: Mapped[int] = mapped_column(sa.BigInteger(), sa.ForeignKey("core.app_user.id"))
    changed_at: Mapped[dt.datetime] = mapped_column(mssql.DATETIME2(0))
