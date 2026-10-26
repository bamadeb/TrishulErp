"""Document numbers (call no, invoice no, ...) from core.number_series."""

from sqlalchemy import Select, case, select
from sqlalchemy.orm import Session

from trishul_api.common.errors import ApiError
from trishul_api.db.models import NumberSeries

# GST requires invoice and credit-note numbers of at most 16 characters (database/README, Q10).
GST_DOCUMENT_NO_MAX_LENGTH = 16


def series_statement(
    *, company_id: int, document_type: str, branch_id: int | None, principal_id: int | None, fiscal_year_id: int | None
) -> Select[NumberSeries]:
    """The most specific active series: a NULL branch, brand or fiscal year means "any"."""
    return (
        select(NumberSeries)
        .where(
            NumberSeries.company_id == company_id,
            NumberSeries.document_type == document_type,
            NumberSeries.is_active,
            (NumberSeries.branch_id == branch_id) | NumberSeries.branch_id.is_(None),
            (NumberSeries.principal_id == principal_id) | NumberSeries.principal_id.is_(None),
            (NumberSeries.fiscal_year_id == fiscal_year_id) | NumberSeries.fiscal_year_id.is_(None),
        )
        .order_by(
            case((NumberSeries.branch_id.is_(None), 1), else_=0),
            case((NumberSeries.principal_id.is_(None), 1), else_=0),
            case((NumberSeries.fiscal_year_id.is_(None), 1), else_=0),
        )
        .limit(1)
        # The row stays locked until the caller commits, so two transactions can never take the same
        # number; a rollback gives the number back. Not .with_for_update(): the SQL Server dialect
        # silently drops it, so the hint is written out.
        .with_hint(NumberSeries, "WITH (UPDLOCK, ROWLOCK)", "mssql")
    )


def format_document_no(series: NumberSeries, number: int) -> str:
    return f"{series.prefix or ''}{number:0{series.padding}d}{series.suffix or ''}"


def next_document_no(
    db: Session,
    *,
    company_id: int,
    document_type: str,
    branch_id: int | None = None,
    principal_id: int | None = None,
    fiscal_year_id: int | None = None,
    max_length: int | None = None,
) -> str:
    """Takes the next number in the caller's transaction. Call it as late as possible before commit:
    the series row stays locked until then."""
    series = db.scalars(
        series_statement(
            company_id=company_id,
            document_type=document_type,
            branch_id=branch_id,
            principal_id=principal_id,
            fiscal_year_id=fiscal_year_id,
        )
    ).first()
    if series is None:
        raise ApiError(f"No number series is set up for {document_type}. Ask an administrator to add one.")
    number = series.next_number
    document_no = format_document_no(series, number)
    if max_length is not None and len(document_no) > max_length:
        raise ApiError(f"{document_type} number {document_no} is longer than {max_length} characters.")
    series.next_number = number + 1
    return document_no
