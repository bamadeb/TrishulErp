"""Sorting and paging for list endpoints, shared by every module's repository."""

from collections.abc import Mapping
from typing import Any

from pydantic import BaseModel
from sqlalchemy import ColumnElement, Select, UnaryExpression, func, select
from sqlalchemy.orm import QueryableAttribute, Session

from trishul_api.common.schemas import Page, PageQuery

SortColumns = Mapping[str, QueryableAttribute[Any] | ColumnElement[Any]]
"""Client sort keys (camelCase field names) -> the column or expression to order by."""


def order_by_sort[S: Select[Any]](
    statement: S, sort: str | None, columns: SortColumns, *, default: str, tiebreaker: UnaryExpression[Any]
) -> S:
    """Orders by the requested key ('-' prefix = descending). Unknown keys fall back to `default`,
    so clients can never order by arbitrary SQL. The tiebreaker keeps paging stable."""
    key = sort if sort and sort.removeprefix("-") in columns else default
    column = columns[key.removeprefix("-")]
    return statement.order_by(column.desc() if key.startswith("-") else column.asc(), tiebreaker)


def paginate[T: BaseModel](session: Session, statement: Select[Any], query: PageQuery, item: type[T]) -> Page[T]:
    """Runs an ordered statement for one page and counts all matching rows."""
    total = session.scalar(select(func.count()).select_from(statement.order_by(None).subquery())) or 0
    rows = session.execute(statement.offset((query.page - 1) * query.page_size).limit(query.page_size)).mappings()
    return Page(
        items=[item.model_validate(row) for row in rows],
        total=total,
        page=query.page,
        page_size=query.page_size,
    )
