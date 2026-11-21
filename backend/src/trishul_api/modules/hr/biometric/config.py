"""Biometric module settings. Sync stays off until credentials and the eSSL contract exist."""

from dataclasses import dataclass

from trishul_api.config import Settings, get_settings


@dataclass(frozen=True, slots=True)
class BiometricSettings:
    """Resolved biometric options. Credentials are never held here — only secret ids."""

    sync_enabled: bool
    default_secret_id: str | None


def load_biometric_settings(settings: Settings | None = None) -> BiometricSettings:
    """Read from TRISHUL_* settings. Default keeps synchronization disabled."""
    cfg = settings or get_settings()
    return BiometricSettings(
        sync_enabled=bool(getattr(cfg, "biometric_sync_enabled", False)),
        default_secret_id=getattr(cfg, "biometric_default_secret_id", None),
    )
