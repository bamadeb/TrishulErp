"""Helpers shared by test modules."""

from typing import Any

from sqlalchemy import Dialect
from sqlalchemy.dialects import mssql
from sqlalchemy.sql import ClauseElement


def sql_server_2019() -> Dialect:
    """The SQL Server dialect as a live RDS connection configures it. Without a connection the
    dialect assumes an old server and pages with ROW_NUMBER() instead of OFFSET / FETCH."""
    dialect: Any = mssql.dialect()  # type: ignore[no-untyped-call]
    dialect.server_version_info = (15, 0)
    dialect._setup_version_attributes()
    return dialect  # type: ignore[no-any-return]


def mssql_sql(statement: ClauseElement) -> str:
    """The statement as SQL Server text with values inlined, on one line."""
    compiled = statement.compile(dialect=sql_server_2019(), compile_kwargs={"literal_binds": True})
    return " ".join(str(compiled).split())
