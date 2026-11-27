# Hand-written until the model generator accepts every migration type.
# Keep these columns in step with migration 0032_leave_masters.

"""Leave type settings and policies. Types, balances and requests stay on the generated tables."""

import datetime as dt
from decimal import Decimal

import sqlalchemy as sa
from sqlalchemy.dialects import mssql
from sqlalchemy.orm import Mapped, mapped_column

from trishul_api.db.models.base import Base
from trishul_api.db.models.generated.hr import Holiday


class LeaveTypeSetting(Base):
    """Extra leave-type rules stored beside the existing hr.leave_type row."""

    __tablename__ = "leave_type_setting"
    __table_args__ = {"schema": "hr"}

    leave_type_id: Mapped[int] = mapped_column(
        sa.BigInteger(), sa.ForeignKey("hr.leave_type.id"), primary_key=True
    )
    description: Mapped[str | None] = mapped_column(sa.NVARCHAR(400))
    accrual_applicable: Mapped[bool] = mapped_column(sa.Boolean(), server_default=sa.FetchedValue())
    half_day_allowed: Mapped[bool] = mapped_column(sa.Boolean(), server_default=sa.FetchedValue())
    attachment_required: Mapped[bool] = mapped_column(sa.Boolean(), server_default=sa.FetchedValue())
    max_consecutive_days: Mapped[int | None] = mapped_column(sa.SmallInteger())


class LeavePolicy(Base):
    """Who a set of leave entitlements applies to, and for which dates."""

    __tablename__ = "leave_policy"
    __table_args__ = {"schema": "hr"}

    id: Mapped[int] = mapped_column(sa.BigInteger(), primary_key=True)
    name: Mapped[str] = mapped_column(sa.NVARCHAR(80))
    employee_type: Mapped[str | None] = mapped_column(sa.NVARCHAR(30))
    department_id: Mapped[int | None] = mapped_column(sa.BigInteger(), sa.ForeignKey("hr.department.id"))
    branch_id: Mapped[int | None] = mapped_column(sa.BigInteger(), sa.ForeignKey("core.branch.id"))
    state_id: Mapped[int | None] = mapped_column(sa.BigInteger(), sa.ForeignKey("core.state.id"))
    year_basis: Mapped[str] = mapped_column(sa.NVARCHAR(20), default="FINANCIAL", server_default=sa.FetchedValue())
    assignment_mode: Mapped[str] = mapped_column(
        sa.NVARCHAR(20), default="AUTOMATIC", server_default=sa.FetchedValue()
    )
    applies_during_probation: Mapped[bool] = mapped_column(sa.Boolean(), server_default=sa.FetchedValue())
    negative_balance_allowed: Mapped[bool] = mapped_column(sa.Boolean(), server_default=sa.FetchedValue())
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


