"""Secret management: caching, JSON parsing, the AWS fetcher, DB-credential parsing and engine wiring.

No AWS is contacted: the AWS fetcher is driven by a fake boto3 client, the rest by an in-memory fetcher.
"""

import json
from typing import Any, cast

import pytest
from botocore.exceptions import ClientError

from trishul_api.config import Settings
from trishul_api.db.credentials import DbCredentials, db_credentials
from trishul_api.db.engine import (
    _is_auth_failure,
    _login_suffix,
    _strip_trusted_connection,
    create_db_engine,
)
from trishul_api.secrets import (
    AwsSecretFetcher,
    SecretError,
    SecretProvider,
    StaticSecretFetcher,
)

DB_SECRET = "trishul/dev/db-app"
DB_JSON = json.dumps({"username": "trishul_app", "password": "p@ss;w{}rd", "host": "db", "port": 1433})


class CountingFetcher:
    """Records how many times each secret was fetched, to prove caching."""

    def __init__(self, values: dict[str, str]) -> None:
        self.values = values
        self.calls: dict[str, int] = {}

    def fetch(self, secret_id: str) -> str:
        self.calls[secret_id] = self.calls.get(secret_id, 0) + 1
        return self.values[secret_id]


class FakeClock:
    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now


def settings(**changes: Any) -> Settings:
    base = {"environment": "dev", "auth_mode": "dev", "dev_username": "demo.admin", "_env_file": None}
    return Settings(**(base | changes))


# ------------------------------------------------------------------ caching


def test_a_secret_is_fetched_once_per_ttl() -> None:
    clock = FakeClock()
    fetcher = CountingFetcher({DB_SECRET: DB_JSON})
    provider = SecretProvider(fetcher, ttl_seconds=300, clock=clock)

    assert provider.get_string(DB_SECRET) == DB_JSON
    provider.get_string(DB_SECRET)
    clock.now = 299
    provider.get_string(DB_SECRET)
    assert fetcher.calls[DB_SECRET] == 1  # all within the TTL window

    clock.now = 301
    provider.get_string(DB_SECRET)
    assert fetcher.calls[DB_SECRET] == 2  # TTL lapsed, re-read


def test_invalidate_forces_a_refresh() -> None:
    fetcher = CountingFetcher({DB_SECRET: DB_JSON})
    provider = SecretProvider(fetcher, ttl_seconds=300)

    provider.get_string(DB_SECRET)
    provider.invalidate(DB_SECRET)
    provider.get_string(DB_SECRET)
    assert fetcher.calls[DB_SECRET] == 2

    provider.invalidate()  # clears everything
    provider.get_string(DB_SECRET)
    assert fetcher.calls[DB_SECRET] == 3


def test_get_json_parses_objects_and_rejects_the_rest() -> None:
    provider = SecretProvider(
        StaticSecretFetcher({"ok": '{"a": 1}', "list": "[1, 2]", "bad": "not json"}), ttl_seconds=300
    )
    assert provider.get_json("ok") == {"a": 1}
    with pytest.raises(SecretError, match="not a JSON object"):
        provider.get_json("list")
    with pytest.raises(SecretError, match="not valid JSON"):
        provider.get_json("bad")


def test_missing_static_secret_is_an_error() -> None:
    with pytest.raises(SecretError, match="not configured"):
        StaticSecretFetcher({}).fetch("absent")


# ------------------------------------------------------------------ AWS fetcher (fake boto3 client)


class FakeSecretsClient:
    def __init__(self, response: dict[str, Any] | None = None, error: Exception | None = None) -> None:
        self._response = response
        self._error = error
        self.requested: list[str] = []

    def get_secret_value(self, SecretId: str) -> dict[str, Any]:
        self.requested.append(SecretId)
        if self._error is not None:
            raise self._error
        assert self._response is not None
        return self._response


def test_aws_fetcher_returns_the_secret_string() -> None:
    client = FakeSecretsClient(response={"SecretString": DB_JSON})
    fetcher = AwsSecretFetcher(settings(), client=cast(Any, client))
    assert fetcher.fetch(DB_SECRET) == DB_JSON
    assert client.requested == [DB_SECRET]


def test_aws_fetcher_maps_access_denied_without_leaking_the_value() -> None:
    denied = ClientError(
        {
            "Error": {
                "Code": "AccessDeniedException",
                "Message": "not authorized to perform secretsmanager:GetSecretValue",
            }
        },
        "GetSecretValue",
    )
    fetcher = AwsSecretFetcher(settings(), client=cast(Any, FakeSecretsClient(error=denied)))
    with pytest.raises(SecretError) as caught:
        fetcher.fetch(DB_SECRET)
    message = str(caught.value)
    assert DB_SECRET in message
    assert "p@ss" not in message  # the secret value never appears in the error


