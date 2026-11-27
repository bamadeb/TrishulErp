"""Security controls shared by every module: rate limits, file download headers, upload limits, settings."""

import io
import zipfile

import pytest
from fastapi import UploadFile
from fastapi.testclient import TestClient
from pydantic import ValidationError

from trishul_api.common.downloads import file_response_headers
from trishul_api.common.errors import ApiError
from trishul_api.common.rate_limit import Limit, SlidingWindow
from trishul_api.common.uploads import MAX_UNPACKED_BYTES, check_workbook_archive, read_upload
from trishul_api.config import Settings

# --- rate limits ------------------------------------------------------------------------------------------


def test_the_window_refuses_past_the_limit_and_frees_up_after_it() -> None:
    now = [100.0]
    window = SlidingWindow(clock=lambda: now[0])
    limit = Limit(3, 60)
    assert [window.hit("k", limit) for _ in range(3)] == [None, None, None]
    assert window.hit("k", limit) == pytest.approx(60.0)
    assert window.hit("other", limit) is None  # keys are counted apart
    now[0] += 30
    assert window.hit("k", limit) == pytest.approx(30.0)
    now[0] += 31
    assert window.hit("k", limit) is None


def test_callers_without_a_token_are_limited_per_address(client: TestClient) -> None:
    statuses = [client.get("/api/v1/me").status_code for _ in range(61)]
    assert statuses[:60] == [401] * 60
    assert statuses[60] == 429
    refused = client.get("/api/v1/me")
    assert refused.status_code == 429
    assert int(refused.headers["Retry-After"]) >= 1
    assert refused.headers["content-type"].startswith("application/problem+json")
    # A refusal still carries the security headers.
    assert refused.headers["X-Content-Type-Options"] == "nosniff"


def test_health_checks_are_never_limited(client: TestClient) -> None:
    assert {client.get("/health").status_code for _ in range(80)} == {200}


def test_own_password_changes_are_limited_per_session(client: TestClient) -> None:
    headers = {"Authorization": "Bearer dev:tester"}
    body = {"currentPassword": "old-password-123", "newPassword": "new-password-123"}
    statuses = [client.post("/api/v1/me/password", json=body, headers=headers).status_code for _ in range(6)]
    assert 429 not in statuses[:5]
    assert statuses[5] == 429
    # Another session is counted apart.
    other = client.post("/api/v1/me/password", json=body, headers={"Authorization": "Bearer dev:someone"})
    assert other.status_code != 429


def test_the_limiter_can_be_switched_off() -> None:
    from sqlalchemy import create_engine

    from trishul_api.main import create_app

    settings = Settings(environment="test", auth_mode="dev", dev_username="t", rate_limit_enabled=False, _env_file=None)
    with TestClient(create_app(settings, engine=create_engine("sqlite://"))) as client:
        assert {client.get("/api/v1/me").status_code for _ in range(70)} == {401}


# --- security headers -------------------------------------------------------------------------------------


def test_api_responses_carry_the_security_headers(client: TestClient) -> None:
    response = client.get("/api/v1/me")
    assert response.headers["Content-Security-Policy"] == "default-src 'none'; frame-ancestors 'none'"
    assert response.headers["X-Frame-Options"] == "DENY"
    assert response.headers["Cache-Control"] == "no-store"
    assert response.headers["Cross-Origin-Resource-Policy"] == "same-origin"
    assert response.headers["X-Permitted-Cross-Domain-Policies"] == "none"


# --- file downloads ---------------------------------------------------------------------------------------


def test_a_non_latin_file_name_is_sent_as_rfc5987() -> None:
    media_type, headers = file_response_headers("रसीद 1.pdf", "application/pdf", inline=False)
    assert media_type == "application/pdf"
    value = headers["Content-Disposition"]
    assert value.startswith('attachment; filename="')
    assert "filename*=UTF-8''%E0%A4%B0" in value
    value.encode("latin-1")  # a header must be Latin-1, or the server answers 500


