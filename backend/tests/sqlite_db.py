"""An in-memory SQLite database with real tables from the generated models, for service tests.

    engine = sqlite_engine(["core.app_user", "core.role", ...])
    insert_row(engine, "core.role", code="ADMIN", name="Administrator")

SQL Server specifics are adapted for SQLite only here: column types, IDENTITY keys, and the server
defaults (created_at, is_active, row_version, ...) that the models leave to the database.
"""

from collections.abc import Iterable
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    BigInteger,
    Boolean,
    Date,
    DateTime,
    Engine,
    FetchedValue,
    Integer,
    Numeric,
    create_engine,
    event,
    insert,
)
from sqlalchemy.dialects.mssql import DATETIME2, ROWVERSION, TINYINT
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.pool import StaticPool
from sqlalchemy.schema import Column, CreateColumn
from sqlalchemy.sql.type_api import TypeEngine

from trishul_api.db.models import Base

SCHEMAS = ("core", "svc", "inv", "pur", "sal", "pre", "hr", "acc", "int", "rpt")


@compiles(DATETIME2, "sqlite")
def _datetime2(*_: Any, **__: Any) -> str:
    return "DATETIME"


@compiles(ROWVERSION, "sqlite")
def _rowversion(*_: Any, **__: Any) -> str:
    return "BLOB"


@compiles(TINYINT, "sqlite")
def _tinyint(*_: Any, **__: Any) -> str:
    return "INTEGER"


@compiles(BigInteger, "sqlite")
def _bigint(*_: Any, **__: Any) -> str:
    return "INTEGER"  # only INTEGER PRIMARY KEY auto-increments in SQLite


@compiles(CreateColumn, "sqlite")
def _column_with_default(element: CreateColumn, compiler: Any, **kw: Any) -> str:
    """Server defaults (FetchedValue in the models) become real DEFAULTs so inserts can omit them."""
    text: str = compiler.visit_create_column(element, **kw)
    column: Column[Any] = element.element
    if type(column.server_default) is FetchedValue and column.computed is None:
        default = _sqlite_default(column)
        if default is not None:
            text += f" DEFAULT {default}"
    return text


def _sqlite_default(column: Column[Any]) -> str | None:
    if column.name == "row_version":
        return "(randomblob(8))"
    kind: TypeEngine[Any] = column.type
    if isinstance(kind, DateTime):
        return "CURRENT_TIMESTAMP"
    if isinstance(kind, Boolean):
        return "1" if column.name == "is_active" else "0"
    if isinstance(kind, Numeric | Integer):
        return "0"
    return "''"


def sqlite_engine(tables: Iterable[str]) -> Engine:
    """In-memory database with the given tables ("schema.table"); foreign keys aren't enforced."""
    # One shared connection; FastAPI runs sync endpoints on worker threads, one request at a time here.
    engine = create_engine("sqlite://", poolclass=StaticPool, connect_args={"check_same_thread": False})

    @event.listens_for(engine, "connect")
    def _attach_schemas(dbapi_connection: Any, _record: Any) -> None:
        for schema in SCHEMAS:
            dbapi_connection.execute(f"ATTACH DATABASE ':memory:' AS {schema}")

    Base.metadata.create_all(engine, tables=[Base.metadata.tables[name] for name in tables])
    return engine


def insert_row(engine: Engine, table_name: str, **values: Any) -> int:
    """Inserts a row, filling required columns that weren't given with placeholder values."""
    table = Base.metadata.tables[table_name]
    for column in table.columns:
        if column.name in values or column.nullable or column.primary_key or column.server_default is not None:
            continue
        values[column.name] = _placeholder(column)
    with engine.begin() as connection:
        result = connection.execute(insert(table).values(**values))
        key = result.inserted_primary_key
        assert key is not None
        return int(key[0])


def _placeholder(column: Column[Any]) -> Any:
    kind: TypeEngine[Any] = column.type
    if isinstance(kind, DateTime):
        return datetime.now(UTC).replace(tzinfo=None)
    if isinstance(kind, Date):
        return date.today()
    if isinstance(kind, Boolean):
        return False
    if isinstance(kind, Numeric):
        return Decimal(0)
    python_type = kind.python_type
    if python_type is int:
        return 1
    return f"{column.name}-x"
