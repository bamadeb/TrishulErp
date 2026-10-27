"""Reusable access to AWS Secrets Manager for the whole backend.

A :class:`SecretProvider` fetches a secret by id, caches it for a short time, and parses JSON secrets.
It is created once in the application's composition root (``create_app``) and shared by every component
that needs a secret (currently the database engine; integration credentials later).

Design notes:
  * Credentials come from the environment's AWS identity -- the ECS task role in AWS, or ``aws_profile``
    locally -- through the default boto3 provider chain. No AWS keys are ever read from code or settings.
  * Secret *values* are never logged, put in exceptions, or placed in ``repr``. Only secret *ids* and
    outcomes are logged, so passwords and tokens can't leak into logs, traces or monitoring.
  * Caching keeps Secrets Manager off the hot path: a value is fetched at most once per TTL, and callers
    can :meth:`invalidate` a secret (e.g. after an authentication failure) to force an immediate refresh,
    which is what lets a rotated database password be picked up without a restart.
"""

import json
import logging
import threading
import time
from collections.abc import Callable, Mapping
from typing import TYPE_CHECKING, Any, Protocol

from trishul_api.config import Settings

if TYPE_CHECKING:
    from mypy_boto3_secretsmanager import SecretsManagerClient

logger = logging.getLogger(__name__)


class SecretError(RuntimeError):
    """A secret could not be fetched or is malformed. The message names the secret id, never its value."""


class SecretFetcher(Protocol):
    """Fetches the raw string of a secret by id. Raises :class:`SecretError` on failure."""

    def fetch(self, secret_id: str) -> str: ...


class AwsSecretFetcher:
    """Reads ``SecretString`` from AWS Secrets Manager with timeouts and retries.

    The boto3 client is created lazily so importing this module needs no AWS access (tests and the
    env-only local setup never touch AWS)."""

    def __init__(self, settings: Settings, client: "SecretsManagerClient | None" = None) -> None:
        self._settings = settings
        self._client = client

    def _get_client(self) -> "SecretsManagerClient":
        if self._client is None:
            import boto3
            from botocore.config import Config

            # Short timeouts and bounded retries: a slow or flapping Secrets Manager must not hang the API.
            config = Config(
                connect_timeout=3,
                read_timeout=5,
                retries={"max_attempts": 3, "mode": "standard"},
            )
            session = boto3.Session(profile_name=self._settings.aws_profile, region_name=self._settings.aws_region)
            self._client = session.client("secretsmanager", config=config)
        return self._client

    def fetch(self, secret_id: str) -> str:
        from botocore.exceptions import BotoCoreError, ClientError

        try:
            response = self._get_client().get_secret_value(SecretId=secret_id)
        except (ClientError, BotoCoreError) as error:
            # str(error) describes the API call and error code (e.g. AccessDeniedException), not the value.
            logger.error("Could not read secret %s from Secrets Manager: %s", secret_id, type(error).__name__)
            raise SecretError(f"Could not read secret '{secret_id}' from AWS Secrets Manager.") from error
        value = response.get("SecretString")
        if value is None:
            raise SecretError(f"Secret '{secret_id}' has no string value (binary secrets are not supported).")
        return value


class StaticSecretFetcher:
    """In-memory secrets for tests and local use. Values stay in process and never reach AWS."""

    def __init__(self, secrets: Mapping[str, str]) -> None:
        self._secrets = dict(secrets)

    def fetch(self, secret_id: str) -> str:
        try:
            return self._secrets[secret_id]
        except KeyError:
            raise SecretError(f"Secret '{secret_id}' is not configured.") from None


class SecretProvider:
    """Caches secret strings for a TTL and parses JSON secrets. Safe to share across threads.

    One fetch per secret per TTL window keeps Secrets Manager off every request. :meth:`invalidate`
    drops a cached value so the next read goes back to the source -- used after a credential rotation."""

    def __init__(
        self,
        fetcher: SecretFetcher,
        ttl_seconds: float,
        *,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._fetcher = fetcher
        self._ttl = ttl_seconds
        self._clock = clock
        self._lock = threading.Lock()
        self._cache: dict[str, tuple[float, str]] = {}

    def get_string(self, secret_id: str) -> str:
        with self._lock:
            entry = self._cache.get(secret_id)
            if entry is not None and (self._clock() - entry[0]) < self._ttl:
                return entry[1]
        # Fetch outside the lock so a slow network call doesn't block readers of other secrets.
        value = self._fetcher.fetch(secret_id)
        with self._lock:
            self._cache[secret_id] = (self._clock(), value)
        return value

    def get_json(self, secret_id: str) -> Mapping[str, Any]:
        raw = self.get_string(secret_id)
        try:
            data = json.loads(raw)
        except json.JSONDecodeError as error:
            raise SecretError(f"Secret '{secret_id}' is not valid JSON.") from error
        if not isinstance(data, dict):
            raise SecretError(f"Secret '{secret_id}' is not a JSON object.")
        return data

    def invalidate(self, secret_id: str | None = None) -> None:
        """Drop one cached secret, or all of them, so the next read fetches a fresh value."""
        with self._lock:
            if secret_id is None:
                self._cache.clear()
            else:
                self._cache.pop(secret_id, None)


def create_secret_provider(settings: Settings) -> SecretProvider:
    """A provider backed by AWS Secrets Manager, with the configured cache TTL."""
    return SecretProvider(AwsSecretFetcher(settings), settings.secrets_cache_seconds)
