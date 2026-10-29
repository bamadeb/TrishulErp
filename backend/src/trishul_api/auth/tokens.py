from dataclasses import dataclass
from typing import Protocol

import jwt

from trishul_api.common.errors import Unauthorized
from trishul_api.config import Settings


@dataclass(frozen=True)
class Identity:
    """Who the bearer token belongs to. Exactly one field is set."""

    cognito_sub: str | None = None
    username: str | None = None

    def __post_init__(self) -> None:
        if (self.cognito_sub is None) == (self.username is None):
            raise ValueError("Identity needs exactly one of cognito_sub or username")


class TokenVerifier(Protocol):
    def verify(self, token: str) -> Identity: ...

    def warm(self) -> None:
        """Pre-fetch anything slow (e.g. JWKS) so the first real verify is fast. Optional, best-effort."""
        ...


class CognitoTokenVerifier:
    """Validates Cognito access tokens: RS256 signature (JWKS), issuer, expiry, token_use and client_id."""

    def __init__(self, settings: Settings, jwks_client: jwt.PyJWKClient | None = None) -> None:
        self._issuer = settings.cognito_issuer
        self._client_id = settings.cognito_app_client_id
        self._jwks = jwks_client or jwt.PyJWKClient(f"{self._issuer}/.well-known/jwks.json", lifespan=3600)

    def verify(self, token: str) -> Identity:
        try:
            signing_key = self._jwks.get_signing_key_from_jwt(token)
            claims = jwt.decode(
                token,
                signing_key.key,
                algorithms=["RS256"],
                issuer=self._issuer,
                leeway=30,
                # Cognito access tokens carry client_id instead of aud.
                options={"require": ["exp", "iat", "sub", "token_use"], "verify_aud": False},
            )
        except jwt.PyJWTError as exc:
            raise Unauthorized("Your session has expired or is not valid. Sign in again.") from exc
        if claims["token_use"] != "access" or claims.get("client_id") != self._client_id:  # noqa: S105
            raise Unauthorized("This token was not issued for Trishul ERP.")
        return Identity(cognito_sub=str(claims["sub"]))

    def warm(self) -> None:
        # Fetch and cache the signing keys now, so the first sign-in doesn't wait on Cognito.
        self._jwks.get_signing_keys()


class DevTokenVerifier:
    """Local development only. "dev:<username>" (sent by the Angular dev sign-in) signs in as that
    core.app_user; any other token signs in as the configured default user."""

    PREFIX = "dev:"

    def __init__(self, default_username: str) -> None:
        self._default_username = default_username

    def verify(self, token: str) -> Identity:
        username = token.removeprefix(self.PREFIX).strip() if token.startswith(self.PREFIX) else ""
        return Identity(username=username or self._default_username)

    def warm(self) -> None:
        # Nothing to pre-fetch for local development sign-in.
        return


def create_token_verifier(settings: Settings) -> TokenVerifier:
    if settings.auth_mode == "dev":
        return DevTokenVerifier(settings.dev_username)
    return CognitoTokenVerifier(settings)
