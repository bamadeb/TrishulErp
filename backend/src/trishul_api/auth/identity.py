"""Administration of sign-in accounts (create, disable, reset password) in the identity provider.

The ERP keeps users in core.app_user; the identity provider (Cognito) keeps their passwords. User
management changes both, through this interface.
"""

import secrets
import string
from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal, Protocol

import boto3
from botocore.exceptions import ClientError

from trishul_api.common.errors import AlreadyExists, ApiError
from trishul_api.config import Settings

if TYPE_CHECKING:
    from collections.abc import Callable

    from mypy_boto3_cognito_idp import CognitoIdentityProviderClient
    from mypy_boto3_cognito_idp.type_defs import AdminGetUserResponseTypeDef, AttributeTypeTypeDef

SignInStatus = Literal[
    "active",  # has signed in with their own password
    "password-change-required",  # invited or given a temporary password; must choose one at sign-in
    "reset-required",  # must reset with an emailed code ("Forgot password?")
    "disabled",
    "missing",  # no account in the identity provider
    "development",  # dev sign-in: no password
    "unknown",
]
Delivery = Literal["email", "show"]


@dataclass(frozen=True)
class CreatedAccount:
    subject: str
    """The provider's permanent user id (Cognito sub), stored in core.app_user.cognito_sub."""
    temporary_password: str | None
    """Set when delivery is "show": give it to the user; they must change it at first sign-in."""


class IdentityProviderError(ApiError):
    status = 502
    title = "Sign-in service error"


class AccountExists(AlreadyExists):
    pass


class IdentityProvider(Protocol):
    def create_account(self, email: str, delivery: Delivery) -> CreatedAccount: ...

    def find_subject(self, email: str) -> str | None: ...

    def delete_account(self, email: str) -> None: ...

    def status(self, email: str) -> SignInStatus: ...

    def disable(self, email: str) -> None:
        """Blocks sign-in and ends every session (refresh tokens revoked)."""
        ...

    def enable(self, email: str) -> None: ...

    def reset_password(self, email: str, delivery: Delivery) -> str | None:
        """Returns the temporary password when delivery is "show"."""
        ...


def temporary_password(length: int = 16) -> str:
    """Random password meeting the pool policy (12+ characters), without look-alike characters."""
    alphabet = "".join(c for c in string.ascii_letters + string.digits if c not in "Il1O0o") + "!#%+=?"
    while True:
        password = "".join(secrets.choice(alphabet) for _ in range(length))
        if any(c.isdigit() for c in password) and any(c.isupper() for c in password):
            return password


_STATUS: dict[str, SignInStatus] = {
    "CONFIRMED": "active",
    "FORCE_CHANGE_PASSWORD": "password-change-required",
    "RESET_REQUIRED": "reset-required",
}