class LeavePolicyLine(Base):
    """Entitlement for one leave type inside a policy."""

    __tablename__ = "leave_policy_line"
    __table_args__ = {"schema": "hr"}

    id: Mapped[int] = mapped_column(sa.BigInteger(), primary_key=True)
    leave_policy_id: Mapped[int] = mapped_column(sa.BigInteger(), sa.ForeignKey("hr.leave_policy.id"))
    leave_type_id: Mapped[int] = mapped_column(sa.BigInteger(), sa.ForeignKey("hr.leave_type.id"))
    annual_entitlement: Mapped[Decimal] = mapped_column(sa.Numeric(6, 1))
    accrual_frequency: Mapped[str] = mapped_column(sa.NVARCHAR(20))
    carry_forward: Mapped[bool] = mapped_column(sa.Boolean(), server_default=sa.FetchedValue())
    max_accumulation: Mapped[Decimal | None] = mapped_column(sa.Numeric(6, 1))
    encashment_eligible: Mapped[bool] = mapped_column(sa.Boolean(), server_default=sa.FetchedValue())
    calculation_method: Mapped[str] = mapped_column(sa.NVARCHAR(20), default="FIXED", server_default=sa.FetchedValue())
    credit_days: Mapped[Decimal | None] = mapped_column(sa.Numeric(6, 1))
    qualifying_days_per_credit: Mapped[int | None] = mapped_column(sa.SmallInteger())
    minimum_qualifying_days: Mapped[int | None] = mapped_column(sa.SmallInteger())
    joining_year_rule: Mapped[str] = mapped_column(sa.NVARCHAR(30), default="NONE", server_default=sa.FetchedValue())
    minimum_service_months: Mapped[int | None] = mapped_column(sa.SmallInteger())
    adolescent_max_accumulation: Mapped[Decimal | None] = mapped_column(sa.Numeric(6, 1))
    exclude_boundary_holidays: Mapped[bool] = mapped_column(sa.Boolean(), server_default=sa.FetchedValue())
    document_required: Mapped[bool] = mapped_column(sa.Boolean(), server_default=sa.FetchedValue())
    benefit_class: Mapped[str] = mapped_column(sa.NVARCHAR(20), default="STANDARD", server_default=sa.FetchedValue())
    compensatory_basis: Mapped[str] = mapped_column(sa.NVARCHAR(30), default="NONE", server_default=sa.FetchedValue())
    compensatory_expiry_months: Mapped[int | None] = mapped_column(sa.SmallInteger())
    max_backdate_days: Mapped[int | None] = mapped_column(sa.SmallInteger())
    backdate_requires_authorization: Mapped[bool] = mapped_column(
        sa.Boolean(), nullable=False, default=False, server_default=sa.text("0")
    )
    created_at: Mapped[dt.datetime] = mapped_column(mssql.DATETIME2(0), server_default=sa.FetchedValue())
    created_by_user_id: Mapped[int | None] = mapped_column(sa.BigInteger())
    updated_at: Mapped[dt.datetime | None] = mapped_column(mssql.DATETIME2(0))
    updated_by_user_id: Mapped[int | None] = mapped_column(sa.BigInteger())
    is_active: Mapped[bool] = mapped_column(sa.Boolean(), server_default=sa.FetchedValue())
    row_version: Mapped[bytes] = mapped_column(
        mssql.ROWVERSION(), server_default=sa.FetchedValue(), server_onupdate=sa.FetchedValue()
    )

    __mapper_args__ = {"version_id_col": row_version, "version_id_generator": False}


def _version() -> Mapped[bytes]:
    return mapped_column(mssql.ROWVERSION(), server_default=sa.FetchedValue(), server_onupdate=sa.FetchedValue())


class LeavePolicyAssignment(Base):
    """An explicit employee assignment. Saving a policy does not create these rows."""

    __tablename__ = "leave_policy_assignment"
    __table_args__ = {"schema": "hr"}

    id: Mapped[int] = mapped_column(sa.BigInteger(), primary_key=True)
    leave_policy_id: Mapped[int] = mapped_column(sa.BigInteger(), sa.ForeignKey("hr.leave_policy.id"))
    employee_id: Mapped[int] = mapped_column(sa.BigInteger(), sa.ForeignKey("core.employee.id"))
    effective_from: Mapped[dt.date] = mapped_column(sa.Date())
    effective_to: Mapped[dt.date | None] = mapped_column(sa.Date())
    created_at: Mapped[dt.datetime] = mapped_column(mssql.DATETIME2(0), server_default=sa.FetchedValue())
    created_by_user_id: Mapped[int | None] = mapped_column(sa.BigInteger())
    updated_at: Mapped[dt.datetime | None] = mapped_column(mssql.DATETIME2(0))
    updated_by_user_id: Mapped[int | None] = mapped_column(sa.BigInteger())
    is_active: Mapped[bool] = mapped_column(sa.Boolean(), server_default=sa.FetchedValue())
    row_version: Mapped[bytes] = _version()

    __mapper_args__ = {"version_id_col": row_version, "version_id_generator": False}


