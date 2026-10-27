import pytest
from pydantic import ValidationError

from trishul_api.common.concurrency import check_row_version, if_match_row_version
from trishul_api.common.errors import ApiError, Conflict, PreconditionRequired
from trishul_api.config import Settings


def test_dev_sign_in_is_refused_in_production() -> None:
    with pytest.raises(ValidationError, match="not allowed in uat or prod"):
        Settings(environment="prod", auth_mode="dev", dev_username="x", _env_file=None)


def test_cognito_settings_are_required() -> None:
    with pytest.raises(ValidationError, match="COGNITO_USER_POOL_ID"):
        Settings(environment="prod", auth_mode="cognito", _env_file=None)


def test_a_cognito_secret_id_satisfies_the_requirement() -> None:
    # A Secrets Manager secret id is an accepted alternative to the inline pool/client ids.
    s = Settings(environment="prod", auth_mode="cognito", cognito_secret_id="trishul/prod/cognito", _env_file=None)
    assert s.cognito_secret_id == "trishul/prod/cognito"


def test_if_match_accepts_quoted_and_weak_etags() -> None:
    assert if_match_row_version('"AAAAAAAAB9E="') == b"\x00\x00\x00\x00\x00\x00\x07\xd1"
    assert if_match_row_version('W/"AAAAAAAAB9E="') == b"\x00\x00\x00\x00\x00\x00\x07\xd1"


def test_if_match_is_required_and_validated() -> None:
    with pytest.raises(PreconditionRequired):
        if_match_row_version(None)
    with pytest.raises(ApiError):
        if_match_row_version("not base64!")


def test_stale_row_version_is_a_conflict() -> None:
    check_row_version(b"\x01", b"\x01")
    with pytest.raises(Conflict):
        check_row_version(b"\x02", b"\x01")