class CognitoIdentityProvider:
    """Cognito user pool through the admin API (needs cognito-idp:Admin* on the pool)."""

    def __init__(self, settings: Settings, client: "CognitoIdentityProviderClient | None" = None) -> None:
        self._pool = settings.cognito_user_pool_id
        if client is None:
            session = boto3.Session(profile_name=settings.aws_profile, region_name=settings.cognito_region)
            client = session.client("cognito-idp")
        self._client = client

    def create_account(self, email: str, delivery: Delivery) -> CreatedAccount:
        password = temporary_password() if delivery == "show" else None
        try:
            if password:
                response = self._client.admin_create_user(
                    UserPoolId=self._pool,
                    Username=email,
                    UserAttributes=_email_attributes(email),
                    TemporaryPassword=password,
                    MessageAction="SUPPRESS",
                )
            else:
                response = self._client.admin_create_user(
                    UserPoolId=self._pool,
                    Username=email,
                    UserAttributes=_email_attributes(email),
                    DesiredDeliveryMediums=["EMAIL"],
                )
        except ClientError as error:
            if _code(error) == "UsernameExistsException":
                raise AccountExists("A sign-in account with this email already exists.") from error
            raise _provider_error(error) from error
        attributes = {a["Name"]: a.get("Value", "") for a in response["User"].get("Attributes", [])}
        return CreatedAccount(subject=attributes["sub"], temporary_password=password)

    def find_subject(self, email: str) -> str | None:
        user = self._get(email)
        if user is None:
            return None
        return next((a["Value"] for a in user["UserAttributes"] if a["Name"] == "sub"), None)

    def delete_account(self, email: str) -> None:
        self._call(lambda: self._client.admin_delete_user(UserPoolId=self._pool, Username=email))

    def status(self, email: str) -> SignInStatus:
        user = self._get(email)
        if user is None:
            return "missing"
        if not user.get("Enabled", True):
            return "disabled"
        return _STATUS.get(user.get("UserStatus", ""), "unknown")

    def disable(self, email: str) -> None:
        self._call(lambda: self._client.admin_disable_user(UserPoolId=self._pool, Username=email))
        self._call(lambda: self._client.admin_user_global_sign_out(UserPoolId=self._pool, Username=email))

    def enable(self, email: str) -> None:
        self._call(lambda: self._client.admin_enable_user(UserPoolId=self._pool, Username=email))

    def reset_password(self, email: str, delivery: Delivery) -> str | None:
        if delivery == "show":
            password = temporary_password()
            self._call(
                lambda: self._client.admin_set_user_password(
                    UserPoolId=self._pool, Username=email, Password=password, Permanent=False
                )
            )
            self._call(lambda: self._client.admin_user_global_sign_out(UserPoolId=self._pool, Username=email))
            return password
        if self.status(email) == "password-change-required":
            # Never signed in: send a fresh invitation instead (a reset needs a confirmed account).
            self._call(
                lambda: self._client.admin_create_user(
                    UserPoolId=self._pool, Username=email, MessageAction="RESEND", DesiredDeliveryMediums=["EMAIL"]
                )
            )
        else:
            self._call(lambda: self._client.admin_reset_user_password(UserPoolId=self._pool, Username=email))
        return None

    def _get(self, email: str) -> "AdminGetUserResponseTypeDef | None":
        try:
            return self._client.admin_get_user(UserPoolId=self._pool, Username=email)
        except ClientError as error:
            if _code(error) == "UserNotFoundException":
                return None
            raise _provider_error(error) from error

    @staticmethod
    def _call(action: "Callable[[], object]") -> None:
        try:
            action()
        except ClientError as error:
            raise _provider_error(error) from error


class DevIdentityProvider:
    """Development sign-in: accounts exist only in core.app_user and have no passwords."""

    def create_account(self, email: str, delivery: Delivery) -> CreatedAccount:
        return CreatedAccount(subject=f"dev:{email}", temporary_password=None)

    def find_subject(self, email: str) -> str | None:
        return None

    def delete_account(self, email: str) -> None:
        return None

    def status(self, email: str) -> SignInStatus:
        return "development"

    def disable(self, email: str) -> None:
        return None

    def enable(self, email: str) -> None:
        return None

    def reset_password(self, email: str, delivery: Delivery) -> str | None:
        raise ApiError("Development sign-in has no passwords to reset.")


def create_identity_provider(settings: Settings) -> IdentityProvider:
    if settings.auth_mode == "cognito":
        return CognitoIdentityProvider(settings)
    return DevIdentityProvider()


def _email_attributes(email: str) -> list["AttributeTypeTypeDef"]:
    # Marked verified: the address comes from the company, and password resets are sent to it.
    return [{"Name": "email", "Value": email}, {"Name": "email_verified", "Value": "true"}]


def _code(error: ClientError) -> str:
    return str(error.response.get("Error", {}).get("Code", ""))


def _provider_error(error: ClientError) -> IdentityProviderError:
    messages = {
        "UserNotFoundException": "This user has no sign-in account in Cognito.",
        "InvalidParameterException": "Cognito rejected the request: "
        + str(error.response.get("Error", {}).get("Message")),
        "LimitExceededException": "Too many requests to Cognito. Wait a minute and try again.",
        "TooManyRequestsException": "Too many requests to Cognito. Wait a minute and try again.",
        "NotAuthorizedException": "The API is not allowed to manage Cognito users. Check its AWS permissions.",
        "AccessDeniedException": "The API is not allowed to manage Cognito users. Check its AWS permissions.",
    }
    return IdentityProviderError(messages.get(_code(error), "The sign-in service could not complete the request."))
