"""HTTPX-based eSSL biometric client abstraction.

No vendor paths, auth schemes or response fields are assumed. Concrete request shapes
must wait for official eSSL API documentation. Until then every fetch raises
:class:`BiometricApiContractMissing`.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Protocol

import httpx2 as httpx

logger = logging.getLogger(__name__)


class BiometricClientError(RuntimeError):
    """Base error for the biometric external client. Messages must never include secret values."""


class BiometricNotConfigured(BiometricClientError):
    """Base URL or Secrets Manager credentials are missing."""


class BiometricApiContractMissing(BiometricClientError):
    """eSSL request/response contract is not implemented yet."""


@dataclass(frozen=True, slots=True)
class BiometricConnectionConfig:
    """Connection parameters resolved from device row + Secrets Manager (ids only in logs)."""

    base_url: str | None
    credential_secret_name: str | None
    timeout_seconds: float = 30.0


class BiometricPunchSource(Protocol):
    """Future vendor punch shape. Intentionally empty until the eSSL contract is known."""


class EsslBiometricClient:
    """eSSL attendance API client shell using HTTPX.

    Methods that would call the vendor raise :class:`BiometricApiContractMissing` so
    synchronization cannot invent endpoints. HTTP plumbing is ready for a later fill-in.
    """

    def __init__(
        self,
        connection: BiometricConnectionConfig,
        *,
        http_client: httpx.Client | None = None,
        credentials: dict[str, Any] | None = None,
    ) -> None:
        self._connection = connection
        self._credentials = credentials or {}
        self._owns_client = http_client is None
        self._http = http_client or httpx.Client(
            base_url=(connection.base_url or "").rstrip("/"),
            timeout=connection.timeout_seconds,
        )

    def close(self) -> None:
        if self._owns_client:
            self._http.close()

    def __enter__(self) -> EsslBiometricClient:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    def ensure_configured(self) -> None:
        if not self._connection.base_url:
            raise BiometricNotConfigured("Biometric API base URL is not configured.")
        if not self._connection.credential_secret_name:
            raise BiometricNotConfigured(
                "Biometric credential secret name is not configured (AWS Secrets Manager)."
            )
        if not self._credentials:
            raise BiometricNotConfigured("Biometric credentials were not loaded from Secrets Manager.")

    def test_connection(self) -> None:
        """Reserved: verify reachability once the eSSL health/auth contract is documented."""
        self.ensure_configured()
        logger.info(
            "biometric.client.test_connection blocked; eSSL API contract not implemented secret_id=%s",
            self._connection.credential_secret_name,
        )
        raise BiometricApiContractMissing(
            "eSSL biometric API contract is not implemented yet. Provide official documentation before enabling sync."
        )

    def fetch_punches(
        self,
        *,
        device_external_id: str | None,
        since: datetime | None,
        until: datetime | None,
    ) -> list[dict[str, Any]]:
        """Reserved: pull punches from eSSL. Does not invent paths or field names."""
        self.ensure_configured()
        logger.info(
            "biometric.client.fetch_punches blocked; eSSL API contract not implemented "
            "device_external_id=%s since=%s until=%s",
            device_external_id,
            since.isoformat() if since else None,
            until.isoformat() if until else None,
        )
        raise BiometricApiContractMissing(
            "eSSL biometric API contract is not implemented yet. Provide official documentation before enabling sync."
        )
