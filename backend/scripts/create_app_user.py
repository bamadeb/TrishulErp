"""Creates an ERP user (core.app_user) linked to its Cognito user, with a role.

    uv run python scripts/create_app_user.py admindemo@trishul.co --cognito-sub <sub> --role ADMIN
    uv run python scripts/create_app_user.py rahul@trishul.co --cognito-sub <sub> --role TEAM_LEAD --branch BHADRAK

The Cognito user is created first (console or `aws cognito-idp admin-create-user`); its `sub`
(`aws cognito-idp admin-get-user ... --query "UserAttributes[?Name=='sub'].Value"`) links the two.
Safe to re-run: an existing user gets the given Cognito sub / email, and only missing roles are added.
"""

import argparse
import sys

from sqlalchemy import select
from sqlalchemy.orm import Session

from trishul_api.config import get_settings
from trishul_api.db import create_db_engine, set_audit_context
from trishul_api.db.models import AppUser, Branch, Role, UserRole


def ensure_app_user(
    session: Session,
    *,
    username: str,
    cognito_sub: str,
    email: str | None,
    role_code: str,
    branch_code: str | None,
) -> None:
    """Creates or updates the user and grants the role. Raises ValueError for unknown role / branch."""
    role = session.scalar(select(Role).where(Role.code == role_code, Role.is_active))
    if role is None:
        raise ValueError(f"Role {role_code} not found in core.role.")
    branch = session.scalar(select(Branch).where(Branch.code == branch_code)) if branch_code else None
    if branch_code and branch is None:
        raise ValueError(f"Branch {branch_code} not found in core.branch.")
    default_branch = branch or session.scalar(select(Branch).where(Branch.is_active).order_by(Branch.id))

    user = session.scalar(select(AppUser).where(AppUser.username == username))
    if user is None:
        user = AppUser(
            username=username,
            cognito_sub=cognito_sub,
            email=email,
            default_branch_id=default_branch.id if default_branch else None,
        )
        session.add(user)
        session.flush()
        print(f"Created app user {username} (id {user.id}).")
    else:
        if user.cognito_sub != cognito_sub:
            user.cognito_sub = cognito_sub
            print(f"Linked existing app user {username} (id {user.id}) to Cognito sub {cognito_sub}.")
        if email and user.email != email:
            user.email = email
        print(f"App user {username} exists (id {user.id}).")

    branch_id = branch.id if branch else None
    branch_match = UserRole.branch_id.is_(None) if branch_id is None else UserRole.branch_id == branch_id
    has_role = session.scalar(
        select(UserRole.id).where(UserRole.app_user_id == user.id, UserRole.role_id == role.id, branch_match)
    )
    where = branch_code or "all branches"
    if has_role is None:
        session.add(UserRole(app_user_id=user.id, role_id=role.id, branch_id=branch_id))
        print(f"Granted {role.code} on {where}.")
    else:
        print(f"Already has {role.code} on {where}.")


def run(*, username: str, cognito_sub: str, email: str | None, role: str, branch: str | None) -> int:
    engine = create_db_engine(get_settings())
    with Session(engine) as session:
        set_audit_context(session, user_id=None, source="System", ip_address=None)
        try:
            ensure_app_user(
                session, username=username, cognito_sub=cognito_sub, email=email, role_code=role, branch_code=branch
            )
        except ValueError as exc:
            print(exc)
            return 1
        session.commit()
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("username", help="sign-in name; the email address for the Trishul user pool")
    parser.add_argument("--cognito-sub", required=True, help="the Cognito user's sub attribute")
    parser.add_argument("--email", help="defaults to the username when it is an email address")
    parser.add_argument("--role", default="ADMIN", help="core.role code (default ADMIN)")
    parser.add_argument("--branch", help="core.branch code to limit the role to; default: all branches")
    args = parser.parse_args()
    email = args.email or (args.username if "@" in args.username else None)
    return run(username=args.username, cognito_sub=args.cognito_sub, email=email, role=args.role, branch=args.branch)


if __name__ == "__main__":
    sys.exit(main())
