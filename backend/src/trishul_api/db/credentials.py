"""Database credentials sourced from AWS Secrets Manager.

The secret is stored in the format AWS RDS uses for its managed rotation secrets, so RDS can rotate it
in place::

    {"username": "trishul_app", "password": "...", "engine": "sqlserver",
     "host": "...", "port": 1433, "dbname": "TrishulDev"}

Only ``username`` and ``password`` are read here; the host, port and database name stay in configuration
so a secret can't silently repoint the API at another server.
"""

from dataclasses import dataclass

from trishul_api.secrets import SecretError, SecretProvider


@dataclass(frozen=True)
class DbCredentials:
    username: str
    password: str

    def __repr__(self) -> str:  # never let the password reach a log line or traceback
        return f"DbCredentials(username={self.username!r}, password=***)"


def db_credentials(provider: SecretProvider, secret_id: str) -> DbCredentials:
    """Read the current username and password from the named secret."""
    data = provider.get_json(secret_id)
    try:
        return DbCredentials(username=str(data["username"]), password=str(data["password"]))
    except KeyError as error:
        raise SecretError(f"Secret '{secret_id}' is missing {error} (expected username and password).") from None
