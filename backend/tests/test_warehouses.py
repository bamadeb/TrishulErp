"""Warehouses and the branch -> warehouse mapping: route -> service -> SQL (SQLite)."""

from collections.abc import Iterator
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine
from sqlalchemy.orm import Session

from trishul_api.auth import get_current_user, get_db
from trishul_api.config import Settings
from trishul_api.db import set_audit_context
from trishul_api.main import create_app
from trishul_api.modules.core.repository import CoreRepository

from .conftest import make_user
from .sqlite_db import insert_row, sqlite_engine

TABLES = ["core.company", "core.state", "core.region", "core.branch", "core.app_user", "core.audit_log"]
HO, BBSR, JSG, ROURKELA, ANGUL, WORKSHOP = 1, 10, 11, 20, 21, 22
URL = "/api/v1/core"
STALE = {"If-Match": '"AAAAAAAAAAA="'}


@pytest.fixture
def db() -> Engine:
    engine = sqlite_engine(TABLES)
    insert_row(engine, "core.company", id=1, code="TRISHUL", legal_name="Trishul", trade_name="Trishul")
    insert_row(engine, "core.company", id=2, code="KASHI", legal_name="Kashi Sales", trade_name="Kashi")
    insert_row(engine, "core.state", id=1, name="Odisha")
    insert_row(engine, "core.app_user", id=1, username="admin@trishul.co")
    rows = (
        (HO, "HO", "Head office", "Head office"),
        (BBSR, "BBSR", "Bhubaneswar", "Warehouse"),
        (JSG, "JHARSUGUDA", "Jharsuguda", "Warehouse"),
        (ROURKELA, "ROURKELA", "Rourkela", "Branch"),
        (ANGUL, "ANGUL", "Angul", "Branch"),
        (WORKSHOP, "WORKSHOP", "Workshop", "Service point"),
    )
    for branch_id, code, name, kind in rows:
        insert_row(
            engine, "core.branch", id=branch_id, company_id=1, state_id=1, code=code, name=name, branch_type=kind
        )
    return engine


def make_client(settings: Settings, db: Engine, permissions: frozenset[str]) -> Iterator[TestClient]:
    app = create_app(settings, engine=db)
    api = app.state.api_v1
    actor = make_user(id=1, permissions=permissions, branch_ids=None, principal_ids=None)
    api.dependency_overrides[get_current_user] = lambda: actor

    def session() -> Iterator[Session]:
        with Session(db, expire_on_commit=False) as s:
            set_audit_context(s, user_id=1, source="Web", ip_address="127.0.0.1")
            yield s

    api.dependency_overrides[get_db] = session
    with TestClient(app, raise_server_exceptions=False) as test_client:
        yield test_client


@pytest.fixture
def client(settings: Settings, db: Engine) -> Iterator[TestClient]:
    yield from make_client(settings, db, frozenset({"core.warehouse.view", "core.warehouse.manage"}))


@pytest.fixture
def viewer(settings: Settings, db: Engine) -> Iterator[TestClient]:
    yield from make_client(settings, db, frozenset({"core.warehouse.view"}))


def match(item: dict[str, Any]) -> dict[str, str]:
    return {"If-Match": f'"{item["rowVersion"]}"'}


def overview(client: TestClient) -> dict[str, Any]:
    response = client.get(f"{URL}/warehouses")
    assert response.status_code == 200, response.text
    return response.json()


def branch(client: TestClient, branch_id: int) -> dict[str, Any]:
    return next(b for b in overview(client)["branches"] if b["id"] == branch_id)


def warehouse(client: TestClient, warehouse_id: int) -> dict[str, Any]:
    return next(w for w in overview(client)["warehouses"] if w["id"] == warehouse_id)


def assign(client: TestClient, branch_id: int, warehouse_id: int | None) -> Any:
    return client.put(
        f"{URL}/branches/{branch_id}/warehouse",
        json={"warehouseId": warehouse_id},
        headers=match(branch(client, branch_id)),
    )


