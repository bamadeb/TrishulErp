"""Reporting-manager assignment history. The live manager stays on core.employee.reporting_manager_id."""

import datetime as dt

import sqlalchemy as sa
from sqlalchemy.dialects import mssql
from sqlalchemy.orm import Mapped, mapped_column

from trishul_api.db.models.base import Base


class ReportingAssignment(Base):
    """One saved change of who an employee reports to."""

    __tablename__ = "reporting_assignment"
    __table_args__ = {"schema": "hr"}

    id: Mapped[int] = mapped_column(sa.BigInteger(), primary_key=True)
    employee_id: Mapped[int] = mapped_column(sa.BigInteger(), sa.ForeignKey("core.employee.id"))
    previous_manager_id: Mapped[int | None] = mapped_column(sa.BigInteger(), sa.ForeignKey("core.employee.id"))
    manager_id: Mapped[int | None] = mapped_column(sa.BigInteger(), sa.ForeignKey("core.employee.id"))
    effective_from: Mapped[dt.date] = mapped_column(sa.Date())
    effective_to: Mapped[dt.date | None] = mapped_column(sa.Date())
    remarks: Mapped[str | None] = mapped_column(sa.NVARCHAR(300))
    created_at: Mapped[dt.datetime] = mapped_column(mssql.DATETIME2(0), server_default=sa.FetchedValue())
    created_by_user_id: Mapped[int | None] = mapped_column(sa.BigInteger())
    is_active: Mapped[bool] = mapped_column(sa.Boolean(), server_default=sa.FetchedValue())
