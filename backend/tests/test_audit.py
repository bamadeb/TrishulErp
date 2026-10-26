"""db.audit against SQLite. The listener only depends on the Audited marker, so the tests use small
models of their own rather than the generated ones."""

import json
from collections.abc import Iterator
from typing import Any

import pytest
from sqlalchemy import Engine, create_engine, event, select, text
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column
from sqlalchemy.pool import StaticPool

from trishul_api.db import set_audit_context
from trishul_api.db.models import Audited, AuditLog


class _TestBase(DeclarativeBase):
    pass


class Gadget(Audited, _TestBase):
    __tablename__ = "gadget"
    __table_args__ = {"schema": "core"}

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str]
    name: Mapped[str]
    updated_by_user_id: Mapped[int | None]
    is_active: Mapped[bool] = mapped_column(server_default=text("1"))


class Note(_TestBase):
    """Not audited."""

    __tablename__ = "note"
    __table_args__ = {"schema": "core"}

    id: Mapped[int] = mapped_column(primary_key=True)
    body: Mapped[str]


AUDIT_LOG_DDL = """CREATE TABLE core.audit_log (
    id INTEGER PRIMARY KEY, entity_type TEXT, entity_id INTEGER, action TEXT,
    old_values TEXT, new_values TEXT, changed_by_user_id INTEGER, changed_at DATETIME,
    source TEXT, ip_address TEXT)"""


@pytest.fixture
def engine() -> Iterator[Engine]:
    engine = create_engine("sqlite://", poolclass=StaticPool)

    @event.listens_for(engine, "connect")
    def _attach(dbapi_connection: Any, _record: Any) -> None:
        dbapi_connection.execute("ATTACH DATABASE ':memory:' AS core")

    _TestBase.metadata.create_all(engine)
    with engine.begin() as connection:
        connection.execute(text(AUDIT_LOG_DDL))
    yield engine
    engine.dispose()


def audit_rows(engine: Engine) -> list[AuditLog]:
    with Session(engine) as session:
        return list(session.scalars(select(AuditLog).order_by(AuditLog.id)))


def audited_session(engine: Engine) -> Session:
    session = Session(engine)
    set_audit_context(session, user_id=7, source="Web", ip_address="10.0.0.5")
    return session


def test_insert_update_delete_are_recorded(engine: Engine) -> None:
    with audited_session(engine) as session:
        gadget = Gadget(code="C001", name="Sahyadri Pharma")
        session.add(gadget)
        session.commit()

        gadget.name = "Sahyadri Pharma Ltd"  # expired by the commit: the old value is loaded first
        session.commit()

        session.delete(gadget)
        session.commit()

    insert, update, delete = audit_rows(engine)

    assert (insert.entity_type, insert.action, insert.changed_by_user_id) == ("core.gadget", "Insert", 7)
    assert (insert.source, insert.ip_address) == ("Web", "10.0.0.5")
    assert insert.entity_id == update.entity_id == delete.entity_id
    new_values = json.loads(insert.new_values or "")
    # Server defaults appear only when the database returned them with the insert.
    assert new_values.items() >= {"code": "C001", "name": "Sahyadri Pharma"}.items()
    assert "id" not in new_values
    assert insert.old_values is None

    assert update.action == "Update"
    assert json.loads(update.old_values or "") == {"name": "Sahyadri Pharma"}
    assert json.loads(update.new_values or "") == {"name": "Sahyadri Pharma Ltd"}

    assert delete.action == "Delete"
    assert json.loads(delete.old_values or "")["name"] == "Sahyadri Pharma Ltd"
    assert delete.new_values is None


def test_housekeeping_only_updates_are_not_recorded(engine: Engine) -> None:
    with audited_session(engine) as session:
        gadget = Gadget(code="C002", name="Deccan Fabricators")
        session.add(gadget)
        session.commit()
        gadget.updated_by_user_id = 7
        session.commit()

    assert [row.action for row in audit_rows(engine)] == ["Insert"]


def test_models_without_the_marker_are_not_recorded(engine: Engine) -> None:
    with audited_session(engine) as session:
        session.add(Note(body="not audited"))
        session.commit()

    assert audit_rows(engine) == []


def test_rollback_discards_audit_rows(engine: Engine) -> None:
    with audited_session(engine) as session:
        session.add(Gadget(code="C003", name="Konkan Stone Crushers"))
        session.flush()
        session.rollback()

    assert audit_rows(engine) == []


def test_sessions_without_context_are_not_audited(engine: Engine) -> None:
    with Session(engine) as session:
        session.add(Gadget(code="C004", name="Vidarbha Textiles"))
        session.commit()

    assert audit_rows(engine) == []


def test_masked_columns(engine: Engine, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(Gadget, "__audit_masked__", frozenset({"name"}))
    with audited_session(engine) as session:
        session.add(Gadget(code="C005", name="Secret"))
        session.commit()

    assert json.loads(audit_rows(engine)[0].new_values or "")["name"] == "***"
