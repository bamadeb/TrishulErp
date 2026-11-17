# Hand-written until the model generator is re-run. Keep these columns in step with
# migration 0040_asc_visit_days.

"""ASC visit days: one row per service call per day an engineer was on site for it."""

import datetime as dt

import sqlalchemy as sa
from sqlalchemy.dialects import mssql
from sqlalchemy.orm import Mapped, mapped_column

from trishul_api.db.models.base import Audited, Base


class ContractVisitDay(Audited, Base):
    """A day one or more engineers worked on site for an ASC call: that day used one ASC visit."""

    __tablename__ = "contract_visit_day"
    __table_args__ = (
        sa.UniqueConstraint("service_call_id", "visit_date", name="UQ_svc_contract_visit_day_call_date"),
        {"schema": "svc"},
    )

    id: Mapped[int] = mapped_column(sa.BigInteger(), primary_key=True)
    service_contract_id: Mapped[int] = mapped_column(sa.BigInteger(), sa.ForeignKey("svc.service_contract.id"))
    service_call_id: Mapped[int] = mapped_column(sa.BigInteger(), sa.ForeignKey("svc.service_call.id"))
    visit_date: Mapped[dt.date] = mapped_column(sa.Date(), doc="Day in India time")
    created_at: Mapped[dt.datetime] = mapped_column(mssql.DATETIME2(0), server_default=sa.FetchedValue())
    created_by_user_id: Mapped[int | None] = mapped_column(sa.BigInteger())
