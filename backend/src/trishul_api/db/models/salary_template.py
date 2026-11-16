# Hand-written until the model generator is re-run. Keep these columns in step with
# migration 0029_salary_templates.

"""Reusable salary packages. Payroll still reads hr.salary_structure, not this table."""

import datetime as dt
from decimal import Decimal

import sqlalchemy as sa
from sqlalchemy.dialects import mssql
from sqlalchemy.orm import Mapped, mapped_column

from trishul_api.db.models.base import Audited, Base


class SalaryTemplate(Audited, Base):
    """A named package of salary components. Editing it does not change saved structures."""

    __tablename__ = "salary_template"
    __table_args__ = {"schema": "hr"}

    id: Mapped[int] = mapped_column(sa.BigInteger(), primary_key=True)
    code: Mapped[str] = mapped_column(sa.NVARCHAR(20))
    name: Mapped[str] = mapped_column(sa.NVARCHAR(80))
    description: Mapped[str | None] = mapped_column(sa.NVARCHAR(400))
    template_type: Mapped[str] = mapped_column(sa.NVARCHAR(20))
    employee_category: Mapped[str | None] = mapped_column(sa.NVARCHAR(30))
    department_id: Mapped[int | None] = mapped_column(sa.BigInteger(), sa.ForeignKey("hr.department.id"))
    designation_id: Mapped[int | None] = mapped_column(sa.BigInteger(), sa.ForeignKey("hr.designation.id"))
    effective_from: Mapped[dt.date] = mapped_column(sa.Date())
    effective_to: Mapped[dt.date | None] = mapped_column(sa.Date())
    created_at: Mapped[dt.datetime] = mapped_column(mssql.DATETIME2(0), server_default=sa.FetchedValue())
    created_by_user_id: Mapped[int | None] = mapped_column(sa.BigInteger())
    updated_at: Mapped[dt.datetime | None] = mapped_column(mssql.DATETIME2(0))
    updated_by_user_id: Mapped[int | None] = mapped_column(sa.BigInteger())
    is_active: Mapped[bool] = mapped_column(sa.Boolean(), server_default=sa.FetchedValue())
    row_version: Mapped[bytes] = mapped_column(
        mssql.ROWVERSION(), server_default=sa.FetchedValue(), server_onupdate=sa.FetchedValue()
    )

    __mapper_args__ = {"version_id_col": row_version, "version_id_generator": False}


class SalaryTemplateLine(Audited, Base):
    """Template-specific amount, percentage or formula for one existing salary component."""

    __tablename__ = "salary_template_line"
    __table_args__ = {"schema": "hr"}

    id: Mapped[int] = mapped_column(sa.BigInteger(), primary_key=True)
    salary_template_id: Mapped[int] = mapped_column(sa.BigInteger(), sa.ForeignKey("hr.salary_template.id"))
    salary_component_id: Mapped[int] = mapped_column(sa.BigInteger(), sa.ForeignKey("hr.salary_component.id"))
    monthly_amount: Mapped[Decimal | None] = mapped_column(sa.Numeric(18, 2))
    percentage: Mapped[Decimal | None] = mapped_column(sa.Numeric(5, 2))
    formula: Mapped[str | None] = mapped_column(sa.NVARCHAR(300))
    display_order: Mapped[int] = mapped_column(sa.Integer(), server_default=sa.FetchedValue())
    created_at: Mapped[dt.datetime] = mapped_column(mssql.DATETIME2(0), server_default=sa.FetchedValue())
    created_by_user_id: Mapped[int | None] = mapped_column(sa.BigInteger())
    updated_at: Mapped[dt.datetime | None] = mapped_column(mssql.DATETIME2(0))
    updated_by_user_id: Mapped[int | None] = mapped_column(sa.BigInteger())
    is_active: Mapped[bool] = mapped_column(sa.Boolean(), server_default=sa.FetchedValue())
    row_version: Mapped[bytes] = mapped_column(
        mssql.ROWVERSION(), server_default=sa.FetchedValue(), server_onupdate=sa.FetchedValue()
    )

    __mapper_args__ = {"version_id_col": row_version, "version_id_generator": False}


class SalaryTemplateDesignation(Base):
    """Designations that may use this template. The saved employee structure is unchanged."""

    __tablename__ = "salary_template_designation"
    __table_args__ = {"schema": "hr"}

    salary_template_id: Mapped[int] = mapped_column(
        sa.BigInteger(), sa.ForeignKey("hr.salary_template.id"), primary_key=True
    )
    designation_id: Mapped[int] = mapped_column(sa.BigInteger(), sa.ForeignKey("hr.designation.id"), primary_key=True)


class SalaryTemplateGrade(Base):
    """Grades that may use this template. Grade text matches hr.designation.grade."""

    __tablename__ = "salary_template_grade"
    __table_args__ = {"schema": "hr"}

    salary_template_id: Mapped[int] = mapped_column(
        sa.BigInteger(), sa.ForeignKey("hr.salary_template.id"), primary_key=True
    )
    grade: Mapped[str] = mapped_column(sa.NVARCHAR(10), primary_key=True)


class SalaryTemplateAssignment(Audited, Base):
    """Links one saved salary structure to the template that filled it. The structure keeps its own lines."""

    __tablename__ = "salary_template_assignment"
    __table_args__ = {"schema": "hr"}

    id: Mapped[int] = mapped_column(sa.BigInteger(), primary_key=True)
    salary_template_id: Mapped[int] = mapped_column(sa.BigInteger(), sa.ForeignKey("hr.salary_template.id"))
    salary_structure_id: Mapped[int] = mapped_column(sa.BigInteger(), sa.ForeignKey("hr.salary_structure.id"))
    employee_id: Mapped[int] = mapped_column(sa.BigInteger(), sa.ForeignKey("core.employee.id"))
    created_at: Mapped[dt.datetime] = mapped_column(mssql.DATETIME2(0), server_default=sa.FetchedValue())
    created_by_user_id: Mapped[int | None] = mapped_column(sa.BigInteger())
    updated_at: Mapped[dt.datetime | None] = mapped_column(mssql.DATETIME2(0))
    updated_by_user_id: Mapped[int | None] = mapped_column(sa.BigInteger())
    is_active: Mapped[bool] = mapped_column(sa.Boolean(), server_default=sa.FetchedValue())
    row_version: Mapped[bytes] = mapped_column(
        mssql.ROWVERSION(), server_default=sa.FetchedValue(), server_onupdate=sa.FetchedValue()
    )

    __mapper_args__ = {"version_id_col": row_version, "version_id_generator": False}
