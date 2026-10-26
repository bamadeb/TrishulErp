"""FastAPI dependencies for sign-in, permissions, branch / brand scope and the user's DB session."""

from collections.abc import Callable, Iterator
from dataclasses import dataclass
from typing import Annotated

from fastapi import Depends, Header, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import Engine
from sqlalchemy.orm import Session

from trishul_api.auth.tokens import TokenVerifier
from trishul_api.auth.users import CurrentUser, UserDirectory
from trishul_api.common.errors import Forbidden, Unauthorized
from trishul_api.db import AuditSource, set_audit_context, user_session

_bearer = HTTPBearer(auto_error=False, description="Cognito access token")

# Sent on every call by the Angular HTTP interceptor, so they are left out of each operation
# in the OpenAPI document (and the generated client) instead of being repeated everywhere.
_CONTEXT_HEADER = Header(include_in_schema=False)


def get_engine(request: Request) -> Engine:
    engine: Engine = request.app.state.engine
    return engine


def get_token_verifier(request: Request) -> TokenVerifier:
    verifier: TokenVerifier = request.app.state.token_verifier
    return verifier


def get_user_directory(request: Request) -> UserDirectory:
    directory: UserDirectory = request.app.state.user_directory
    return directory


def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
    verifier: Annotated[TokenVerifier, Depends(get_token_verifier)],
    directory: Annotated[UserDirectory, Depends(get_user_directory)],
) -> CurrentUser:
    if credentials is None:
        raise Unauthorized("Sign in to continue.")
    user = directory.get(verifier.verify(credentials.credentials))
    if user is None:
        # 403, not 401: signing in again would not help.
        raise Forbidden("Your account is not set up in Trishul ERP or is locked. Contact your administrator.")
    return user


CurrentUserDep = Annotated[CurrentUser, Depends(get_current_user)]


def require_permission(*codes: str) -> Callable[[CurrentUser], CurrentUser]:
    """Route dependency: the user must hold at least one of the core.permission codes."""

    def check(user: CurrentUserDep) -> CurrentUser:
        if not user.can(*codes):
            raise Forbidden("You do not have permission for this action.")
        return user

    return check


@dataclass(frozen=True)
class RequestScope:
    """Branch and brand the user is working in, from the X-Branch-Id / X-Principal-Id headers."""

    branch_id: int | None
    principal_id: int | None


def get_scope(
    user: CurrentUserDep,
    x_branch_id: Annotated[int | None, _CONTEXT_HEADER] = None,
    x_principal_id: Annotated[int | None, _CONTEXT_HEADER] = None,
) -> RequestScope:
    branch_id = x_branch_id if x_branch_id is not None else user.default_branch_id
    if branch_id is not None and not user.can_use_branch(branch_id):
        raise Forbidden("You do not have access to this branch.")
    if x_principal_id is not None and not user.can_see_principal(x_principal_id):
        raise Forbidden("You do not have access to this brand.")
    return RequestScope(branch_id=branch_id, principal_id=x_principal_id)


ScopeDep = Annotated[RequestScope, Depends(get_scope)]


_PLATFORMS: dict[str, AuditSource] = {"web": "Web", "android": "Android", "ios": "iOS", "api": "API"}


def get_db(
    request: Request,
    user: CurrentUserDep,
    engine: Annotated[Engine, Depends(get_engine)],
    x_client_platform: Annotated[str | None, _CONTEXT_HEADER] = None,
) -> Iterator[Session]:
    """Session tagged with the user for row-level security and auditing. Commit explicitly after writes."""
    with user_session(engine, user.id) as session:
        set_audit_context(
            session,
            user_id=user.id,
            source=_PLATFORMS.get((x_client_platform or "").lower(), "Web"),
            # Behind the ALB, uvicorn's --proxy-headers makes this the real client address.
            ip_address=request.client.host if request.client else None,
        )
        yield session


DbSession = Annotated[Session, Depends(get_db)]