class LeaveEntitlementRun(Base):
    """One controlled entitlement credit for an employee, policy line and year."""

    __tablename__ = "leave_entitlement_run"
    __table_args__ = {"schema": "hr"}

    id: Mapped[int] = mapped_column(sa.BigInteger(), primary_key=True)
    employee_id: Mapped[int] = mapped_column(sa.BigInteger(), sa.ForeignKey("core.employee.id"))
    leave_policy_line_id: Mapped[int] = mapped_column(sa.BigInteger(), sa.ForeignKey("hr.leave_policy_line.id"))
    leave_year: Mapped[int] = mapped_column(sa.SmallInteger())
    eligibility_days: Mapped[Decimal] = mapped_column(sa.Numeric(7, 1))
    days_worked: Mapped[Decimal] = mapped_column(sa.Numeric(7, 1))
    deemed_days: Mapped[Decimal] = mapped_column(sa.Numeric(7, 1))
    credited_days: Mapped[Decimal] = mapped_column(sa.Numeric(6, 1))
    created_at: Mapped[dt.datetime] = mapped_column(mssql.DATETIME2(0), server_default=sa.FetchedValue())
    created_by_user_id: Mapped[int | None] = mapped_column(sa.BigInteger())
    is_active: Mapped[bool] = mapped_column(sa.Boolean(), server_default=sa.FetchedValue())
    row_version: Mapped[bytes] = _version()

    __mapper_args__ = {"version_id_col": row_version, "version_id_generator": False}


class LeaveBalanceTransaction(Base):
    """Append-only credit, usage, expiry, adjustment or reversal. Existing balances are not overwritten."""

    __tablename__ = "leave_balance_transaction"
    __table_args__ = {"schema": "hr"}

    id: Mapped[int] = mapped_column(sa.BigInteger(), primary_key=True)
    employee_id: Mapped[int] = mapped_column(sa.BigInteger(), sa.ForeignKey("core.employee.id"))
    leave_type_id: Mapped[int] = mapped_column(sa.BigInteger(), sa.ForeignKey("hr.leave_type.id"))
    leave_year: Mapped[int] = mapped_column(sa.SmallInteger())
    leave_balance_id: Mapped[int | None] = mapped_column(sa.BigInteger(), sa.ForeignKey("hr.leave_balance.id"))
    kind: Mapped[str] = mapped_column(sa.NVARCHAR(20))
    days: Mapped[Decimal] = mapped_column(sa.Numeric(6, 1))
    remarks: Mapped[str | None] = mapped_column(sa.NVARCHAR(300))
    source_type: Mapped[str | None] = mapped_column(sa.NVARCHAR(40))
    source_id: Mapped[int | None] = mapped_column(sa.BigInteger())
    created_at: Mapped[dt.datetime] = mapped_column(mssql.DATETIME2(0), server_default=sa.FetchedValue())
    created_by_user_id: Mapped[int | None] = mapped_column(sa.BigInteger())
    is_active: Mapped[bool] = mapped_column(sa.Boolean(), server_default=sa.FetchedValue())
    row_version: Mapped[bytes] = _version()

    __mapper_args__ = {"version_id_col": row_version, "version_id_generator": False}


class LeaveWeeklyRestGrant(Base):
    """Statutory compensatory leave for one denied weekly holiday."""

    __tablename__ = "leave_weekly_rest_grant"
    __table_args__ = {"schema": "hr"}

    id: Mapped[int] = mapped_column(sa.BigInteger(), primary_key=True)
    employee_id: Mapped[int] = mapped_column(sa.BigInteger(), sa.ForeignKey("core.employee.id"))
    leave_policy_line_id: Mapped[int] = mapped_column(sa.BigInteger(), sa.ForeignKey("hr.leave_policy_line.id"))
    original_holiday_date: Mapped[dt.date] = mapped_column(sa.Date())
    granted_on: Mapped[dt.date] = mapped_column(sa.Date())
    expires_on: Mapped[dt.date] = mapped_column(sa.Date())
    days: Mapped[Decimal] = mapped_column(sa.Numeric(4, 1))
    created_at: Mapped[dt.datetime] = mapped_column(mssql.DATETIME2(0), server_default=sa.FetchedValue())
    created_by_user_id: Mapped[int | None] = mapped_column(sa.BigInteger())
    is_active: Mapped[bool] = mapped_column(sa.Boolean(), server_default=sa.FetchedValue())
    row_version: Mapped[bytes] = _version()

    __mapper_args__ = {"version_id_col": row_version, "version_id_generator": False}


