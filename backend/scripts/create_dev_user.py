"""Creates the local sign-in user for TRISHUL_AUTH_MODE=dev (dev and test databases only).

    uv run python scripts/create_dev_user.py            # TRISHUL_DEV_USERNAME with the ADMIN role
    uv run python scripts/create_dev_user.py --role TEAM_LEAD --branch BHADRAK

The user has no Cognito account (its cognito_sub is a placeholder), so it can only sign in through
dev mode. Safe to re-run. For real users, use create_app_user.py.
"""

import argparse
import sys

from create_app_user import run

from trishul_api.config import get_settings


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--role", default="ADMIN", help="core.role code (default ADMIN)")
    parser.add_argument("--branch", help="core.branch code to limit the role to; default: all branches")
    args = parser.parse_args()

    settings = get_settings()
    if settings.environment not in ("dev", "test"):
        print(f"Refusing: TRISHUL_ENVIRONMENT is {settings.environment}; dev users are for dev and test only.")
        return 1
    if not settings.dev_username:
        print("Set TRISHUL_DEV_USERNAME first.")
        return 1
    return run(
        username=settings.dev_username,
        cognito_sub=f"dev:{settings.dev_username}",
        email=None,
        role=args.role,
        branch=args.branch,
    )


if __name__ == "__main__":
    sys.exit(main())