def test_overview_lists_warehouses_and_branches_but_not_the_head_office(client: TestClient) -> None:
    body = overview(client)
    assert [w["code"] for w in body["warehouses"]] == ["BBSR", "JHARSUGUDA"]
    assert [b["code"] for b in body["branches"]] == ["ANGUL", "ROURKELA", "WORKSHOP"]
    assert all(b["warehouseId"] is None for b in body["branches"])


def test_assigning_branches_to_a_warehouse_and_moving_them(client: TestClient) -> None:
    for branch_id in (ROURKELA, ANGUL, WORKSHOP):
        assert assign(client, branch_id, BBSR).status_code == 200
    assert warehouse(client, BBSR)["branchCount"] == 3
    moved = assign(client, ROURKELA, JSG)
    assert moved.status_code == 200 and moved.json()["warehouseId"] == JSG
    assert (warehouse(client, BBSR)["branchCount"], warehouse(client, JSG)["branchCount"]) == (2, 1)
    assert assign(client, ROURKELA, None).json()["warehouseId"] is None


def test_a_branch_can_only_be_supplied_by_an_active_warehouse(client: TestClient) -> None:
    for bad in (ANGUL, HO, 999):
        assert assign(client, ROURKELA, bad).status_code == 400, bad
    off = client.patch(f"{URL}/warehouses/{JSG}", json={"isActive": False}, headers=match(warehouse(client, JSG)))
    assert off.status_code == 200
    assert assign(client, ROURKELA, JSG).status_code == 400


def test_the_head_office_and_warehouses_cannot_be_assigned(client: TestClient) -> None:
    for location in (HO, BBSR):
        response = client.put(f"{URL}/branches/{location}/warehouse", json={"warehouseId": JSG}, headers=STALE)
        assert response.status_code == 404, location


def test_a_stale_version_is_refused(client: TestClient) -> None:
    put = client.put(f"{URL}/branches/{ROURKELA}/warehouse", json={"warehouseId": BBSR}, headers=STALE)
    assert put.status_code == 409
    assert client.patch(f"{URL}/warehouses/{BBSR}", json={"name": "X"}, headers=STALE).status_code == 409


def test_add_and_edit_a_warehouse(client: TestClient) -> None:
    created = client.post(f"{URL}/warehouses", json={"code": "WH-NEW", "name": "Cuttack"})
    assert created.status_code == 201, created.text
    assert (created.json()["code"], created.json()["branchCount"]) == ("WH-NEW", 0)
    assert client.post(f"{URL}/warehouses", json={"code": "BBSR", "name": "Dup"}).status_code in (400, 409)
    renamed = client.patch(
        f"{URL}/warehouses/{created.json()['id']}", json={"name": "Cuttack Warehouse"}, headers=match(created.json())
    )
    assert renamed.status_code == 200 and renamed.json()["name"] == "Cuttack Warehouse"
    not_a_warehouse = client.patch(f"{URL}/warehouses/{ROURKELA}", json={"name": "X"}, headers=STALE)
    assert not_a_warehouse.status_code == 404


def test_add_a_branch_under_a_warehouse_or_without_one(client: TestClient) -> None:
    under = client.post(f"{URL}/branches", json={"code": "PURI", "name": "Puri", "warehouseId": BBSR})
    assert under.status_code == 201, under.text
    assert (under.json()["warehouseId"], under.json()["branchType"], under.json()["isActive"]) == (BBSR, "Branch", True)
    alone = client.post(f"{URL}/branches", json={"code": "KENDU", "name": "Kendujhar", "branchType": "Service point"})
    assert alone.status_code == 201 and alone.json()["warehouseId"] is None
    overview = client.get(f"{URL}/warehouses").json()
    assert {b["code"] for b in overview["branches"]} >= {"PURI", "KENDU"}
    assert next(w for w in overview["warehouses"] if w["id"] == BBSR)["branchCount"] == 1