class CompOffAuthorization(Base):
    """Manager authorization to work a weekly off, company holiday, or declared non-working day."""

    __tablename__ = "comp_off_authorization"
    __table_args__ = {"schema": "hr"}

    id: Mapped[int] = mapped_column(sa.BigInteger(), primary_key=True)
    employee_id: Mapped[int] = mapped_column(sa.BigInteger(), sa.ForeignKey("core.employee.id"))
    work_date: Mapped[dt.date] = mapped_column(sa.Date())
    day_kind: Mapped[str] = mapped_column(sa.NVARCHAR(20))
    status: Mapped[str] = mapped_column(sa.NVARCHAR(20))
    remarks: Mapped[str | None] = mapped_column(sa.NVARCHAR(300))
    regularization_id: Mapped[int | None] = mapped_column(sa.BigInteger())
    authorized_by_user_id: Mapped[int | None] = mapped_column(sa.BigInteger())
    authorized_at: Mapped[dt.datetime] = mapped_column(mssql.DATETIME2(0))
    certified_by_user_id: Mapped[int | None] = mapped_column(sa.BigInteger())
    certified_at: Mapped[dt.datetime | None] = mapped_column(mssql.DATETIME2(0))
    created_at: Mapped[dt.datetime] = mapped_column(mssql.DATETIME2(0), server_default=sa.FetchedValue())
    created_by_user_id: Mapped[int | None] = mapped_column(sa.BigInteger())
    updated_at: Mapped[dt.datetime | None] = mapped_column(mssql.DATETIME2(0))
    updated_by_user_id: Mapped[int | None] = mapped_column(sa.BigInteger())
    is_active: Mapped[bool] = mapped_column(sa.Boolean(), server_default=sa.FetchedValue())
    row_version: Mapped[bytes] = _version()

    __mapper_args__ = {"version_id_col": row_version, "version_id_generator": False}


class CompOffCredit(Base):
    """One Comp Off credit. Unused days lapse 90 days after the credit date."""

    __tablename__ = "comp_off_credit"
    __table_args__ = {"schema": "hr"}

    id: Mapped[int] = mapped_column(sa.BigInteger(), primary_key=True)
    authorization_id: Mapped[int | None] = mapped_column(
        sa.BigInteger(), sa.ForeignKey("hr.comp_off_authorization.id")
    )
    employee_id: Mapped[int] = mapped_column(sa.BigInteger(), sa.ForeignKey("core.employee.id"))
    leave_type_id: Mapped[int] = mapped_column(sa.BigInteger(), sa.ForeignKey("hr.leave_type.id"))
    work_date: Mapped[dt.date] = mapped_column(sa.Date())
    day_kind: Mapped[str] = mapped_column(sa.NVARCHAR(20))
    credited_on: Mapped[dt.date] = mapped_column(sa.Date())
    expires_on: Mapped[dt.date] = mapped_column(sa.Date())
    days: Mapped[Decimal] = mapped_column(sa.Numeric(4, 1))
    consumed_days: Mapped[Decimal] = mapped_column(sa.Numeric(4, 1), server_default=sa.FetchedValue())
    expired_days: Mapped[Decimal] = mapped_column(sa.Numeric(4, 1), server_default=sa.FetchedValue())
    status: Mapped[str] = mapped_column(sa.NVARCHAR(20))
    created_at: Mapped[dt.datetime] = mapped_column(mssql.DATETIME2(0), server_default=sa.FetchedValue())
    created_by_user_id: Mapped[int | None] = mapped_column(sa.BigInteger())
    updated_at: Mapped[dt.datetime | None] = mapped_column(mssql.DATETIME2(0))
    updated_by_user_id: Mapped[int | None] = mapped_column(sa.BigInteger())
    is_active: Mapped[bool] = mapped_column(sa.Boolean(), server_default=sa.FetchedValue())
    row_version: Mapped[bytes] = _version()

    __mapper_args__ = {"version_id_col": row_version, "version_id_generator": False}