def test_aws_fetcher_rejects_a_binary_only_secret() -> None:
    fetcher = AwsSecretFetcher(settings(), client=cast(Any, FakeSecretsClient(response={"SecretBinary": b"x"})))
    with pytest.raises(SecretError, match="no string value"):
        fetcher.fetch(DB_SECRET)


# ------------------------------------------------------------------ DB credentials


def test_db_credentials_are_read_from_the_secret() -> None:
    provider = SecretProvider(StaticSecretFetcher({DB_SECRET: DB_JSON}), ttl_seconds=300)
    creds = db_credentials(provider, DB_SECRET)
    assert (creds.username, creds.password) == ("trishul_app", "p@ss;w{}rd")


def test_db_credentials_report_missing_fields() -> None:
    provider = SecretProvider(StaticSecretFetcher({DB_SECRET: '{"username": "x"}'}), ttl_seconds=300)
    with pytest.raises(SecretError, match="password"):
        db_credentials(provider, DB_SECRET)


def test_db_credentials_repr_hides_the_password() -> None:
    assert "secret" not in repr(DbCredentials(username="u", password="secret"))
    assert "***" in repr(DbCredentials(username="u", password="secret"))


# ------------------------------------------------------------------ connection-string assembly


def test_login_suffix_escapes_braces_and_separators() -> None:
    # A password with ; { } must stay inside one brace-wrapped ODBC value, with } doubled.
    suffix = _login_suffix(DbCredentials(username="trishul_app", password="p@ss;w}rd"))
    assert suffix == ";UID={trishul_app};PWD={p@ss;w}}rd}"


def test_trusted_connection_is_removed_so_sql_auth_is_used() -> None:
    # The pyodbc dialect adds Trusted_Connection=Yes when the URL has no login; it must not remain,
    # or the driver uses Windows integrated auth and ignores UID/PWD.
    base = "DRIVER={ODBC Driver 18 for SQL Server};SERVER=db;DATABASE=TrishulDev;Trusted_Connection=Yes"
    stripped = _strip_trusted_connection(base)
    assert "trusted_connection" not in stripped.lower()
    assert "SERVER=db" in stripped


def test_auth_failure_is_detected_from_the_driver_error() -> None:
    assert _is_auth_failure(Exception("[28000] Login failed for user 'trishul_app'. (18456)"))
    assert not _is_auth_failure(Exception("timeout expired"))
    assert not _is_auth_failure(None)


# ------------------------------------------------------------------ engine wiring


def _has_connect_listener(engine: Any) -> bool:
    # do_connect is a dialect-level event, so a listener attached to the engine lives on the dialect.
    try:
        return len(list(engine.dialect.dispatch.do_connect)) > 0
    except AttributeError:  # no listener was ever registered
        return False


def test_engine_with_a_secret_injects_the_login_at_connect_time() -> None:
    provider = SecretProvider(StaticSecretFetcher({DB_SECRET: DB_JSON}), ttl_seconds=300)
    engine = create_db_engine(settings(db_secret_id=DB_SECRET), provider)
    # The password is supplied per-connection, never baked into the engine URL.
    assert engine.url.username is None
    assert engine.url.password is None
    assert _has_connect_listener(engine)

    # Firing do_connect appends the current secret's login to the ODBC connection string.
    cargs = ["DRIVER={ODBC Driver 18 for SQL Server};SERVER=db"]
    engine.dialect.dispatch.do_connect(engine.dialect, None, cargs, {})
    assert cargs[0].endswith(";UID={trishul_app};PWD={p@ss;w{}}rd}")


def test_engine_reads_host_port_and_database_from_the_secret() -> None:
    full = json.dumps({"username": "u", "password": "p", "host": "db.internal", "port": 1444, "dbname": "TrishulProd"})
    provider = SecretProvider(StaticSecretFetcher({DB_SECRET: full}), ttl_seconds=300)
    engine = create_db_engine(settings(db_secret_id=DB_SECRET, db_host="ignored", db_name="ignored"), provider)
    assert engine.url.host == "db.internal"
    assert engine.url.port == 1444
    assert engine.url.database == "TrishulProd"


def test_engine_falls_back_to_env_for_fields_the_secret_omits() -> None:
    # The secret carries only a login; host/port/database come from configuration.
    provider = SecretProvider(StaticSecretFetcher({DB_SECRET: '{"username": "u", "password": "p"}'}), ttl_seconds=300)
    engine = create_db_engine(settings(db_secret_id=DB_SECRET, db_host="rds.example", db_name="TrishulDev"), provider)
    assert engine.url.host == "rds.example"
    assert engine.url.database == "TrishulDev"


def test_engine_without_a_secret_uses_the_env_login() -> None:
    engine = create_db_engine(settings(db_user="sa", db_password="envpw", db_secret_id=DB_SECRET), secrets=None)
    # No provider given, so it falls back to the env login and bakes it into the URL as before.
    assert engine.url.username == "sa"
    assert engine.url.password == "envpw"
    assert not _has_connect_listener(engine)
