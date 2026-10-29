"""Checks the SQL Server statement the call register runs, without needing a database."""

from typing import Any

from trishul_api.auth import RequestScope
from trishul_api.modules.service.repository import ServiceCallRepository
from trishul_api.modules.service.schemas import AssignedServiceCallQuery, ServiceCallQuery

from .helpers import mssql_sql


def sql(scope: RequestScope, **query: Any) -> str:
    statement = ServiceCallRepository.list_statement(scope, ServiceCallQuery(**query))
    return mssql_sql(statement.offset(20).limit(20))


def assigned_sql(engineer_id: int, scope: RequestScope, **query: Any) -> str:
    statement = ServiceCallRepository.assigned_statement(engineer_id, scope, AssignedServiceCallQuery(**query))
    return mssql_sql(statement.offset(20).limit(20))


def test_filters_by_selected_branch_and_brand() -> None:
    text = sql(RequestScope(branch_id=3, principal_id=10))
    assert "svc.service_call.branch_id = 3" in text
    assert "svc.service_call.principal_id = 10" in text


def test_no_branch_filter_when_no_branch_selected() -> None:
    assert "branch_id =" not in sql(RequestScope(branch_id=None, principal_id=None))


def test_pages_with_offset_fetch_and_a_stable_order() -> None:
    text = sql(RequestScope(1, None))
    assert "ORDER BY svc.service_call.received_at DESC, svc.service_call.id DESC" in text
    assert "OFFSET 20 ROWS FETCH FIRST 20 ROWS ONLY" in text


def test_priority_sorts_by_severity_not_alphabetically() -> None:
    text = sql(RequestScope(1, None), sort="priority")
    assert "ORDER BY CASE svc.service_call.priority WHEN 'Critical' THEN 1" in text


def test_unknown_sort_falls_back_to_the_default_order() -> None:
    text = sql(RequestScope(1, None), sort="row_version; DROP TABLE x")
    assert "ORDER BY svc.service_call.received_at DESC" in text
    assert "DROP" not in text


def test_search_escapes_like_wildcards() -> None:
    text = sql(RequestScope(1, None), search="50%_off")
    # NVARCHAR columns: Unicode literals, so non-Latin names (Hindi, Marathi) match.
    assert "LIKE '%' + N'50/%/_off' + '%' ESCAPE '/'" in text


def test_status_and_priority_filters() -> None:
    text = sql(RequestScope(1, None), status=["Logged", "Reopened"], priority=["High"])
    assert "svc.service_call.current_status IN (N'Logged', N'Reopened')" in text
    assert "svc.service_call.priority IN (N'High')" in text


def test_assigned_list_is_scoped_to_the_signed_in_engineer() -> None:
    text = assigned_sql(55, RequestScope(branch_id=3, principal_id=10))
    assert "svc.service_call.assigned_engineer_id = 55" in text
    assert "svc.service_call.branch_id = 3" in text
    assert "svc.service_call.principal_id = 10" in text


def test_assigned_list_hides_closed_and_cancelled_by_default() -> None:
    text = assigned_sql(55, RequestScope(1, None))
    assert "svc.service_call.current_status NOT IN (N'Closed', N'Cancelled')" in text


def test_assigned_list_honours_an_explicit_status_filter() -> None:
    text = assigned_sql(55, RequestScope(1, None), status=["Trip started"])
    assert "svc.service_call.current_status IN (N'Trip started')" in text
    assert "NOT IN" not in text


def test_assigned_list_defaults_to_priority_then_id() -> None:
    text = assigned_sql(55, RequestScope(1, None))
    assert "ORDER BY CASE svc.service_call.priority WHEN 'Critical' THEN 1" in text
    assert "svc.service_call.id DESC" in text


def test_assigned_list_rejects_arbitrary_sort() -> None:
    text = assigned_sql(55, RequestScope(1, None), sort="caller_phone; DROP TABLE x")
    assert "DROP" not in text