class CompOffLedger(Base):
    """Append-only credit, consumption, expiry, adjustment, and reversal history."""

    __tablename__ = "comp_off_ledger"
    __table_args__ = {"schema": "hr"}

    id: Mapped[int] = mapped_column(sa.BigInteger(), primary_key=True)
    credit_id: Mapped[int] = mapped_column(sa.BigInteger(), sa.ForeignKey("hr.comp_off_credit.id"))
    employee_id: Mapped[int] = mapped_column(sa.BigInteger(), sa.ForeignKey("core.employee.id"))
    kind: Mapped[str] = mapped_column(sa.NVARCHAR(20))
    days: Mapped[Decimal] = mapped_column(sa.Numeric(4, 1))
    leave_request_id: Mapped[int | None] = mapped_column(sa.BigInteger())
    remarks: Mapped[str | None] = mapped_column(sa.NVARCHAR(300))
    created_at: Mapped[dt.datetime] = mapped_column(mssql.DATETIME2(0), server_default=sa.FetchedValue())
    created_by_user_id: Mapped[int | None] = mapped_column(sa.BigInteger())
    is_active: Mapped[bool] = mapped_column(sa.Boolean(), server_default=sa.FetchedValue())
    row_version: Mapped[bytes] = _version()

    __mapper_args__ = {"version_id_col": row_version, "version_id_generator": False}


class LeaveAttendanceClass(Base):
    """How one existing attendance status counts. Unmapped statuses block Earned Leave calculation."""

    __tablename__ = "leave_attendance_class"
    __table_args__ = {"schema": "hr"}

    attendance_status: Mapped[str] = mapped_column(sa.NVARCHAR(30), primary_key=True)
    counts_for_eligibility: Mapped[bool] = mapped_column(sa.Boolean(), server_default=sa.FetchedValue())
    counts_as_days_worked: Mapped[bool] = mapped_column(sa.Boolean(), server_default=sa.FetchedValue())
    is_deemed_work: Mapped[bool] = mapped_column(sa.Boolean(), server_default=sa.FetchedValue())
    day_weight: Mapped[Decimal | None] = mapped_column(sa.Numeric(3, 1))
    created_at: Mapped[dt.datetime] = mapped_column(mssql.DATETIME2(0), server_default=sa.FetchedValue())
    created_by_user_id: Mapped[int | None] = mapped_column(sa.BigInteger())
    updated_at: Mapped[dt.datetime | None] = mapped_column(mssql.DATETIME2(0))
    updated_by_user_id: Mapped[int | None] = mapped_column(sa.BigInteger())
    is_active: Mapped[bool] = mapped_column(sa.Boolean(), server_default=sa.FetchedValue())
    row_version: Mapped[bytes] = _version()

    __mapper_args__ = {"version_id_col": row_version, "version_id_generator": False}


def _extend_holiday_table() -> None:
    """State and notification columns added by 0036. The generated Holiday class stays untouched."""
    table = Holiday.__table__
    if "state_id" in table.c:
        return
    table.append_column(sa.Column("state_id", sa.BigInteger(), nullable=True))
    table.append_column(sa.Column("source_notification_no", sa.NVARCHAR(40), nullable=True))
    table.append_column(sa.Column("source_notification_date", sa.Date(), nullable=True))
    table.append_column(sa.Column("description", sa.NVARCHAR(400), nullable=True))


_extend_holiday_table()