def test_quotes_and_line_breaks_cannot_break_out_of_the_header() -> None:
    _, headers = file_response_headers('a"; filename=evil.html\r\nX-Injected: 1.pdf', "application/pdf", inline=False)
    value = headers["Content-Disposition"]
    assert "\r" not in value and "\n" not in value
    assert value.count('"') == 2
    assert value.startswith('attachment; filename="a_')


@pytest.mark.parametrize("content_type", ["text/html", "image/svg+xml", "application/xml", None, "TEXT/HTML"])
def test_only_pdfs_and_pictures_are_shown_inline(content_type: str | None) -> None:
    _, headers = file_response_headers("x.bin", content_type, inline=True)
    assert headers["Content-Disposition"].startswith("attachment;")
    assert headers["X-Content-Type-Options"] == "nosniff"


def test_a_picture_may_be_shown_inline() -> None:
    _, headers = file_response_headers("photo.jpg", "image/jpeg", inline=True)
    assert headers["Content-Disposition"] == 'inline; filename="photo.jpg"'


# --- uploads ----------------------------------------------------------------------------------------------


def _upload(raw: bytes) -> UploadFile:
    return UploadFile(io.BytesIO(raw), filename="f.xlsx")


def test_an_upload_is_read_only_up_to_its_limit() -> None:
    assert read_upload(_upload(b"x" * 10), 10, "too big") == b"x" * 10
    with pytest.raises(ApiError, match="too big"):
        read_upload(_upload(b"x" * 11), 10, "too big")
    with pytest.raises(ApiError, match="empty"):
        read_upload(_upload(b""), 10, "too big")


def _zip(entries: dict[str, bytes]) -> bytes:
    out = io.BytesIO()
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, data in entries.items():
            archive.writestr(name, data)
    return out.getvalue()


def test_a_workbook_that_unpacks_too_far_is_refused() -> None:
    bomb = _zip({"[Content_Types].xml": b"<x/>", "xl/sheet1.xml": b"\0" * (MAX_UNPACKED_BYTES + 1)})
    assert len(bomb) < 1024 * 1024  # small on the wire
    with pytest.raises(ApiError, match="too large once unpacked"):
        check_workbook_archive(bomb)


def test_a_workbook_with_macros_is_refused() -> None:
    with pytest.raises(ApiError, match="macros"):
        check_workbook_archive(_zip({"[Content_Types].xml": b"<x/>", "xl/vbaProject.bin": b"x"}))


def test_a_normal_workbook_and_a_non_zip_pass_to_the_parser() -> None:
    check_workbook_archive(_zip({"[Content_Types].xml": b"<x/>", "xl/workbook.xml": b"<w/>"}))
    check_workbook_archive(b"not a zip at all")


def test_workbook_xml_is_parsed_with_entity_protection() -> None:
    import openpyxl.xml

    assert openpyxl.xml.DEFUSEDXML is True


# --- settings ---------------------------------------------------------------------------------------------


@pytest.mark.parametrize("key", ["", "short-key"])
def test_prod_needs_a_strong_download_signing_key(key: str) -> None:
    with pytest.raises(ValidationError, match="DOWNLOAD_SIGNING_KEY"):
        Settings(
            environment="prod",
            cognito_user_pool_id="pool",
            cognito_app_client_id="client",
            download_signing_key=key,
            _env_file=None,
        )


def test_prod_starts_with_a_strong_download_signing_key() -> None:
    settings = Settings(
        environment="prod",
        cognito_user_pool_id="pool",
        cognito_app_client_id="client",
        download_signing_key="k" * 64,
        _env_file=None,
    )
    assert settings.rate_limit_enabled is True


def test_dev_sign_in_is_refused_in_prod() -> None:
    with pytest.raises(ValidationError, match="AUTH_MODE=dev"):
        Settings(environment="prod", auth_mode="dev", dev_username="x", download_signing_key="k" * 64, _env_file=None)
