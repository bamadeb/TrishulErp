import time
from dataclasses import dataclass
from typing import Any

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa

from trishul_api.auth.tokens import CognitoTokenVerifier, DevTokenVerifier
from trishul_api.common.errors import Unauthorized
from trishul_api.config import Settings

POOL = "ap-south-1_TestPool"
CLIENT_ID = "test-client"
ISSUER = f"https://cognito-idp.ap-south-1.amazonaws.com/{POOL}"

signing_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
other_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)


@dataclass
class FakeSigningKey:
    key: Any


class FakeJwks:
    """Stands in for PyJWKClient: always returns the test public key."""

    def get_signing_key_from_jwt(self, token: str) -> FakeSigningKey:
        return FakeSigningKey(signing_key.public_key())


@pytest.fixture
def verifier() -> CognitoTokenVerifier:
    settings = Settings(
        environment="test",
        cognito_user_pool_id=POOL,
        cognito_app_client_id=CLIENT_ID,
        _env_file=None,
    )
    return CognitoTokenVerifier(settings, jwks_client=FakeJwks())  # type: ignore[arg-type]


def token(key: Any = signing_key, **claims: Any) -> str:
    now = int(time.time())
    payload = {
        "sub": "3f1c-user",
        "iss": ISSUER,
        "client_id": CLIENT_ID,
        "token_use": "access",
        "iat": now,
        "exp": now + 3600,
    } | claims
    return jwt.encode(payload, key, algorithm="RS256")


def test_accepts_valid_access_token(verifier: CognitoTokenVerifier) -> None:
    assert verifier.verify(token()).cognito_sub == "3f1c-user"


@pytest.mark.parametrize(
    "bad_token",
    [
        pytest.param(token(exp=int(time.time()) - 120), id="expired"),
        pytest.param(token(iss="https://evil.example.com"), id="wrong issuer"),
        pytest.param(token(client_id="other-app"), id="other app client"),
        pytest.param(token(token_use="id"), id="id token instead of access token"),
        pytest.param(token(key=other_key), id="bad signature"),
        pytest.param("not-a-jwt", id="garbage"),
    ],
)
def test_rejects_invalid_tokens(verifier: CognitoTokenVerifier, bad_token: str) -> None:
    with pytest.raises(Unauthorized):
        verifier.verify(bad_token)


def test_accepts_tokens_from_extra_app_clients() -> None:
    settings = Settings(
        environment="test",
        cognito_user_pool_id=POOL,
        cognito_app_client_id=CLIENT_ID,
        cognito_extra_client_ids=["mobile-client"],
        _env_file=None,
    )
    verifier = CognitoTokenVerifier(settings, jwks_client=FakeJwks())  # type: ignore[arg-type]
    assert verifier.verify(token(client_id="mobile-client")).cognito_sub == "3f1c-user"
    with pytest.raises(Unauthorized):
        verifier.verify(token(client_id="other-app"))


def test_rejects_unsigned_token(verifier: CognitoTokenVerifier) -> None:
    unsigned = jwt.encode({"sub": "x", "iss": ISSUER, "token_use": "access"}, "", algorithm="none")
    with pytest.raises(Unauthorized):
        verifier.verify(unsigned)


def test_dev_tokens_choose_the_user() -> None:
    verifier = DevTokenVerifier("demo.admin")
    assert verifier.verify("dev:team.lead").username == "team.lead"
    assert verifier.verify("dev:  ").username == "demo.admin"
    assert verifier.verify("anything-else").username == "demo.admin"
