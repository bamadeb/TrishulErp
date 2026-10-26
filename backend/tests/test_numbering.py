from typing import Any

import pytest

from trishul_api.common.errors import ApiError
from trishul_api.common.numbering import (
    GST_DOCUMENT_NO_MAX_LENGTH,
    format_document_no,
    next_document_no,
    series_statement,
)
from trishul_api.db.models import NumberSeries

from .helpers import mssql_sql


class FakeResult:
    def __init__(self, row: NumberSeries | None) -> None:
        self._row = row

    def first(self) -> NumberSeries | None:
        return self._row


class FakeSession:
    """Returns one series for any query; enough to test the numbering rules."""

    def __init__(self, series: NumberSeries | None) -> None:
        self.series = series

    def scalars(self, _statement: Any) -> FakeResult:
        return FakeResult(self.series)


def make_series(**values: Any) -> NumberSeries:
    defaults: dict[str, Any] = {"prefix": "SC/25-26/", "next_number": 4210, "padding": 5, "suffix": None}
    return NumberSeries(**(defaults | values))


def take(session: FakeSession, **kwargs: Any) -> str:
    return next_document_no(session, company_id=1, document_type="SERVICE_CALL", **kwargs)  # type: ignore[arg-type]


def test_numbers_are_formatted_and_advance() -> None:
    session = FakeSession(make_series())
    assert take(session) == "SC/25-26/04210"
    assert take(session) == "SC/25-26/04211"
    assert session.series is not None
    assert session.series.next_number == 4212


def test_prefix_and_suffix_are_optional() -> None:
    assert format_document_no(make_series(prefix=None, suffix="/PUN", padding=3), 7) == "007/PUN"


def test_missing_series_is_a_clear_error() -> None:
    with pytest.raises(ApiError, match="No number series is set up for SERVICE_CALL"):
        take(FakeSession(None))


def test_gst_length_limit_is_enforced_without_using_the_number() -> None:
    session = FakeSession(make_series(prefix="INV/PUNE/2025-26/"))
    with pytest.raises(ApiError, match="longer than 16"):
        take(session, max_length=GST_DOCUMENT_NO_MAX_LENGTH)
    assert session.series is not None
    assert session.series.next_number == 4210


def test_series_row_is_locked_and_most_specific_first() -> None:
    statement = series_statement(
        company_id=1, document_type="SALES_INVOICE", branch_id=3, principal_id=None, fiscal_year_id=9
    )
    compiled = mssql_sql(statement)
    assert "SELECT TOP 1" in compiled
    assert "FROM core.number_series WITH (UPDLOCK, ROWLOCK)" in compiled
    assert "core.number_series.branch_id = 3 OR core.number_series.branch_id IS NULL" in compiled
    assert "ORDER BY CASE WHEN (core.number_series.branch_id IS NULL) THEN 1 ELSE 0 END" in compiled
