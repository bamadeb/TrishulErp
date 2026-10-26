"""Writes the API's OpenAPI document to frontend/libs/core/api/openapi.json.

uv run python scripts/export_openapi.py            # then: npx nx run core-api:generate (in frontend/)
uv run python scripts/export_openapi.py --check    # CI: fail if the committed copy is stale
"""

import json
import os
import sys
from pathlib import Path

TARGET = Path(__file__).resolve().parents[2] / "frontend" / "libs" / "core" / "api" / "openapi.json"


def render() -> str:
    # The document doesn't depend on sign-in settings; dev mode avoids needing Cognito ids here.
    os.environ.setdefault("TRISHUL_AUTH_MODE", "dev")
    os.environ.setdefault("TRISHUL_DEV_USERNAME", "openapi-export")
    from trishul_api.config import get_settings
    from trishul_api.main import create_api_v1

    return json.dumps(create_api_v1(get_settings()).openapi(), indent=2, ensure_ascii=False) + "\n"


def main() -> int:
    document = render()
    if "--check" in sys.argv:
        if not TARGET.exists() or TARGET.read_text(encoding="utf-8") != document:
            print(f"{TARGET} is out of date: run scripts/export_openapi.py and regenerate the client.")
            return 1
        print("OpenAPI document is up to date.")
        return 0
    TARGET.write_text(document, encoding="utf-8", newline="\n")
    print(f"Wrote {TARGET}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