def test_a_new_branch_needs_a_free_code_a_real_type_and_an_active_warehouse(client: TestClient) -> None:
    assert client.post(f"{URL}/branches", json={"code": "ANGUL", "name": "Dup"}).status_code in (400, 409)
    assert (
        client.post(f"{URL}/branches", json={"code": "X1", "name": "X", "branchType": "Warehouse"}).status_code == 422
    )
    not_warehouse = client.post(f"{URL}/branches", json={"code": "X2", "name": "X", "warehouseId": ANGUL})
    assert not_warehouse.status_code == 400
    assert "warehouseId" in not_warehouse.json()["errors"]


def test_warehouses_and_branches_are_mapped_to_a_company(client: TestClient) -> None:
    overview = client.get(f"{URL}/warehouses").json()
    assert [(c["id"], c["name"]) for c in overview["companies"]] == [(2, "Kashi Sales"), (1, "Trishul")]
    assert {w["companyName"] for w in overview["warehouses"]} == {"Trishul"}

    created = client.post(f"{URL}/warehouses", json={"code": "WH-K", "name": "Kashi store", "companyId": 2})
    assert created.status_code == 201, created.text
    assert (created.json()["companyId"], created.json()["companyName"]) == (2, "Kashi Sales")

    moved = client.patch(f"{URL}/warehouses/{BBSR}", json={"companyId": 2}, headers=match(warehouse(client, BBSR)))
    assert moved.status_code == 200 and moved.json()["companyName"] == "Kashi Sales"

    inherits = client.post(f"{URL}/branches", json={"code": "B1", "name": "One", "warehouseId": JSG})
    assert inherits.json()["companyId"] == 1  # the warehouse's company when none is chosen
    own = client.post(f"{URL}/branches", json={"code": "B2", "name": "Two", "companyId": 2})
    assert (own.json()["companyId"], own.json()["companyName"]) == (2, "Kashi Sales")

    unknown = client.post(f"{URL}/warehouses", json={"code": "WH-X", "name": "X", "companyId": 99})
    assert unknown.status_code == 400 and "companyId" in unknown.json()["errors"]


def test_a_warehouse_that_still_supplies_branches_cannot_be_deactivated(client: TestClient) -> None:
    assign(client, ROURKELA, JSG)
    refused = client.patch(f"{URL}/warehouses/{JSG}", json={"isActive": False}, headers=match(warehouse(client, JSG)))
    assert refused.status_code == 400
    assign(client, ROURKELA, None)
    done = client.patch(f"{URL}/warehouses/{JSG}", json={"isActive": False}, headers=match(warehouse(client, JSG)))
    assert done.status_code == 200 and done.json()["isActive"] is False


def test_viewing_needs_view_and_changing_needs_manage(viewer: TestClient) -> None:
    assert viewer.get(f"{URL}/warehouses").status_code == 200
    assert viewer.post(f"{URL}/warehouses", json={"code": "X", "name": "X"}).status_code == 403
    assert viewer.post(f"{URL}/branches", json={"code": "X", "name": "X"}).status_code == 403
    put = viewer.put(f"{URL}/branches/{ROURKELA}/warehouse", json={"warehouseId": BBSR}, headers=STALE)
    assert put.status_code == 403


def test_me_branches_carry_their_warehouse(client: TestClient, db: Engine) -> None:
    assign(client, ROURKELA, JSG)
    with Session(db) as session:
        by_code = {b.code: b for b in CoreRepository(session).branches(None)}
    assert (by_code["ROURKELA"].warehouse_id, by_code["ROURKELA"].warehouse_name) == (JSG, "Jharsuguda")
    assert by_code["JHARSUGUDA"].warehouse_id == JSG  # a warehouse is its own warehouse
    assert by_code["HO"].warehouse_id is None
